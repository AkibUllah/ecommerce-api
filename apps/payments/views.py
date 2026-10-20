from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.exceptions import NotFound
from apps.orders.models import Order

from . import services
from .serializers import CreateIntentSerializer, PaymentIntentSerializer


class CreatePaymentIntentView(APIView):
    """Start a payment for a pending order; returns the provider redirect URL."""

    permission_classes = (permissions.AllowAny,)

    @extend_schema(request=CreateIntentSerializer, responses={201: PaymentIntentSerializer})
    def post(self, request):
        serializer = CreateIntentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        qs = Order.objects.all()
        if request.user.is_authenticated and not request.user.is_staff:
            qs = qs.filter(user=request.user)
        elif not request.user.is_authenticated:
            qs = qs.filter(user__isnull=True)
        try:
            order = qs.get(number=data["order_number"])
        except Order.DoesNotExist:
            raise NotFound("Order not found.")
        intent = services.create_intent(order, data["provider"])
        return Response(PaymentIntentSerializer(intent).data, status=status.HTTP_201_CREATED)


@method_decorator(csrf_exempt, name="dispatch")
class ProviderWebhookView(APIView):
    """Inbound provider notifications. Authenticated by HMAC signature, not by user."""

    permission_classes = (permissions.AllowAny,)
    authentication_classes = ()
    throttle_classes = ()

    @extend_schema(request=None, responses={200: OpenApiResponse(description="Processed")})
    def post(self, request, provider: str):
        event = services.handle_webhook(provider, body=request.body, headers=request.headers)
        return Response(
            {"received": True, "event_id": event.event_id, "processed": event.processed}
        )
