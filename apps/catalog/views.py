from django.db.models import Prefetch
from rest_framework import permissions, viewsets

from .filters import ProductFilter
from .models import Category, Product, ProductVariant
from .serializers import CategorySerializer, ProductDetailSerializer, ProductListSerializer


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Category.objects.filter(is_active=True)
    serializer_class = CategorySerializer
    permission_classes = (permissions.AllowAny,)
    lookup_field = "slug"
    pagination_class = None


class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = (permissions.AllowAny,)
    lookup_field = "slug"
    filterset_class = ProductFilter
    search_fields = ("name", "name_bn", "description", "variants__sku")
    ordering_fields = ("base_price", "created_at", "name")
    ordering = ("-created_at",)

    def get_queryset(self):
        return (
            Product.objects.filter(is_active=True)
            .select_related("category")
            .prefetch_related(
                "images",
                Prefetch(
                    "variants",
                    queryset=ProductVariant.objects.select_related("inventory", "product"),
                ),
            )
        )

    def get_serializer_class(self):
        return ProductDetailSerializer if self.action == "retrieve" else ProductListSerializer
