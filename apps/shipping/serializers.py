from rest_framework import serializers


class RateQuerySerializer(serializers.Serializer):
    district = serializers.CharField(max_length=80)
    weight_grams = serializers.IntegerField(min_value=1, default=500)
    cod_amount = serializers.DecimalField(max_digits=12, decimal_places=2, default=0)


class ShippingQuoteSerializer(serializers.Serializer):
    courier = serializers.CharField()
    zone = serializers.CharField()
    fee = serializers.DecimalField(max_digits=12, decimal_places=2)
    cod_fee = serializers.DecimalField(max_digits=12, decimal_places=2)
    total = serializers.DecimalField(max_digits=12, decimal_places=2)
    eta_days = serializers.IntegerField()
