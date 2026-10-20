"""Coupon validation and discount math.

``validate_coupon`` is pure (no writes); ``redeem``/``revert`` adjust usage counters
and are called from the checkout / cancellation transactions.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.core.exceptions import CouponError
from apps.core.money import ZERO, percent_of, quantize

from .models import Coupon, CouponRedemption


@dataclass(frozen=True)
class DiscountResult:
    coupon: Coupon
    discount: Decimal  # applied to the merchandise subtotal
    shipping_discount: Decimal  # applied to the shipping fee

    @property
    def total(self) -> Decimal:
        return self.discount + self.shipping_discount


def validate_coupon(code: str, *, subtotal: Decimal, user=None) -> Coupon:
    """Return the coupon if it can be applied to an order of ``subtotal``; raise otherwise."""
    normalized = (code or "").strip().upper()
    if not normalized:
        raise CouponError("Coupon code is required.")
    try:
        coupon = Coupon.objects.get(code=normalized)
    except Coupon.DoesNotExist:
        raise CouponError("Coupon code not found.", details={"code": normalized})

    now = timezone.now()
    if not coupon.is_active:
        raise CouponError("This coupon is no longer active.")
    if coupon.starts_at and now < coupon.starts_at:
        raise CouponError("This coupon is not valid yet.")
    if coupon.expires_at and now >= coupon.expires_at:
        raise CouponError("This coupon has expired.")
    if coupon.usage_limit is not None and coupon.used_count >= coupon.usage_limit:
        raise CouponError("This coupon has reached its usage limit.")
    if subtotal < coupon.min_order_amount:
        raise CouponError(
            f"Order subtotal must be at least {coupon.min_order_amount} to use this coupon.",
            details={"min_order_amount": str(coupon.min_order_amount)},
        )
    if coupon.per_user_limit is not None and user is not None and user.is_authenticated:
        used = CouponRedemption.objects.filter(coupon=coupon, user=user).count()
        if used >= coupon.per_user_limit:
            raise CouponError("You have already used this coupon the maximum number of times.")
    return coupon


def compute_discount(coupon: Coupon, *, subtotal: Decimal, shipping_fee: Decimal) -> DiscountResult:
    subtotal = quantize(subtotal)
    shipping_fee = quantize(shipping_fee)
    discount = ZERO
    shipping_discount = ZERO

    if coupon.type == Coupon.Type.PERCENT:
        discount = percent_of(subtotal, coupon.value / Decimal(100))
        if coupon.max_discount is not None:
            discount = min(discount, quantize(coupon.max_discount))
    elif coupon.type == Coupon.Type.FIXED:
        discount = min(quantize(coupon.value), subtotal)
    elif coupon.type == Coupon.Type.FREE_SHIPPING:
        shipping_discount = shipping_fee

    return DiscountResult(coupon=coupon, discount=discount, shipping_discount=shipping_discount)


def apply_coupon(
    code: str, *, subtotal: Decimal, shipping_fee: Decimal, user=None
) -> DiscountResult:
    coupon = validate_coupon(code, subtotal=subtotal, user=user)
    return compute_discount(coupon, subtotal=subtotal, shipping_fee=shipping_fee)


@transaction.atomic
def redeem(result: DiscountResult, *, order, user=None) -> CouponRedemption:
    """Record the redemption and bump the usage counter atomically (re-checking the limit)."""
    coupon = Coupon.objects.select_for_update().get(pk=result.coupon.pk)
    if coupon.usage_limit is not None and coupon.used_count >= coupon.usage_limit:
        raise CouponError("This coupon has reached its usage limit.")
    Coupon.objects.filter(pk=coupon.pk).update(used_count=F("used_count") + 1)
    return CouponRedemption.objects.create(
        coupon=coupon,
        order=order,
        user=user if (user is not None and user.is_authenticated) else None,
        discount_amount=result.discount,
        shipping_discount=result.shipping_discount,
    )


@transaction.atomic
def revert(order) -> None:
    """Give the usage back when an order is cancelled or expires unpaid."""
    redemption = CouponRedemption.objects.filter(order=order).select_related("coupon").first()
    if redemption is None:
        return
    Coupon.objects.filter(pk=redemption.coupon_id, used_count__gt=0).update(
        used_count=F("used_count") - 1
    )
    redemption.delete()
