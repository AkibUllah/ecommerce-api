from django.contrib import admin

from .models import Review


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = (
        "product",
        "user",
        "rating",
        "is_verified_purchase",
        "is_approved",
        "created_at",
    )
    list_filter = ("rating", "is_verified_purchase", "is_approved")
    search_fields = ("product__name", "user__username", "title", "body")
    list_editable = ("is_approved",)
