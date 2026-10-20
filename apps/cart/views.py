from django.conf import settings
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .models import Cart
from .serializers import AddItemSerializer, CartSerializer, MergeSerializer, UpdateItemSerializer

TOKEN_PARAM = OpenApiParameter(
    name=settings.CART_TOKEN_HEADER,
    location=OpenApiParameter.HEADER,
    required=False,
    description="Guest cart token (returned on the first cart response).",
)


def _resolve_cart(request) -> Cart:
    token = request.headers.get(settings.CART_TOKEN_HEADER)
    return services.get_or_create_cart(user=request.user, token=token)


def _cart_response(cart: Cart, status_code: int = status.HTTP_200_OK) -> Response:
    cart = Cart.objects.prefetch_related("items__variant__product").get(pk=cart.pk)
    response = Response(CartSerializer(cart).data, status=status_code)
    response[settings.CART_TOKEN_HEADER] = str(cart.token)
    return response


class CartView(APIView):
    permission_classes = (permissions.AllowAny,)

    @extend_schema(parameters=[TOKEN_PARAM], responses=CartSerializer)
    def get(self, request):
        return _cart_response(_resolve_cart(request))

    @extend_schema(parameters=[TOKEN_PARAM], responses=CartSerializer)
    def delete(self, request):
        cart = _resolve_cart(request)
        services.clear(cart)
        return _cart_response(cart)


class CartItemsView(APIView):
    permission_classes = (permissions.AllowAny,)

    @extend_schema(parameters=[TOKEN_PARAM], request=AddItemSerializer, responses=CartSerializer)
    def post(self, request):
        serializer = AddItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        cart = _resolve_cart(request)
        services.add_item(cart, **serializer.validated_data)
        return _cart_response(cart, status.HTTP_201_CREATED)


class CartItemDetailView(APIView):
    permission_classes = (permissions.AllowAny,)

    @extend_schema(parameters=[TOKEN_PARAM], request=UpdateItemSerializer, responses=CartSerializer)
    def patch(self, request, item_id: int):
        serializer = UpdateItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        cart = _resolve_cart(request)
        services.set_quantity(cart, item_id, serializer.validated_data["quantity"])
        return _cart_response(cart)

    @extend_schema(parameters=[TOKEN_PARAM], responses=CartSerializer)
    def delete(self, request, item_id: int):
        cart = _resolve_cart(request)
        services.remove_item(cart, item_id)
        return _cart_response(cart)


class CartMergeView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    @extend_schema(request=MergeSerializer, responses=CartSerializer)
    def post(self, request):
        serializer = MergeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        cart = services.merge_guest_cart(
            request.user, str(serializer.validated_data["guest_token"])
        )
        return _cart_response(cart)
