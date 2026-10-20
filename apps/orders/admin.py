from django.contrib import admin

from .models import Order, OrderItem, OrderStatusHistory, StockReservation


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = (
        "variant",
        "product_name",
        "variant_name",
        "sku",
        "unit_price",
        "quantity",
        "line_total",
    )


class ReservationInline(admin.TabularInline):
    model = StockReservation
    extra = 0
    readonly_fields = ("inventory", "quantity", "status", "expires_at", "resolved_at")


class HistoryInline(admin.TabularInline):
    model = OrderStatusHistory
    extra = 0
    readonly_fields = ("from_status", "to_status", "note", "actor", "created_at")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "status",
        "customer_name",
        "phone",
        "district",
        "payment_method",
        "total",
        "created_at",
    )
    list_filter = ("status", "payment_method", "courier", "shipping_zone")
    search_fields = ("number", "customer_name", "phone", "email")
    readonly_fields = (
        "number",
        "subtotal",
        "discount",
        "shipping_fee",
        "shipping_discount",
        "vat_rate",
        "vat",
        "total",
        "paid_at",
    )
    inlines = (OrderItemInline, ReservationInline, HistoryInline)
    date_hierarchy = "created_at"


@admin.register(StockReservation)
class StockReservationAdmin(admin.ModelAdmin):
    list_display = ("order", "inventory", "quantity", "status", "expires_at", "resolved_at")
    list_filter = ("status",)
    search_fields = ("order__number", "inventory__variant__sku")
