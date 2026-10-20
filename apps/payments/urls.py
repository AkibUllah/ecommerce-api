from django.urls import path

from .views import CreatePaymentIntentView, ProviderWebhookView

urlpatterns = [
    path("intents/", CreatePaymentIntentView.as_view(), name="payment-intent-create"),
    path("webhooks/<slug:provider>/", ProviderWebhookView.as_view(), name="payment-webhook"),
]
