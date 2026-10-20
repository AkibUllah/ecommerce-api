import django_filters

from .models import Product


class ProductFilter(django_filters.FilterSet):
    category = django_filters.CharFilter(field_name="category__slug")
    min_price = django_filters.NumberFilter(field_name="base_price", lookup_expr="gte")
    max_price = django_filters.NumberFilter(field_name="base_price", lookup_expr="lte")
    in_stock = django_filters.BooleanFilter(method="filter_in_stock")

    class Meta:
        model = Product
        fields = ("category", "min_price", "max_price", "in_stock")

    def filter_in_stock(self, queryset, name, value):
        from django.db.models import F

        qs = queryset.filter(
            variants__inventory__quantity__gt=F("variants__inventory__reserved")
        ).distinct()
        return qs if value else queryset.exclude(pk__in=qs.values("pk"))
