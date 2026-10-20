"""Checkout and order lifecycle.

``place_order`` is the heart of the system. Inside one database transaction it

1. locks the inventory rows for every cart line (``select_for_update``, ordered by
   PK so two checkouts always lock in the same order),
2. reserves stock, failing fast with ``InsufficientStock`` if anything is short,
3. prices the order: subtotal, coupon discount, VAT on the discounted goods,
   courier fee by zone and weight,
4. writes the order, its items and a ``StockReservation`` per line that expires
   after ``RESERVATION_TTL_MINUTES``.

Cash-on-delivery orders are confirmed immediately (stock committed); online
payments stay ``PENDING`` until the provider webhook arrives.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.cart import services as cart_services
from apps.cart.models import Cart
from apps.catalog import services as inventory
from apps.core.exceptions import DomainError, InvalidTransition
from apps.core.money import ZERO, percent_of, quantize
from apps.promotions import services as promotions
from apps.shipping.rates import get_calculator
from apps.shipping.zones import zone_for_district

from .models import (
    COMMITTED_STATUSES,
    RESERVED_STATUSES,
    Order,
    OrderItem,
    OrderStatus,
    OrderStatusHistory,
    PaymentMethod,
    StockReservation,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ShippingAddress:
    customer_name: str
    phone: str
    address_line: str
    district: str
    area: str = ""
    postcode: str = ""
    email: str = ""


@dataclass(frozen=True)
class PriceBreakdown:
    subtotal: Decimal
    discount: Decimal
    shipping_fee: Decimal
    shipping_discount: Decimal
    vat_rate: Decimal
    vat: Decimal
    total: Decimal


def price_order(
    *,
    subtotal: Decimal,
    shipping_fee: Decimal,
    discount: Decimal = ZERO,
    shipping_discount: Decimal = ZERO,
    vat_rate: Decimal | None = None,
) -> PriceBreakdown:
    """Pure pricing: ``total = (subtotal - discount) + VAT + (shipping - shipping_discount)``.

    VAT is charged on the discounted merchandise value only; courier fees are passed
    through without VAT.
    """
    vat_rate = settings.VAT_RATE if vat_rate is None else vat_rate
    subtotal = quantize(subtotal)
    discount = min(quantize(discount), subtotal)
    shipping_fee = quantize(shipping_fee)
    shipping_discount = min(quantize(shipping_discount), shipping_fee)
    taxable = subtotal - discount
    vat = percent_of(taxable, vat_rate)
    total = quantize(taxable + vat + shipping_fee - shipping_discount)
    return PriceBreakdown(
        subtotal=subtotal,
        discount=discount,
        shipping_fee=shipping_fee,
        shipping_discount=shipping_discount,
        vat_rate=Decimal(vat_rate),
        vat=vat,
        total=total,
    )


@transaction.atomic
def place_order(
    *,
    cart: Cart,
    address: ShippingAddress,
    courier: str,
    payment_method: str,
    coupon_code: str = "",
    user=None,
    notes: str = "",
) -> Order:
    items = list(cart.items.select_related("variant__product").order_by("variant_id"))
    if not items:
        raise DomainError("Cart is empty.")
    if payment_method not in PaymentMethod.values:
        raise DomainError(f"Unsupported payment method '{payment_method}'.")

    # 1. lock + reserve
    inventories = inventory.lock_inventories([item.variant_id for item in items])
    for item in items:
        inv = inventories.get(item.variant_id)
        if inv is None:
            raise DomainError(f"No inventory record for {item.variant.sku}.")
        inventory.reserve(inv, item.quantity)

    # 2. price
    subtotal = quantize(sum((item.line_total for item in items), ZERO))
    weight = sum(item.variant.weight_grams * item.quantity for item in items)
    zone = zone_for_district(address.district)
    cod_amount = subtotal if payment_method == PaymentMethod.COD else ZERO
    shipping_quote = get_calculator(courier).quote(zone, weight, cod_amount)

    discount_result = None
    if coupon_code:
        discount_result = promotions.apply_coupon(
            coupon_code, subtotal=subtotal, shipping_fee=shipping_quote.total, user=user
        )
    breakdown = price_order(
        subtotal=subtotal,
        shipping_fee=shipping_quote.total,
        discount=discount_result.discount if discount_result else ZERO,
        shipping_discount=discount_result.shipping_discount if discount_result else ZERO,
    )

    # 3. persist
    expires_at = timezone.now() + timezone.timedelta(minutes=settings.RESERVATION_TTL_MINUTES)
    order = Order.objects.create(
        user=user if (user is not None and user.is_authenticated) else None,
        customer_name=address.customer_name,
        email=address.email,
        phone=address.phone,
        address_line=address.address_line,
        area=address.area,
        district=address.district,
        postcode=address.postcode,
        notes=notes,
        shipping_zone=zone.value,
        courier=courier,
        shipping_fee=breakdown.shipping_fee,
        currency=settings.DEFAULT_CURRENCY,
        subtotal=breakdown.subtotal,
        discount=breakdown.discount,
        shipping_discount=breakdown.shipping_discount,
        vat_rate=breakdown.vat_rate,
        vat=breakdown.vat,
        total=breakdown.total,
        coupon_code=discount_result.coupon.code if discount_result else "",
        payment_method=payment_method,
        reservation_expires_at=expires_at,
    )
    OrderItem.objects.bulk_create(
        [
            OrderItem(
                order=order,
                variant=item.variant,
                product_name=item.variant.product.name,
                variant_name=item.variant.name,
                sku=item.variant.sku,
                unit_price=item.unit_price,
                quantity=item.quantity,
                line_total=item.line_total,
            )
            for item in items
        ]
    )
    StockReservation.objects.bulk_create(
        [
            StockReservation(
                order=order,
                inventory=inventories[item.variant_id],
                quantity=item.quantity,
                expires_at=expires_at,
            )
            for item in items
        ]
    )
    OrderStatusHistory.objects.create(
        order=order, from_status="", to_status=order.status, note="Order placed"
    )
    if discount_result:
        promotions.redeem(discount_result, order=order, user=user)

    cart_services.clear(cart)

    if payment_method == PaymentMethod.COD:
        order = mark_paid(order, note="Cash on delivery: confirmed at checkout")

    logger.info(
        "order placed number=%s total=%s method=%s", order.number, order.total, payment_method
    )
    return order


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------
def _resolve_reservations(order: Order, *, commit_stock: bool) -> None:
    """Commit or release every ACTIVE reservation of the order under row locks."""
    reservations = list(
        order.reservations.select_related("inventory").filter(status=StockReservation.Status.ACTIVE)
    )
    if not reservations:
        return
    locked = inventory.lock_inventories([r.inventory.variant_id for r in reservations])
    now = timezone.now()
    for res in reservations:
        inv = locked[res.inventory.variant_id]
        if commit_stock:
            inventory.commit(inv, res.quantity)
            res.status = StockReservation.Status.COMMITTED
        else:
            inventory.release(inv, res.quantity)
            res.status = StockReservation.Status.RELEASED
        res.resolved_at = now
        res.save(update_fields=["status", "resolved_at"])


@transaction.atomic
def mark_paid(order: Order, *, note: str = "Payment confirmed", actor=None) -> Order:
    order = Order.objects.select_for_update().get(pk=order.pk)
    if order.status == OrderStatus.CONFIRMED:
        return order  # idempotent: duplicate webhook deliveries are harmless
    if order.status != OrderStatus.PENDING:
        raise InvalidTransition(
            f"Order {order.number} is '{order.status}' and cannot be marked paid.",
            details={"from": order.status, "to": OrderStatus.CONFIRMED},
        )
    _resolve_reservations(order, commit_stock=True)
    order.transition(OrderStatus.CONFIRMED, note=note, actor=actor)
    return order


@transaction.atomic
def cancel_order(order: Order, *, reason: str = "", actor=None) -> Order:
    order = Order.objects.select_for_update().get(pk=order.pk)
    if not order.can_transition(OrderStatus.CANCELLED):
        raise InvalidTransition(
            f"Order {order.number} in status '{order.status}' cannot be cancelled.",
            details={"from": order.status, "to": OrderStatus.CANCELLED},
        )
    if order.status in RESERVED_STATUSES:
        _resolve_reservations(order, commit_stock=False)
    elif order.status in COMMITTED_STATUSES:
        _restock_committed(order)
    promotions.revert(order)
    order.transition(OrderStatus.CANCELLED, note=reason or "Cancelled", actor=actor)
    return order


def _restock_committed(order: Order) -> None:
    """Put goods back on the shelf for orders cancelled after payment."""
    reservations = list(
        order.reservations.select_related("inventory").filter(
            status=StockReservation.Status.COMMITTED
        )
    )
    locked = inventory.lock_inventories([r.inventory.variant_id for r in reservations])
    for res in reservations:
        inv = locked[res.inventory.variant_id]
        inv.quantity += res.quantity
        inv.save(update_fields=["quantity", "updated_at"])
        res.status = StockReservation.Status.RELEASED
        res.resolved_at = timezone.now()
        res.save(update_fields=["status", "resolved_at"])


@transaction.atomic
def expire_order(order: Order) -> Order:
    order = Order.objects.select_for_update().get(pk=order.pk)
    if order.status != OrderStatus.PENDING:
        return order
    _resolve_reservations(order, commit_stock=False)
    promotions.revert(order)
    order.transition(OrderStatus.EXPIRED, note="Reservation expired before payment")
    return order


def release_expired_reservations(now=None) -> int:
    """Expire every unpaid order whose reservation window has passed. Returns the count."""
    now = now or timezone.now()
    expired_ids = list(
        Order.objects.filter(
            status=OrderStatus.PENDING, reservation_expires_at__lte=now
        ).values_list("pk", flat=True)
    )
    count = 0
    for pk in expired_ids:
        try:
            expire_order(Order.objects.get(pk=pk))
            count += 1
        except Order.DoesNotExist:  # pragma: no cover
            continue
    if count:
        logger.info("released %d expired reservation(s)", count)
    return count


@transaction.atomic
def advance_status(order: Order, new_status: str, *, note: str = "", actor=None) -> Order:
    """Staff-driven fulfilment transitions (processing, shipped, delivered, refunded)."""
    order = Order.objects.select_for_update().get(pk=order.pk)
    if new_status == OrderStatus.CANCELLED:
        return cancel_order(order, reason=note, actor=actor)
    if new_status == OrderStatus.CONFIRMED:
        return mark_paid(order, note=note or "Marked paid by staff", actor=actor)
    order.transition(new_status, note=note, actor=actor)
    return order
