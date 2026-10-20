from django.conf import settings
from django.db.models import Prefetch
from drf_spectacular.utils import extend_schema
from rest_framework import permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from apps.cart import services as cart_services
from apps.core.exceptions import NotFound
from apps.core.permissions import IsStaff

from . import services
from .models import Order, OrderItem
from .serializers import (
    CheckoutSerializer,
    OrderListSerializer,
    OrderSerializer,
    StatusUpdateSerializer,
)


class OrderViewSet(GenericViewSet):
    """Checkout, order history and status management.

    * ``POST /orders/`` places an order from the caller's cart (guest or user).
    * ``GET /orders/`` lists the authenticated user's orders.
    * ``GET /orders/{number}/`` is readable by the owner, staff, or by the guest who
      placed it (matched on phone passed as ``?phone=``).
    """

    lookup_field = "number"
    serializer_class = OrderSerializer
    permission_classes = (permissions.AllowAny,)
    filterset_fields = ("status", "payment_method")
    ordering_fields = ("created_at", "total")

    def get_queryset(self):
        qs = Order.objects.prefetch_related(
            Prefetch("items", queryset=OrderItem.objects.order_by("id")), "history"
        )
        user = self.request.user
        if user.is_authenticated and user.is_staff and self.action != "list":
            return qs
        if user.is_authenticated:
            return qs.filter(user=user)
        phone = self.request.query_params.get("phone")
        return qs.filter(user__isnull=True, phone=phone) if phone else qs.none()

    def _get_order(self) -> Order:
        try:
            return self.get_queryset().get(number=self.kwargs["number"])
        except Order.DoesNotExist:
            raise NotFound("Order not found.")

    @extend_schema(responses=OrderListSerializer(many=True))
    def list(self, request):
        if not request.user.is_authenticated:
            return Response(
                {"error": {"code": "not_authenticated", "message": "Login to see your orders."}},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        page = self.paginate_queryset(self.filter_queryset(self.get_queryset()))
        return self.get_paginated_response(OrderListSerializer(page, many=True).data)

    def retrieve(self, request, number=None):
        return Response(OrderSerializer(self._get_order()).data)

    @extend_schema(request=CheckoutSerializer, responses={201: OrderSerializer})
    def create(self, request):
        serializer = CheckoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        token = data.pop("guest_token", None) or request.headers.get(settings.CART_TOKEN_HEADER)
        cart = cart_services.get_or_create_cart(
            user=request.user, token=str(token) if token else None
        )

        address = services.ShippingAddress(
            customer_name=data["customer_name"],
            phone=data["phone"],
            email=data["email"],
            address_line=data["address_line"],
            area=data["area"],
            district=data["district"],
            postcode=data["postcode"],
        )
        order = services.place_order(
            cart=cart,
            address=address,
            courier=data["courier"],
            payment_method=data["payment_method"],
            coupon_code=data["coupon_code"],
            user=request.user,
            notes=data["notes"],
        )
        order = Order.objects.prefetch_related("items", "history").get(pk=order.pk)
        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=None, responses=OrderSerializer)
    @action(detail=True, methods=["post"])
    def cancel(self, request, number=None):
        order = services.cancel_order(
            self._get_order(), reason="Cancelled by customer", actor=request.user
        )
        return Response(OrderSerializer(order).data)

    @extend_schema(request=StatusUpdateSerializer, responses=OrderSerializer)
    @action(detail=True, methods=["post"], url_path="status", permission_classes=(IsStaff,))
    def set_status(self, request, number=None):
        serializer = StatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = services.advance_status(
            self._get_order(),
            serializer.validated_data["status"],
            note=serializer.validated_data["note"],
            actor=request.user,
        )
        return Response(OrderSerializer(order).data)
