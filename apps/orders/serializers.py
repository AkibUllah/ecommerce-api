from django.conf import settings
from rest_framework import serializers

from apps.shipping.rates import CALCULATORS

from .models import Order, OrderItem, OrderStatus, OrderStatusHistory, PaymentMethod


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = (
            "id",
            "variant",
            "product_name",
            "variant_name",
            "sku",
            "unit_price",
            "quantity",
            "line_total",
        )


class OrderStatusHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderStatusHistory
        fields = ("from_status", "to_status", "note", "created_at")


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    history = OrderStatusHistorySerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = (
            "number",
            "status",
            "customer_name",
            "email",
            "phone",
            "address_line",
            "area",
            "district",
            "postcode",
            "notes",
            "shipping_zone",
            "courier",
            "shipping_fee",
            "shipping_discount",
            "currency",
            "subtotal",
            "discount",
            "vat_rate",
            "vat",
            "total",
            "coupon_code",
            "payment_method",
            "paid_at",
            "reservation_expires_at",
            "items",
            "history",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class OrderListSerializer(serializers.ModelSerializer):
    item_count = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = (
            "number",
            "status",
            "total",
            "currency",
            "payment_method",
            "courier",
            "item_count",
            "created_at",
        )

    def get_item_count(self, obj: Order) -> int:
        return sum(item.quantity for item in obj.items.all())


class CheckoutSerializer(serializers.Serializer):
    customer_name = serializers.CharField(max_length=120)
    phone = serializers.RegexField(
        regex=r"^(\+8801|01)[3-9]\d{8}$",
        error_messages={"invalid": "Enter a valid Bangladeshi mobile number (e.g. 017XXXXXXXX)."},
    )
    email = serializers.EmailField(required=False, allow_blank=True, default="")
    address_line = serializers.CharField(max_length=255)
    area = serializers.CharField(max_length=120, required=False, allow_blank=True, default="")
    district = serializers.CharField(max_length=80)
    postcode = serializers.CharField(max_length=10, required=False, allow_blank=True, default="")
    courier = serializers.ChoiceField(choices=sorted(CALCULATORS))
    payment_method = serializers.ChoiceField(choices=PaymentMethod.choices)
    coupon_code = serializers.CharField(max_length=40, required=False, allow_blank=True, default="")
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    guest_token = serializers.UUIDField(
        required=False,
        help_text=f"Guest cart token; alternatively send the {settings.CART_TOKEN_HEADER} header.",
    )


class StatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=OrderStatus.choices)
    note = serializers.CharField(required=False, allow_blank=True, default="")
