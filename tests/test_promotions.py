from decimal import Decimal

import pytest
from django.utils import timezone

from apps.core.exceptions import CouponError
from apps.promotions import services
from apps.promotions.models import Coupon, CouponRedemption

pytestmark = pytest.mark.django_db


def test_percent_coupon_discount(percent_coupon):
    result = services.apply_coupon("eid10", subtotal=Decimal("2300.00"), shipping_fee=Decimal("60"))
    assert result.discount == Decimal("230.00")
    assert result.shipping_discount == Decimal("0.00")


def test_percent_coupon_capped_by_max_discount(percent_coupon):
    result = services.apply_coupon("EID10", subtotal=Decimal("9000.00"), shipping_fee=Decimal("60"))
    assert result.discount == Decimal("500.00")


def test_fixed_coupon_never_exceeds_subtotal():
    Coupon.objects.create(code="FLAT300", type=Coupon.Type.FIXED, value=Decimal("300"))
    assert services.apply_coupon(
        "FLAT300", subtotal=Decimal("1000"), shipping_fee=Decimal("0")
    ).discount == Decimal("300.00")
    assert services.apply_coupon(
        "FLAT300", subtotal=Decimal("200"), shipping_fee=Decimal("0")
    ).discount == Decimal("200.00")


def test_free_shipping_coupon():
    Coupon.objects.create(code="FREESHIP", type=Coupon.Type.FREE_SHIPPING)
    result = services.apply_coupon(
        "FREESHIP", subtotal=Decimal("500"), shipping_fee=Decimal("120.00")
    )
    assert result.discount == Decimal("0.00")
    assert result.shipping_discount == Decimal("120.00")
    assert result.total == Decimal("120.00")


def test_min_order_amount_enforced(percent_coupon):
    with pytest.raises(CouponError, match="at least 1000"):
        services.validate_coupon("EID10", subtotal=Decimal("999.99"))


def test_unknown_inactive_and_expired_coupons():
    with pytest.raises(CouponError, match="not found"):
        services.validate_coupon("NOPE", subtotal=Decimal("5000"))
    Coupon.objects.create(code="OFF", type=Coupon.Type.FIXED, value=10, is_active=False)
    with pytest.raises(CouponError, match="no longer active"):
        services.validate_coupon("OFF", subtotal=Decimal("5000"))
    Coupon.objects.create(
        code="OLD",
        type=Coupon.Type.FIXED,
        value=10,
        expires_at=timezone.now() - timezone.timedelta(minutes=1),
    )
    with pytest.raises(CouponError, match="expired"):
        services.validate_coupon("OLD", subtotal=Decimal("5000"))
    Coupon.objects.create(
        code="SOON",
        type=Coupon.Type.FIXED,
        value=10,
        starts_at=timezone.now() + timezone.timedelta(days=1),
    )
    with pytest.raises(CouponError, match="not valid yet"):
        services.validate_coupon("SOON", subtotal=Decimal("5000"))


def test_usage_limit_enforced(percent_coupon):
    percent_coupon.usage_limit = 1
    percent_coupon.used_count = 1
    percent_coupon.save()
    with pytest.raises(CouponError, match="usage limit"):
        services.validate_coupon("EID10", subtotal=Decimal("5000"))


def test_per_user_limit_enforced(percent_coupon, user, place, variant):
    percent_coupon.per_user_limit = 1
    percent_coupon.save()
    order = place((variant, 1), coupon_code="EID10")
    assert CouponRedemption.objects.filter(coupon=percent_coupon, user=user, order=order).exists()
    percent_coupon.refresh_from_db()
    assert percent_coupon.used_count == 1
    with pytest.raises(CouponError, match="maximum number of times"):
        services.validate_coupon("EID10", subtotal=Decimal("5000"), user=user)


def test_revert_restores_usage(percent_coupon, place, variant):
    order = place((variant, 1), coupon_code="EID10")
    services.revert(order)
    percent_coupon.refresh_from_db()
    assert percent_coupon.used_count == 0
    assert not CouponRedemption.objects.filter(order=order).exists()


def test_validate_endpoint(api_client, percent_coupon):
    response = api_client.post(
        "/api/v1/promotions/validate/",
        {"code": "eid10", "subtotal": "2000.00", "shipping_fee": "60"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["discount"] == "200.00"
    assert body["coupon"]["code"] == "EID10"

    bad = api_client.post("/api/v1/promotions/validate/", {"code": "eid10", "subtotal": "100"})
    assert bad.status_code == 400
    assert bad.json()["error"]["code"] == "invalid_coupon"
