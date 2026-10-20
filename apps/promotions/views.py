from drf_spectacular.utils import extend_schema
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import DiscountSerializer, ValidateCouponSerializer
from .services import apply_coupon


class ValidateCouponView(APIView):
    """Dry-run a coupon against a subtotal so the storefront can show the discount."""

    permission_classes = (permissions.AllowAny,)

    @extend_schema(request=ValidateCouponSerializer, responses=DiscountSerializer)
    def post(self, request):
        serializer = ValidateCouponSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        result = apply_coupon(
            data["code"],
            subtotal=data["subtotal"],
            shipping_fee=data["shipping_fee"],
            user=request.user,
        )
        return Response(DiscountSerializer(result).data)
