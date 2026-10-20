from decimal import Decimal

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.cart import services as cart_services
from apps.core.exceptions import DomainError, InsufficientStock, InvalidTransition
from apps.orders import services
from apps.orders.models import Order, OrderStatus, PaymentMethod, StockReservation
from apps.orders.services import price_order
from apps.promotions.models import Coupon

pytestmark = pytest.mark.django_db


# --- pure pricing -----------------------------------------------------------
def test_price_order_applies_vat_on_discounted_goods_only():
    b = price_order(
        subtotal=Decimal("2000"),
        shipping_fee=Decimal("60"),
        discount=Decimal("200"),
        vat_rate=Decimal("0.05"),
    )
    assert b.vat == Decimal("90.00")  # 5% of 1800, not of shipping
    assert b.total == Decimal("1950.00")  # 1800 + 90 + 60


def test_price_order_clamps_discounts():
    b = price_order(
        subtotal=Decimal("100"),
        shipping_fee=Decimal("60"),
        discount=Decimal("500"),
        shipping_discount=Decimal("999"),
        vat_rate=Decimal("0.15"),
    )
    assert (b.discount, b.shipping_discount, b.vat, b.total) == (
        Decimal("100.00"),
        Decimal("60.00"),
        Decimal("0.00"),
        Decimal("0.00"),
    )


def test_price_order_rounds_half_up():
    b = price_order(subtotal=Decimal("333.33"), shipping_fee=Decimal("0"), vat_rate=Decimal("0.05"))
    assert b.vat == Decimal("16.67")
    assert b.total == Decimal("350.00")


# --- checkout ---------------------------------------------------------------
def test_checkout_totals_with_shipping_and_vat(place, variant, heavy_product, settings):
    settings.VAT_RATE = Decimal("0.05")
    fan = heavy_product.variants.get()
    order = place((variant, 2), (fan, 1))  # 2300 + 3290 = 5590; weight 480 + 6500 = 6980 g
    assert order.subtotal == Decimal("5590.00")
    assert order.shipping_zone == "inside_dhaka"
    assert order.shipping_fee == Decimal("150.00")  # Pathao inside Dhaka: 60 + 6 extra kg * 15
    assert order.vat == Decimal("279.50")
    assert order.total == Decimal("6019.50")
    assert order.status == OrderStatus.PENDING
    assert order.items.count() == 2
    assert order.reservation_expires_at > timezone.now()


def test_checkout_outside_dhaka_cod_adds_cod_fee_and_confirms(place, variant, chittagong_address):
    order = place(
        (variant, 1), address=chittagong_address, courier="redx", payment_method=PaymentMethod.COD
    )
    # RedX outside: 130 + 1% COD fee on 1150 = 11.50
    assert order.shipping_fee == Decimal("141.50")
    assert order.status == OrderStatus.CONFIRMED
    assert order.paid_at is not None
    inv = variant.inventory
    inv.refresh_from_db()
    assert (inv.quantity, inv.reserved) == (9, 0)
    assert order.reservations.get().status == StockReservation.Status.COMMITTED


def test_checkout_with_percent_coupon_and_free_shipping(place, variant, percent_coupon):
    order = place((variant, 2), coupon_code="eid10")
    assert order.coupon_code == "EID10"
    assert order.discount == Decimal("230.00")
    assert order.vat == Decimal("103.50")  # 5% of 2070
    assert order.total == Decimal("2233.50")  # 2070 + 103.5 + 60

    Coupon.objects.create(code="FREESHIP", type=Coupon.Type.FREE_SHIPPING)
    free = place((variant, 1), coupon_code="FREESHIP")
    assert free.shipping_fee == Decimal("60.00")
    assert free.shipping_discount == Decimal("60.00")
    assert free.total == Decimal("1207.50")  # 1150 + 57.50 VAT


def test_checkout_reserves_stock_and_clears_cart(place, user, variant):
    order = place((variant, 3))
    inv = variant.inventory
    inv.refresh_from_db()
    assert (inv.quantity, inv.reserved, inv.available) == (10, 3, 7)
    assert order.reservations.filter(status=StockReservation.Status.ACTIVE).count() == 1
    assert cart_services.get_or_create_cart(user=user).items.count() == 0


def test_checkout_empty_cart_rejected(user, dhaka_address):
    cart = cart_services.get_or_create_cart(user=user)
    with pytest.raises(DomainError, match="empty"):
        services.place_order(
            cart=cart,
            address=dhaka_address,
            courier="pathao",
            payment_method=PaymentMethod.BKASH,
            user=user,
        )


def test_sequential_race_for_last_units(place, scarce_variant, user, other_user, variant):
    """Two carts both hold the last 2 units; the second checkout must fail and roll back."""
    cart_a = cart_services.get_or_create_cart(user=user)
    cart_services.add_item(cart_a, scarce_variant.pk, 2)
    cart_b = cart_services.get_or_create_cart(user=other_user)
    cart_services.add_item(cart_b, scarce_variant.pk, 2)
    cart_services.add_item(cart_b, variant.pk, 1)

    first = place(owner=user)  # cart_a already filled
    assert first.status == OrderStatus.PENDING

    before = Order.objects.count()
    with pytest.raises(InsufficientStock):
        place(owner=other_user)
    assert Order.objects.count() == before  # nothing half-written
    variant.inventory.refresh_from_db()
    assert variant.inventory.reserved == 0  # the other line of cart_b was rolled back too
    assert cart_b.items.count() == 2  # cart untouched on failure


