from rest_framework import serializers

from .models import PaymentIntent
from .registry import available_providers


class CreateIntentSerializer(serializers.Serializer):
    order_number = serializers.CharField(max_length=24)
    provider = serializers.ChoiceField(choices=[(p, p) for p in available_providers()])


class PaymentIntentSerializer(serializers.ModelSerializer):
    order_number = serializers.CharField(source="order.number", read_only=True)

    class Meta:
        model = PaymentIntent
        fields = (
            "id",
            "order_number",
            "provider",
            "amount",
            "currency",
            "status",
            "provider_ref",
            "redirect_url",
            "failure_reason",
            "created_at",
        )
        read_only_fields = fields
