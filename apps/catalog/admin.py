from django.contrib import admin

from .models import Category, Inventory, Product, ProductImage, ProductVariant


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 0


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 0


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "name_bn", "slug", "parent", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "name_bn", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "base_price", "is_active", "updated_at")
    list_filter = ("is_active", "category")
    search_fields = ("name", "name_bn", "slug", "variants__sku")
    prepopulated_fields = {"slug": ("name",)}
    inlines = (ProductVariantInline, ProductImageInline)


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = ("sku", "product", "name", "price", "weight_grams", "is_active")
    search_fields = ("sku", "product__name")


@admin.register(Inventory)
class InventoryAdmin(admin.ModelAdmin):
    list_display = ("variant", "quantity", "reserved", "available", "is_low", "updated_at")
    search_fields = ("variant__sku",)
    readonly_fields = ("reserved",)

    @admin.display(boolean=True)
    def is_low(self, obj):
        return obj.is_low