def test_cancel_pending_order_releases_reservation(place, variant, percent_coupon):
    order = place((variant, 2), coupon_code="EID10")
    services.cancel_order(order, reason="changed my mind")
    order.refresh_from_db()
    assert order.status == OrderStatus.CANCELLED
    variant.inventory.refresh_from_db()
    assert variant.inventory.reserved == 0
    assert order.reservations.get().status == StockReservation.Status.RELEASED
    percent_coupon.refresh_from_db()
    assert percent_coupon.used_count == 0
    assert [h.to_status for h in order.history.all()] == ["pending", "cancelled"]


def test_cancel_confirmed_order_restocks(place, variant):
    order = place((variant, 4), payment_method=PaymentMethod.COD)
    variant.inventory.refresh_from_db()
    assert variant.inventory.quantity == 6
    services.cancel_order(order)
    variant.inventory.refresh_from_db()
    assert (variant.inventory.quantity, variant.inventory.reserved) == (10, 0)


def test_state_machine_rejects_invalid_transitions(place, variant):
    order = place((variant, 1))
    with pytest.raises(InvalidTransition):
        order.transition(OrderStatus.SHIPPED)
    with pytest.raises(InvalidTransition):
        order.transition(OrderStatus.DELIVERED)
    services.mark_paid(order)
    order.refresh_from_db()
    assert order.status == OrderStatus.CONFIRMED
    order.transition(OrderStatus.PROCESSING)
    order.transition(OrderStatus.SHIPPED)
    with pytest.raises(InvalidTransition):
        services.cancel_order(order)  # shipped orders can only be delivered or refunded
    order.transition(OrderStatus.DELIVERED)
    with pytest.raises(InvalidTransition):
        order.transition(OrderStatus.PENDING)


def test_mark_paid_is_idempotent(place, variant):
    order = place((variant, 1))
    services.mark_paid(order)
    services.mark_paid(order)
    variant.inventory.refresh_from_db()
    assert (variant.inventory.quantity, variant.inventory.reserved) == (9, 0)
    assert order.history.filter(to_status=OrderStatus.CONFIRMED).count() == 1


def test_release_expired_reservations_command(place, variant, percent_coupon):
    expired = place((variant, 2), coupon_code="EID10")
    fresh = place((variant, 1))
    Order.objects.filter(pk=expired.pk).update(
        reservation_expires_at=timezone.now() - timezone.timedelta(minutes=1)
    )
    call_command("release_expired_reservations")

    expired.refresh_from_db()
    fresh.refresh_from_db()
    assert expired.status == OrderStatus.EXPIRED
    assert fresh.status == OrderStatus.PENDING
    variant.inventory.refresh_from_db()
    assert variant.inventory.reserved == 1
    percent_coupon.refresh_from_db()
    assert percent_coupon.used_count == 0


# --- API --------------------------------------------------------------------
CHECKOUT = {
    "customer_name": "Rahim Uddin",
    "phone": "01711223344",
    "address_line": "House 12, Road 5",
    "area": "Dhanmondi",
    "district": "Dhaka",
    "postcode": "1205",
    "courier": "pathao",
    "payment_method": "bkash",
}


def test_checkout_endpoint_for_authenticated_user(auth_client, variant):
    auth_client.post("/api/v1/cart/items/", {"variant_id": variant.pk, "quantity": 1})
    response = auth_client.post("/api/v1/orders/", CHECKOUT)
    assert response.status_code == 201, response.json()
    body = response.json()
    assert body["status"] == "pending"
    assert body["total"] == "1267.50"  # 1150 + 57.50 VAT + 60 shipping
    assert body["items"][0]["sku"] == "PB-BLK"

    listing = auth_client.get("/api/v1/orders/").json()
    assert listing["count"] == 1
    detail = auth_client.get(f"/api/v1/orders/{body['number']}/").json()
    assert detail["number"] == body["number"]

    cancelled = auth_client.post(f"/api/v1/orders/{body['number']}/cancel/").json()
    assert cancelled["status"] == "cancelled"


def test_guest_checkout_with_cart_token(api_client, variant):
    token = api_client.post("/api/v1/cart/items/", {"variant_id": variant.pk, "quantity": 2})[
        "X-Cart-Token"
    ]
    response = api_client.post("/api/v1/orders/", {**CHECKOUT, "guest_token": token})
    assert response.status_code == 201, response.json()
    number = response.json()["number"]
    # Guests can look up their order by number + phone, nobody else can
    assert api_client.get(f"/api/v1/orders/{number}/?phone=01711223344").status_code == 200
    assert api_client.get(f"/api/v1/orders/{number}/").status_code == 404


def test_checkout_endpoint_validates_phone_and_courier(auth_client, variant):
    auth_client.post("/api/v1/cart/items/", {"variant_id": variant.pk, "quantity": 1})
    response = auth_client.post("/api/v1/orders/", {**CHECKOUT, "phone": "12345", "courier": "dhl"})
    assert response.status_code == 400
    details = response.json()["error"]["details"]
    assert "phone" in details and "courier" in details


def test_users_cannot_see_each_others_orders(place, variant, api_client, other_user):
    order = place((variant, 1))
    api_client.force_authenticate(user=other_user)
    assert api_client.get(f"/api/v1/orders/{order.number}/").status_code == 404


def test_staff_status_endpoint(place, variant, api_client, staff_user, user):
    order = place((variant, 1), payment_method=PaymentMethod.COD)
    api_client.force_authenticate(user=user)
    assert (
        api_client.post(
            f"/api/v1/orders/{order.number}/status/", {"status": "processing"}
        ).status_code
        == 403
    )
    api_client.force_authenticate(user=staff_user)
    body = api_client.post(
        f"/api/v1/orders/{order.number}/status/", {"status": "processing", "note": "Packed"}
    ).json()
    assert body["status"] == "processing"
    bad = api_client.post(f"/api/v1/orders/{order.number}/status/", {"status": "delivered"})
    assert bad.status_code == 409
    assert bad.json()["error"]["code"] == "invalid_transition"
