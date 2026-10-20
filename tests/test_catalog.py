import pytest

from apps.catalog import services as inventory
from apps.core.exceptions import InsufficientStock
from tests.conftest import make_product

pytestmark = pytest.mark.django_db


def test_health_endpoint(api_client):
    response = api_client.get("/health/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": True}


def test_product_list_and_detail(api_client, product):
    response = api_client.get("/api/v1/catalog/products/")
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["results"][0]["slug"] == product.slug
    assert body["results"][0]["price_from"] == "1150.00"

    detail = api_client.get(f"/api/v1/catalog/products/{product.slug}/").json()
    assert {v["sku"] for v in detail["variants"]} == {"PB-BLK", "PB-WHT"}
    white = next(v for v in detail["variants"] if v["sku"] == "PB-WHT")
    assert white["price"] == "1250.00"
    assert white["inventory"]["available"] == 2
    assert detail["rating"] == {"average": None, "count": 0}


def test_product_filter_search_and_ordering(api_client, category, product):
    other = make_product(
        category, "Bluetooth Earbuds", "1890.00", ("TWS-01", "Default", None, 120, 5)
    )
    make_product(category, "Out Of Stock Lamp", "500.00", ("LAMP-01", "Default", None, 800, 0))

    assert api_client.get("/api/v1/catalog/products/?search=earbuds").json()["count"] == 1
    assert (
        api_client.get("/api/v1/catalog/products/?search=TWS-01").json()["results"][0]["slug"]
        == other.slug
    )
    assert api_client.get("/api/v1/catalog/products/?min_price=1500").json()["count"] == 1
    assert api_client.get("/api/v1/catalog/products/?in_stock=true").json()["count"] == 2
    assert (
        api_client.get("/api/v1/catalog/products/?in_stock=false").json()["results"][0]["slug"]
        == "out-of-stock-lamp"
    )
    ordered = api_client.get("/api/v1/catalog/products/?ordering=base_price").json()["results"]
    assert [p["base_price"] for p in ordered] == ["500.00", "1150.00", "1890.00"]


def test_inactive_products_hidden(api_client, product):
    product.is_active = False
    product.save()
    assert api_client.get("/api/v1/catalog/products/").json()["count"] == 0
    assert api_client.get(f"/api/v1/catalog/products/{product.slug}/").status_code == 404


def test_inventory_reserve_release_commit(variant):
    inv = variant.inventory
    inventory.reserve(inv, 4)
    assert (inv.quantity, inv.reserved, inv.available) == (10, 4, 6)
    inventory.release(inv, 1)
    assert inv.reserved == 3
    inventory.commit(inv, 3)
    assert (inv.quantity, inv.reserved, inv.available) == (7, 0, 7)


def test_inventory_reserve_more_than_available_fails(scarce_variant):
    with pytest.raises(InsufficientStock) as exc:
        inventory.reserve(scarce_variant.inventory, 3)
    assert exc.value.details == {"sku": "PB-WHT", "requested": 3, "available": 2}


def test_adjust_stock_cannot_drop_below_reserved(variant):
    inventory.reserve(variant.inventory, 6)
    with pytest.raises(InsufficientStock):
        inventory.adjust_stock(variant.inventory.pk, -5)
    inv = inventory.adjust_stock(variant.inventory.pk, +15)
    assert inv.quantity == 25
