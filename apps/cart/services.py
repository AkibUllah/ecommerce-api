from __future__ import annotations

from django.db import transaction
from django.db.models import F

from apps.catalog.models import ProductVariant
from apps.core.exceptions import DomainError, InsufficientStock, NotFound

from .models import Cart, CartItem


def get_or_create_cart(*, user=None, token: str | None = None) -> Cart:
    """Resolve the caller's cart: the user's cart when authenticated, else the token cart."""
    if user is not None and user.is_authenticated:
        cart, _ = Cart.objects.get_or_create(user=user)
        return cart
    if token:
        try:
            return Cart.objects.get(token=token, user__isnull=True)
        except (Cart.DoesNotExist, ValueError):
            pass
    return Cart.objects.create()


def _check_available(variant: ProductVariant, quantity: int) -> None:
    inventory = getattr(variant, "inventory", None)
    available = inventory.available if inventory else 0
    if quantity > available:
        raise InsufficientStock(
            f"Only {available} unit(s) of {variant.sku} available.",
            details={"sku": variant.sku, "requested": quantity, "available": available},
        )


@transaction.atomic
def add_item(cart: Cart, variant_id: int, quantity: int) -> CartItem:
    if quantity <= 0:
        raise DomainError("Quantity must be at least 1.")
    try:
        variant = ProductVariant.objects.select_related("product", "inventory").get(
            pk=variant_id, is_active=True, product__is_active=True
        )
    except ProductVariant.DoesNotExist:
        raise NotFound("Variant not found or inactive.")

    item, created = CartItem.objects.get_or_create(
        cart=cart, variant=variant, defaults={"quantity": 0}
    )
    new_quantity = item.quantity + quantity
    _check_available(variant, new_quantity)
    item.quantity = new_quantity
    item.save(update_fields=["quantity"])
    Cart.objects.filter(pk=cart.pk).update(updated_at=F("updated_at"))
    return item


@transaction.atomic
def set_quantity(cart: Cart, item_id: int, quantity: int) -> CartItem | None:
    try:
        item = cart.items.select_related("variant__inventory", "variant__product").get(pk=item_id)
    except CartItem.DoesNotExist:
        raise NotFound("Cart item not found.")
    if quantity <= 0:
        item.delete()
        return None
    _check_available(item.variant, quantity)
    item.quantity = quantity
    item.save(update_fields=["quantity"])
    return item


def remove_item(cart: Cart, item_id: int) -> None:
    deleted, _ = cart.items.filter(pk=item_id).delete()
    if not deleted:
        raise NotFound("Cart item not found.")


@transaction.atomic
def merge_guest_cart(user, guest_token: str) -> Cart:
    """Fold a guest cart into the user's cart (quantities are summed), then delete it."""
    user_cart, _ = Cart.objects.get_or_create(user=user)
    try:
        guest_cart = Cart.objects.get(token=guest_token, user__isnull=True)
    except (Cart.DoesNotExist, ValueError):
        return user_cart

    for guest_item in guest_cart.items.select_related("variant__inventory"):
        item, _ = CartItem.objects.get_or_create(
            cart=user_cart, variant=guest_item.variant, defaults={"quantity": 0}
        )
        inventory = getattr(guest_item.variant, "inventory", None)
        available = inventory.available if inventory else 0
        item.quantity = min(item.quantity + guest_item.quantity, max(available, 1))
        item.save(update_fields=["quantity"])
    guest_cart.delete()
    return user_cart


def clear(cart: Cart) -> None:
    cart.items.all().delete()
