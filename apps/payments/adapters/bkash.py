"""bKash Tokenized Checkout - sandbox stub.

Mirrors the field names of the bKash API (``paymentID``, ``trxID``,
``transactionStatus``) so a real adapter can replace this one without touching
the webhook view.
"""

from __future__ import annotations

import secrets
from collections.abc import Mapping
from decimal import Decimal

from .base import IntentResult, WebhookResult, verify_hmac

SIGNATURE_HEADER = "X-Bkash-Signature"


class BkashSandboxAdapter:
    code = "bkash"
    requires_webhook = True

    def __init__(self, *, webhook_secret: str) -> None:
        self.webhook_secret = webhook_secret

    def create_intent(self, *, order_number: str, amount: Decimal, currency: str) -> IntentResult:
        payment_id = f"TR{secrets.token_hex(6).upper()}"
        return IntentResult(
            provider_ref=payment_id,
            redirect_url=f"https://sandbox.payment.bkash.com/checkout/{payment_id}",
            raw={
                "paymentID": payment_id,
                "merchantInvoiceNumber": order_number,
                "amount": str(amount),
                "currency": currency,
                "intent": "sale",
                "mode": "sandbox",
            },
        )

    def parse_webhook(
        self, *, body: bytes, headers: Mapping[str, str], payload: dict
    ) -> WebhookResult:
        verify_hmac(self.webhook_secret, body, headers.get(SIGNATURE_HEADER))
        status = str(payload.get("transactionStatus", "")).lower()
        return WebhookResult(
            event_id=str(payload.get("trxID") or payload.get("paymentID", "")),
            provider_ref=str(payload.get("paymentID", "")),
            succeeded=status == "completed",
            amount=Decimal(str(payload["amount"])) if payload.get("amount") is not None else None,
            failure_reason="" if status == "completed" else payload.get("statusMessage", status),
            raw=payload,
        )
