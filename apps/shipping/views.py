from drf_spectacular.utils import extend_schema
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from .rates import quote_all
from .serializers import RateQuerySerializer, ShippingQuoteSerializer
from .zones import zone_for_district


class ShippingRatesView(APIView):
    permission_classes = (permissions.AllowAny,)

    @extend_schema(parameters=[RateQuerySerializer], responses=ShippingQuoteSerializer(many=True))
    def get(self, request):
        query = RateQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        data = query.validated_data
        zone = zone_for_district(data["district"])
        quotes = quote_all(zone, data["weight_grams"], data["cod_amount"])
        return Response(
            {"zone": zone.value, "quotes": ShippingQuoteSerializer(quotes, many=True).data}
        )
