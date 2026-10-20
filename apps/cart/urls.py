from django.urls import path

from .views import CartItemDetailView, CartItemsView, CartMergeView, CartView

urlpatterns = [
    path("", CartView.as_view(), name="cart"),
    path("items/", CartItemsView.as_view(), name="cart-items"),
    path("items/<int:item_id>/", CartItemDetailView.as_view(), name="cart-item-detail"),
    path("merge/", CartMergeView.as_view(), name="cart-merge"),
]
