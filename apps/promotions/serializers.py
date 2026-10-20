from rest_framework import serializers

from .models import Coupon


class CouponSerializer(serializers.ModelSerializer):
    class Meta:
        model = Coupon
        fields = (
            "code",
            "description",
            "type",
            "value",
            "min_order_amount",
            "max_discount",
            "expires_at",
        )


class ValidateCouponSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=40)
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2)
    shipping_fee = serializers.DecimalField(max_digits=12, decimal_places=2, default=0)


class DiscountSerializer(serializers.Serializer):
    coupon = CouponSerializer()
    discount = serializers.DecimalField(max_digits=12, decimal_places=2)
    shipping_discount = serializers.DecimalField(max_digits=12, decimal_places=2)
    total = serializers.DecimalField(max_digits=12, decimal_places=2)
