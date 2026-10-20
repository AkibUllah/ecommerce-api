from decimal import Decimal

import pytest

from apps.core.exceptions import DomainError
from apps.shipping.rates import PathaoRateCalculator, RedXRateCalculator, get_calculator, quote_all
from apps.shipping.zones import Zone, zone_for_district


@pytest.mark.parametrize(
    "district,expected",
    [
        ("Dhaka", Zone.INSIDE_DHAKA),
        ("  dhaka ", Zone.INSIDE_DHAKA),
        ("ঢাকা", Zone.INSIDE_DHAKA),
        ("Chattogram", Zone.OUTSIDE_DHAKA),
        ("Gazipur", Zone.OUTSIDE_DHAKA),
        ("", Zone.OUTSIDE_DHAKA),
    ],
)
def test_zone_detection(district, expected):
    assert zone_for_district(district) is expected


def test_pathao_base_fee_inside_and_outside_dhaka():
    calc = PathaoRateCalculator()
    inside = calc.quote(Zone.INSIDE_DHAKA, 800)
    outside = calc.quote(Zone.OUTSIDE_DHAKA, 800)
    assert (inside.fee, inside.eta_days) == (Decimal("60.00"), 1)
    assert (outside.fee, outside.eta_days) == (Decimal("120.00"), 3)
    assert inside.cod_fee == Decimal("0.00")


def test_weight_surcharge_rounds_up_per_kg():
    calc = PathaoRateCalculator()
    assert calc.quote(Zone.INSIDE_DHAKA, 1000).fee == Decimal("60.00")  # exactly 1 kg included
    assert calc.quote(Zone.INSIDE_DHAKA, 1001).fee == Decimal("75.00")  # 1 extra kg
    assert calc.quote(Zone.INSIDE_DHAKA, 2500).fee == Decimal("90.00")  # 2 extra kg
    assert calc.quote(Zone.OUTSIDE_DHAKA, 6500).fee == Decimal("240.00")  # 120 + 6*20


def test_cod_fee_is_one_percent_of_collected_amount():
    quote = RedXRateCalculator().quote(Zone.OUTSIDE_DHAKA, 500, cod_amount=Decimal("2345.00"))
    assert quote.fee == Decimal("130.00")
    assert quote.cod_fee == Decimal("23.45")
    assert quote.total == Decimal("153.45")


def test_quote_all_sorted_by_total_and_unknown_courier():
    quotes = quote_all(Zone.OUTSIDE_DHAKA, 500)
    assert [q.courier for q in quotes] == ["pathao", "redx"]
    assert quotes[0].total <= quotes[1].total
    with pytest.raises(DomainError):
        get_calculator("sundarban")


def test_invalid_weight():
    with pytest.raises(DomainError):
        PathaoRateCalculator().quote(Zone.INSIDE_DHAKA, 0)


@pytest.mark.django_db
def test_rates_endpoint(api_client):
    response = api_client.get(
        "/api/v1/shipping/rates/",
        {"district": "Sylhet", "weight_grams": 1500, "cod_amount": "1000"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["zone"] == "outside_dhaka"
    pathao = next(q for q in body["quotes"] if q["courier"] == "pathao")
    assert pathao == {
        "courier": "pathao",
        "zone": "outside_dhaka",
        "fee": "140.00",
        "cod_fee": "10.00",
        "total": "150.00",
        "eta_days": 3,
    }

    bad = api_client.get("/api/v1/shipping/rates/", {"district": "Dhaka", "weight_grams": 0})
    assert bad.status_code == 400
