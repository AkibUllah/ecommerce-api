import pytest
from rest_framework.test import APIClient

from apps.orders.models import OrderStatus, PaymentMethod
from apps.reviews.models import Review
from apps.reviews.services import rating_summary

pytestmark = pytest.mark.django_db

URL = "/api/v1/reviews/"


def test_create_review_requires_auth(api_client, product):
    assert api_client.post(URL, {"product": product.pk, "rating": 5}).status_code == 401


def test_create_review_and_aggregate(auth_client, other_user, product):
    response = auth_client.post(
        URL,
        {
            "product": product.pk,
            "rating": 4,
            "title": "Good value",
            "body": "Charges my phone twice.",
        },
    )
    assert response.status_code == 201, response.json()
    assert response.json()["is_verified_purchase"] is False
    other_client = APIClient()
    other_client.force_authenticate(user=other_user)
    other_client.post(URL, {"product": product.pk, "rating": 5})
    assert rating_summary(product) == {"average": 4.5, "count": 2}
    detail = APIClient().get(f"/api/v1/catalog/products/{product.slug}/").json()
    assert detail["rating"] == {"average": 4.5, "count": 2}


def test_one_review_per_user_per_product(auth_client, product):
    assert auth_client.post(URL, {"product": product.pk, "rating": 3}).status_code == 201
    dup = auth_client.post(URL, {"product": product.pk, "rating": 1})
    assert dup.status_code == 400


def test_rating_bounds(auth_client, product):
    assert auth_client.post(URL, {"product": product.pk, "rating": 6}).status_code == 400
    assert auth_client.post(URL, {"product": product.pk, "rating": 0}).status_code == 400


def test_verified_purchase_flag_after_delivery(auth_client, place, variant, product):
    order = place((variant, 1), payment_method=PaymentMethod.COD)
    order.transition(OrderStatus.PROCESSING)
    order.transition(OrderStatus.SHIPPED)
    order.transition(OrderStatus.DELIVERED)
    response = auth_client.post(URL, {"product": product.pk, "rating": 5})
    assert response.json()["is_verified_purchase"] is True
    assert auth_client.get(f"{URL}?is_verified_purchase=true").json()["count"] == 1


def test_only_author_can_edit_or_delete(auth_client, other_user, product, user):
    review = Review.objects.create(product=product, user=user, rating=2)
    other_client = APIClient()
    other_client.force_authenticate(user=other_user)
    assert other_client.patch(f"{URL}{review.pk}/", {"rating": 5}).status_code == 403
    assert auth_client.patch(f"{URL}{review.pk}/", {"rating": 5}).json()["rating"] == 5
    assert auth_client.delete(f"{URL}{review.pk}/").status_code == 204
