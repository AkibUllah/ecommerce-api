from django.contrib import admin

from .models import Coupon, CouponRedemption


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "type",
        "value",
        "min_order_amount",
        "used_count",
        "usage_limit",
        "expires_at",
        "is_active",
    )
    list_filter = ("type", "is_active")
    search_fields = ("code", "description")
    readonly_fields = ("used_count",)


@admin.register(CouponRedemption)
class CouponRedemptionAdmin(admin.ModelAdmin):
    list_display = (
        "coupon",
        "order",
        "user",
        "discount_amount",
        "shipping_discount",
        "redeemed_at",
    )
    search_fields = ("coupon__code", "order__number")
