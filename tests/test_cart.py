import pytest

from apps.cart import services
from apps.cart.models import Cart
from apps.core.exceptions import InsufficientStock

pytestmark = pytest.mark.django_db

CART_URL = "/api/v1/cart/"


def test_guest_cart_is_created_and_token_returned(api_client):
    response = api_client.get(CART_URL)
    assert response.status_code == 200
    token = response["X-Cart-Token"]
    assert response.json()["token"] == token
    # The same token resolves to the same cart
    again = api_client.get(CART_URL, HTTP_X_CART_TOKEN=token)
    assert again.json()["token"] == token
    assert Cart.objects.count() == 1


def test_guest_add_update_remove_items(api_client, variant):
    response = api_client.post(f"{CART_URL}items/", {"variant_id": variant.pk, "quantity": 2})
    assert response.status_code == 201
    token = response["X-Cart-Token"]
    body = response.json()
    assert body["total_items"] == 2
    assert body["subtotal"] == "2300.00"
    item_id = body["items"][0]["id"]

    # Adding the same variant again increments quantity
    body = api_client.post(
        f"{CART_URL}items/", {"variant_id": variant.pk, "quantity": 1}, HTTP_X_CART_TOKEN=token
    ).json()
    assert body["items"][0]["quantity"] == 3

    body = api_client.patch(
        f"{CART_URL}items/{item_id}/", {"quantity": 5}, HTTP_X_CART_TOKEN=token
    ).json()
    assert body["items"][0]["quantity"] == 5
    assert body["subtotal"] == "5750.00"

    body = api_client.delete(f"{CART_URL}items/{item_id}/", HTTP_X_CART_TOKEN=token).json()
    assert body["items"] == []


def test_add_item_beyond_stock_rejected(api_client, scarce_variant):
    response = api_client.post(
        f"{CART_URL}items/", {"variant_id": scarce_variant.pk, "quantity": 3}
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "insufficient_stock"


def test_add_unknown_variant_404(api_client):
    response = api_client.post(f"{CART_URL}items/", {"variant_id": 9999, "quantity": 1})
    assert response.status_code == 404


def test_user_cart_is_bound_to_user(auth_client, user, variant):
    auth_client.post(f"{CART_URL}items/", {"variant_id": variant.pk, "quantity": 1})
    cart = Cart.objects.get(user=user)
    assert cart.total_items == 1
    # A second request without a token still finds the same cart
    assert auth_client.get(CART_URL).json()["token"] == str(cart.token)


def test_merge_guest_cart_sums_quantities_and_deletes_guest(user, variant, scarce_variant):
    guest = services.get_or_create_cart()
    services.add_item(guest, variant.pk, 2)
    services.add_item(guest, scarce_variant.pk, 1)
    user_cart = services.get_or_create_cart(user=user)
    services.add_item(user_cart, variant.pk, 3)

    merged = services.merge_guest_cart(user, str(guest.token))

    assert merged.pk == user_cart.pk
    quantities = {i.variant.sku: i.quantity for i in merged.items.all()}
    assert quantities == {"PB-BLK": 5, "PB-WHT": 1}
    assert not Cart.objects.filter(pk=guest.pk).exists()


def test_merge_caps_quantity_at_available_stock(user, scarce_variant):
    guest = services.get_or_create_cart()
    services.add_item(guest, scarce_variant.pk, 2)
    user_cart = services.get_or_create_cart(user=user)
    services.add_item(user_cart, scarce_variant.pk, 2)

    merged = services.merge_guest_cart(user, str(guest.token))
    assert merged.items.get(variant=scarce_variant).quantity == 2


def test_merge_endpoint_requires_auth_and_works(api_client, user, variant):
    guest_token = api_client.post(f"{CART_URL}items/", {"variant_id": variant.pk, "quantity": 2})[
        "X-Cart-Token"
    ]
    assert api_client.post(f"{CART_URL}merge/", {"guest_token": guest_token}).status_code == 401

    api_client.force_authenticate(user=user)
    body = api_client.post(f"{CART_URL}merge/", {"guest_token": guest_token}).json()
    assert body["total_items"] == 2
    assert body["token"] != guest_token


def test_set_quantity_to_zero_removes_item(user, variant):
    cart = services.get_or_create_cart(user=user)
    item = services.add_item(cart, variant.pk, 1)
    assert services.set_quantity(cart, item.pk, 0) is None
    assert cart.items.count() == 0


def test_set_quantity_beyond_stock(user, scarce_variant):
    cart = services.get_or_create_cart(user=user)
    item = services.add_item(cart, scarce_variant.pk, 1)
    with pytest.raises(InsufficientStock):
        services.set_quantity(cart, item.pk, 5)
