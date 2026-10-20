from django.urls import path

from .views import ShippingRatesView

urlpatterns = [
    path("rates/", ShippingRatesView.as_view(), name="shipping-rates"),
]
