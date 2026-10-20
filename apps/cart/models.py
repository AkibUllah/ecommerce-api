from __future__ import annotations

import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models

from apps.catalog.models import ProductVariant
from apps.core.models import TimeStampedModel
from apps.core.money import ZERO, quantize


class Cart(TimeStampedModel):
    """A cart belongs either to a logged-in user or to an anonymous token.

    Guests get a ``token`` returned in the ``X-Cart-Token`` header; after login the
    client calls ``/cart/merge/`` to fold the guest cart into the user's cart.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="cart",
    )
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    class Meta:
        ordering = ("-updated_at",)

    def __str__(self) -> str:
        owner = self.user.username if self.user_id else f"guest:{str(self.token)[:8]}"
        return f"Cart({owner})"

    @property
    def subtotal(self) -> Decimal:
        return quantize(sum((item.line_total for item in self.items.all()), ZERO))

    @property
    def total_items(self) -> int:
        return sum(item.quantity for item in self.items.all())

    @property
    def total_weight_grams(self) -> int:
        return sum(item.variant.weight_grams * item.quantity for item in self.items.all())


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("cart", "variant")
        ordering = ("added_at",)

    def __str__(self) -> str:
        return f"{self.quantity} x {self.variant.sku}"

    @property
    def unit_price(self) -> Decimal:
        return self.variant.effective_price

    @property
    def line_total(self) -> Decimal:
        return quantize(self.unit_price * self.quantity)
