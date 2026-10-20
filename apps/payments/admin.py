from django.contrib import admin

from .models import PaymentIntent, WebhookEvent


@admin.register(PaymentIntent)
class PaymentIntentAdmin(admin.ModelAdmin):
    list_display = ("id", "order", "provider", "amount", "status", "provider_ref", "created_at")
    list_filter = ("provider", "status")
    search_fields = ("order__number", "provider_ref")
    readonly_fields = ("raw_response",)


@admin.register(WebhookEvent)
class WebhookEventAdmin(admin.ModelAdmin):
    list_display = ("provider", "event_id", "intent", "signature_valid", "processed", "received_at")
    list_filter = ("provider", "processed", "signature_valid")
    search_fields = ("event_id",)
    readonly_fields = ("payload",)
