from __future__ import annotations

import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.catalog.models import Inventory, ProductVariant
from apps.core.exceptions import InvalidTransition
from apps.core.models import TimeStampedModel


def generate_order_number() -> str:
    """Human-friendly, non-sequential order number, e.g. ``ORD-20260312-7K3Q9X``."""
    stamp = timezone.now().strftime("%Y%m%d")
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    suffix = "".join(secrets.choice(alphabet) for _ in range(6))
    return f"ORD-{stamp}-{suffix}"


class OrderStatus(models.TextChoices):
    PENDING = "pending", "Pending payment"
    CONFIRMED = "confirmed", "Confirmed"
    PROCESSING = "processing", "Processing"
    SHIPPED = "shipped", "Shipped"
    DELIVERED = "delivered", "Delivered"
    CANCELLED = "cancelled", "Cancelled"
    EXPIRED = "expired", "Expired (unpaid)"
    REFUNDED = "refunded", "Refunded"


# Allowed transitions. Anything not listed raises InvalidTransition.
TRANSITIONS: dict[str, frozenset[str]] = {
    OrderStatus.PENDING: frozenset(
        {OrderStatus.CONFIRMED, OrderStatus.CANCELLED, OrderStatus.EXPIRED}
    ),
    OrderStatus.CONFIRMED: frozenset({OrderStatus.PROCESSING, OrderStatus.CANCELLED}),
    OrderStatus.PROCESSING: frozenset({OrderStatus.SHIPPED, OrderStatus.CANCELLED}),
    OrderStatus.SHIPPED: frozenset({OrderStatus.DELIVERED, OrderStatus.REFUNDED}),
    OrderStatus.DELIVERED: frozenset({OrderStatus.REFUNDED}),
    OrderStatus.CANCELLED: frozenset(),
    OrderStatus.EXPIRED: frozenset(),
    OrderStatus.REFUNDED: frozenset(),
}

# Statuses in which stock is still only *reserved* (not yet committed).
RESERVED_STATUSES = frozenset({OrderStatus.PENDING})
# Statuses in which committed stock should be returned to the shelf on cancellation.
COMMITTED_STATUSES = frozenset({OrderStatus.CONFIRMED, OrderStatus.PROCESSING})


class PaymentMethod(models.TextChoices):
    BKASH = "bkash", "bKash"
    SSLCOMMERZ = "sslcommerz", "SSLCommerz (card / MFS / netbanking)"
    COD = "cod", "Cash on delivery"


class Order(TimeStampedModel):
    number = models.CharField(max_length=24, unique=True, default=generate_order_number)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="orders",
    )
    status = models.CharField(
        max_length=20, choices=OrderStatus.choices, default=OrderStatus.PENDING, db_index=True
    )

    # Contact + shipping address (denormalised; addresses change, orders must not)
    customer_name = models.CharField(max_length=120)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20)
    address_line = models.CharField(max_length=255)
    area = models.CharField(max_length=120, blank=True, help_text="Thana / upazila")
    district = models.CharField(max_length=80)
    postcode = models.CharField(max_length=10, blank=True)
    notes = models.TextField(blank=True)

    # Shipping
    shipping_zone = models.CharField(max_length=20)
    courier = models.CharField(max_length=20)
    shipping_fee = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # Money
    currency = models.CharField(max_length=3, default="BDT")
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    shipping_discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    vat_rate = models.DecimalField(max_digits=5, decimal_places=4, default=0)
    vat = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    coupon_code = models.CharField(max_length=40, blank=True)

    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices)
    paid_at = models.DateTimeField(null=True, blank=True)
    reservation_expires_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return self.number

    # -- state machine -------------------------------------------------------
    def can_transition(self, new_status: str) -> bool:
        return new_status in TRANSITIONS.get(self.status, frozenset())

    def transition(self, new_status: str, *, note: str = "", actor=None) -> None:
        if not self.can_transition(new_status):
            raise InvalidTransition(
                f"Cannot move order {self.number} from '{self.status}' to '{new_status}'.",
                details={"from": self.status, "to": new_status},
            )
        previous = self.status
        self.status = new_status
        if new_status == OrderStatus.CONFIRMED and self.paid_at is None:
            self.paid_at = timezone.now()
        self.save(update_fields=["status", "paid_at", "updated_at"])
        OrderStatusHistory.objects.create(
            order=self,
            from_status=previous,
            to_status=new_status,
            note=note,
            actor=actor if (actor is not None and getattr(actor, "pk", None)) else None,
        )

    @property
    def is_expired(self) -> bool:
        return (
            self.status == OrderStatus.PENDING
            and self.reservation_expires_at is not None
            and self.reservation_expires_at <= timezone.now()
        )


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    variant = models.ForeignKey(ProductVariant, on_delete=models.PROTECT)
    product_name = models.CharField(max_length=200)
    variant_name = models.CharField(max_length=120)
    sku = models.CharField(max_length=64)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    quantity = models.PositiveIntegerField()
    line_total = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self) -> str:
        return f"{self.quantity} x {self.sku}"


class StockReservation(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        COMMITTED = "committed", "Committed"
        RELEASED = "released", "Released"

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="reservations")
    inventory = models.ForeignKey(Inventory, on_delete=models.CASCADE, related_name="reservations")
    quantity = models.PositiveIntegerField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    expires_at = models.DateTimeField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return f"{self.quantity} x {self.inventory.variant.sku} ({self.status})"


class OrderStatusHistory(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="history")
    from_status = models.CharField(max_length=20, blank=True)
    to_status = models.CharField(max_length=20)
    note = models.CharField(max_length=255, blank=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at",)
        verbose_name_plural = "order status history"

    def __str__(self) -> str:
        return f"{self.order.number}: {self.from_status} -> {self.to_status}"
