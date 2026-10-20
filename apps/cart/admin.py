from django.contrib import admin

from .models import Cart, CartItem


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ("__str__", "user", "token", "total_items", "subtotal", "updated_at")
    search_fields = ("user__username", "user__email", "token")
    inlines = (CartItemInline,)
