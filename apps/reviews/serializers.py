from rest_framework import serializers

from .models import Review


class ReviewSerializer(serializers.ModelSerializer):
    author = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = Review
        fields = (
            "id",
            "product",
            "author",
            "rating",
            "title",
            "body",
            "is_verified_purchase",
            "created_at",
        )
        read_only_fields = ("id", "author", "is_verified_purchase", "created_at")

    def validate(self, attrs):
        request = self.context["request"]
        if (
            self.instance is None
            and Review.objects.filter(product=attrs["product"], user=request.user).exists()
        ):
            raise serializers.ValidationError("You have already reviewed this product.")
        return attrs
