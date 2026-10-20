import json
from decimal import Decimal

import pytest

from apps.core.exceptions import PaymentError
from apps.orders.models import OrderStatus, PaymentMethod
from apps.payments import services
from apps.payments.adapters.base import hmac_hex
from apps.payments.models import PaymentIntent, WebhookEvent

pytestmark = pytest.mark.django_db

BKASH_SECRET = "bkash-sandbox-secret"
SSL_SECRET = "sslcommerz-sandbox-secret"


def _post_webhook(client, provider, payload, secret, header):
    body = json.dumps(payload).encode()
    headers = {f"HTTP_{header.upper().replace('-', '_')}": hmac_hex(secret, body)} if secret else {}
    return client.post(
        f"/api/v1/payments/webhooks/{provider}/",
        data=body,
        content_type="application/json",
        **headers,
    )


def test_create_intent_returns_redirect(auth_client, place, variant):
    order = place((variant, 1))
    response = auth_client.post(
        "/api/v1/payments/intents/", {"order_number": order.number, "provider": "bkash"}
    )
    assert response.status_code == 201, response.json()
    body = response.json()
    assert body["status"] == "created"
    assert body["amount"] == str(order.total)
    assert body["redirect_url"].startswith("https://sandbox.payment.bkash.com/checkout/")
    assert PaymentIntent.objects.get(pk=body["id"]).provider_ref == body["provider_ref"]


def test_intent_provider_must_match_order_method(place, variant):
    order = place((variant, 1), payment_method=PaymentMethod.SSLCOMMERZ)
    with pytest.raises(PaymentError, match="cannot pay with 'bkash'"):
        services.create_intent(order, "bkash")


def test_intent_rejected_for_non_pending_order(place, variant):
    order = place((variant, 1), payment_method=PaymentMethod.COD)
    assert order.status == OrderStatus.CONFIRMED
    with pytest.raises(PaymentError, match="not awaiting payment"):
        services.create_intent(order, "cod")


def test_bkash_webhook_success_confirms_order_and_commits_stock(api_client, place, variant):
    order = place((variant, 2))
    intent = services.create_intent(order, "bkash")
    payload = {
        "paymentID": intent.provider_ref,
        "trxID": "8AB12CD3EF",
        "transactionStatus": "Completed",
        "amount": str(order.total),
        "currency": "BDT",
    }
    response = _post_webhook(api_client, "bkash", payload, BKASH_SECRET, "X-Bkash-Signature")
    assert response.status_code == 200, response.json()

    order.refresh_from_db()
    intent.refresh_from_db()
    assert order.status == OrderStatus.CONFIRMED
    assert intent.status == PaymentIntent.Status.SUCCEEDED
    variant.inventory.refresh_from_db()
    assert (variant.inventory.quantity, variant.inventory.reserved) == (8, 0)
    assert WebhookEvent.objects.get(event_id="8AB12CD3EF").processed


def test_webhook_bad_signature_rejected(api_client, place, variant):
    order = place((variant, 1))
    intent = services.create_intent(order, "bkash")
    payload = {"paymentID": intent.provider_ref, "trxID": "X1", "transactionStatus": "Completed"}
    response = _post_webhook(api_client, "bkash", payload, "wrong-secret", "X-Bkash-Signature")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_signature"
    missing = _post_webhook(api_client, "bkash", payload, None, "X-Bkash-Signature")
    assert missing.status_code == 400
    order.refresh_from_db()
    assert order.status == OrderStatus.PENDING
    assert WebhookEvent.objects.count() == 0


def test_webhook_failure_keeps_order_pending_for_retry(api_client, place, variant):
    order = place((variant, 1), payment_method=PaymentMethod.SSLCOMMERZ)
    intent = services.create_intent(order, "sslcommerz")
    payload = {
        "tran_id": intent.provider_ref,
        "val_id": "V-1",
        "status": "FAILED",
        "error": "Insufficient balance",
    }
    response = _post_webhook(
        api_client, "sslcommerz", payload, SSL_SECRET, "X-SSLCommerz-Signature"
    )
    assert response.status_code == 200
    intent.refresh_from_db()
    order.refresh_from_db()
    assert intent.status == PaymentIntent.Status.FAILED
    assert intent.failure_reason == "Insufficient balance"
    assert order.status == OrderStatus.PENDING

    # Customer retries and succeeds
    retry = services.create_intent(order, "sslcommerz")
    ok = {
        "tran_id": retry.provider_ref,
        "val_id": "V-2",
        "status": "VALID",
        "amount": str(order.total),
    }
    assert (
        _post_webhook(
            api_client, "sslcommerz", ok, SSL_SECRET, "X-SSLCommerz-Signature"
        ).status_code
        == 200
    )
    order.refresh_from_db()
    assert order.status == OrderStatus.CONFIRMED


def test_duplicate_webhook_is_ignored(api_client, place, variant):
    order = place((variant, 1))
    intent = services.create_intent(order, "bkash")
    payload = {"paymentID": intent.provider_ref, "trxID": "DUP1", "transactionStatus": "Completed"}
    for _ in range(2):
        assert (
            _post_webhook(
                api_client, "bkash", payload, BKASH_SECRET, "X-Bkash-Signature"
            ).status_code
            == 200
        )
    assert WebhookEvent.objects.filter(event_id="DUP1").count() == 1
    variant.inventory.refresh_from_db()
    assert variant.inventory.quantity == 9  # committed exactly once


def test_webhook_amount_mismatch_fails_intent(api_client, place, variant):
    order = place((variant, 1))
    intent = services.create_intent(order, "bkash")
    payload = {
        "paymentID": intent.provider_ref,
        "trxID": "LOW1",
        "transactionStatus": "Completed",
        "amount": str(order.total - Decimal("100")),
    }
    response = _post_webhook(api_client, "bkash", payload, BKASH_SECRET, "X-Bkash-Signature")
    assert response.status_code == 400
    assert "Amount mismatch" in response.json()["error"]["message"]
    order.refresh_from_db()
    assert order.status == OrderStatus.PENDING


def test_webhook_unknown_provider_and_unknown_reference(api_client):
    assert (
        api_client.post(
            "/api/v1/payments/webhooks/paypal/", data=b"{}", content_type="application/json"
        ).status_code
        == 404
    )
    payload = {"paymentID": "NOPE", "trxID": "T", "transactionStatus": "Completed"}
    response = _post_webhook(api_client, "bkash", payload, BKASH_SECRET, "X-Bkash-Signature")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "payment_error"
