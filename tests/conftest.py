from __future__ import annotations

from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.cart import services as cart_services
from apps.catalog.models import Category, Inventory, Product, ProductVariant
from apps.orders.models import PaymentMethod
from apps.orders.services import ShippingAddress, place_order
from apps.promotions.models import Coupon

User = get_user_model()


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


@pytest.fixture
def user(db):
    return User.objects.create_user("rahim", "rahim@example.com", "s3cret-pass-123")


@pytest.fixture
def other_user(db):
    return User.objects.create_user("karim", "karim@example.com", "s3cret-pass-456")


@pytest.fixture
def staff_user(db):
    return User.objects.create_user("ops", "ops@example.com", "ops-pass-789", is_staff=True)


@pytest.fixture
def auth_client(api_client, user) -> APIClient:
    api_client.force_authenticate(user=user)
    return api_client


@pytest.fixture
def category(db) -> Category:
    return Category.objects.create(name="Electronics", name_bn="ইলেকট্রনিক্স")


def make_product(category, name, base_price, *variants) -> Product:
    """variants: tuples of (sku, variant_name, price_override, weight_grams, stock)."""
    product = Product.objects.create(category=category, name=name, base_price=Decimal(base_price))
    for sku, vname, price, weight, stock in variants:
        variant = ProductVariant.objects.create(
            product=product,
            sku=sku,
            name=vname,
            price=Decimal(price) if price is not None else None,
            weight_grams=weight,
        )
        Inventory.objects.create(variant=variant, quantity=stock)
    return product


@pytest.fixture
def product(category) -> Product:
    return make_product(
        category,
        "Power Bank 10000 mAh",
        "1150.00",
        ("PB-BLK", "Black", None, 240, 10),
        ("PB-WHT", "White", "1250.00", 240, 2),
    )


@pytest.fixture
def variant(product) -> ProductVariant:
    return product.variants.get(sku="PB-BLK")


@pytest.fixture
def scarce_variant(product) -> ProductVariant:
    """Only 2 units in stock."""
    return product.variants.get(sku="PB-WHT")


@pytest.fixture
def heavy_product(category) -> Product:
    return make_product(
        category, "Ceiling Fan 56 inch", "3290.00", ("FAN-56", "56 inch", None, 6500, 5)
    )


@pytest.fixture
def dhaka_address() -> ShippingAddress:
    return ShippingAddress(
        customer_name="Rahim Uddin",
        phone="01711223344",
        email="rahim@example.com",
        address_line="House 12, Road 5, Dhanmondi",
        area="Dhanmondi",
        district="Dhaka",
        postcode="1205",
    )


@pytest.fixture
def chittagong_address() -> ShippingAddress:
    return ShippingAddress(
        customer_name="Karim Chowdhury",
        phone="01811223344",
        address_line="GEC Circle",
        area="Khulshi",
        district="Chattogram",
        postcode="4000",
    )


@pytest.fixture
def percent_coupon(db) -> Coupon:
    return Coupon.objects.create(
        code="EID10",
        type=Coupon.Type.PERCENT,
        value=Decimal("10"),
        min_order_amount=Decimal("1000"),
        max_discount=Decimal("500"),
    )


@pytest.fixture
def cart_with(user):
    """Factory: build a user cart with the given (variant, qty) pairs."""

    def _build(*lines):
        cart = cart_services.get_or_create_cart(user=user)
        for v, qty in lines:
            cart_services.add_item(cart, v.pk, qty)
        return cart

    return _build


@pytest.fixture
def place(user, dhaka_address):
    """Factory: place an order for the given lines with sane defaults."""

    def _place(
        *lines,
        address=dhaka_address,
        courier="pathao",
        payment_method=PaymentMethod.BKASH,
        coupon_code="",
        owner=user,
    ):
        cart = cart_services.get_or_create_cart(user=owner)
        for v, qty in lines:
            cart_services.add_item(cart, v.pk, qty)
        return place_order(
            cart=cart,
            address=address,
            courier=courier,
            payment_method=payment_method,
            coupon_code=coupon_code,
            user=owner,
        )

    return _place
