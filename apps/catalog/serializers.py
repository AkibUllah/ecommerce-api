from rest_framework import serializers

from .models import Category, Inventory, Product, ProductImage, ProductVariant


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ("id", "name", "name_bn", "slug", "parent", "is_active")


class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ("id", "url", "alt_text", "sort_order")


class InventorySerializer(serializers.ModelSerializer):
    available = serializers.IntegerField(read_only=True)
    is_low = serializers.BooleanField(read_only=True)

    class Meta:
        model = Inventory
        fields = ("quantity", "reserved", "available", "is_low")


class ProductVariantSerializer(serializers.ModelSerializer):
    price = serializers.DecimalField(
        source="effective_price", max_digits=12, decimal_places=2, read_only=True
    )
    inventory = InventorySerializer(read_only=True)

    class Meta:
        model = ProductVariant
        fields = (
            "id",
            "sku",
            "name",
            "attributes",
            "price",
            "weight_grams",
            "is_active",
            "inventory",
        )


class ProductListSerializer(serializers.ModelSerializer):
    category = serializers.SlugRelatedField(slug_field="slug", read_only=True)
    price_from = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    thumbnail = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = (
            "id",
            "name",
            "name_bn",
            "slug",
            "category",
            "base_price",
            "price_from",
            "thumbnail",
            "is_active",
        )

    def get_thumbnail(self, obj: Product) -> str | None:
        images = list(obj.images.all())
        return images[0].url if images else None


class ProductDetailSerializer(ProductListSerializer):
    variants = ProductVariantSerializer(many=True, read_only=True)
    images = ProductImageSerializer(many=True, read_only=True)
    rating = serializers.SerializerMethodField()

    class Meta(ProductListSerializer.Meta):
        fields = ProductListSerializer.Meta.fields + (
            "description",
            "variants",
            "images",
            "rating",
            "created_at",
        )

    def get_rating(self, obj: Product) -> dict:
        from apps.reviews.services import rating_summary

        return rating_summary(obj)
