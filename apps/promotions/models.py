from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


class Coupon(TimeStampedModel):
    class Type(models.TextChoices):
        PERCENT = "percent", "Percentage off"
        FIXED = "fixed", "Fixed amount off"
        FREE_SHIPPING = "free_shipping", "Free shipping"

    code = models.CharField(max_length=40, unique=True)
    description = models.CharField(max_length=200, blank=True)
    type = models.CharField(max_length=20, choices=Type.choices)
    value = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text="Percent (0-100) for percent coupons, BDT amount for fixed coupons.",
    )
    min_order_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    max_discount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Cap for percentage coupons.",
    )
    usage_limit = models.PositiveIntegerField(null=True, blank=True)
    per_user_limit = models.PositiveIntegerField(null=True, blank=True)
    used_count = models.PositiveIntegerField(default=0)
    starts_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("code",)

    def __str__(self) -> str:
        return self.code

    def save(self, *args, **kwargs):
        self.code = self.code.strip().upper()
        super().save(*args, **kwargs)


class CouponRedemption(models.Model):
    coupon = models.ForeignKey(Coupon, on_delete=models.CASCADE, related_name="redemptions")
    order = models.OneToOneField(
        "orders.Order", on_delete=models.CASCADE, related_name="coupon_redemption"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2)
    shipping_discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    redeemed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.coupon.code} on {self.order_id}"
