"""SSLCommerz hosted checkout - sandbox stub.

Field names follow the SSLCommerz IPN (``tran_id``, ``val_id``, ``status``).
"""

from __future__ import annotations

import secrets
from collections.abc import Mapping
from decimal import Decimal

from .base import IntentResult, WebhookResult, verify_hmac

SIGNATURE_HEADER = "X-SSLCommerz-Signature"


class SSLCommerzSandboxAdapter:
    code = "sslcommerz"
    requires_webhook = True

    def __init__(self, *, webhook_secret: str) -> None:
        self.webhook_secret = webhook_secret

    def create_intent(self, *, order_number: str, amount: Decimal, currency: str) -> IntentResult:
        session_key = secrets.token_hex(16).upper()
        return IntentResult(
            provider_ref=order_number,  # SSLCommerz echoes the merchant tran_id back
            redirect_url=f"https://sandbox.sslcommerz.com/EasyCheckOut/{session_key}",
            raw={
                "sessionkey": session_key,
                "tran_id": order_number,
                "total_amount": str(amount),
                "currency": currency,
                "mode": "sandbox",
            },
        )

    def parse_webhook(
        self, *, body: bytes, headers: Mapping[str, str], payload: dict
    ) -> WebhookResult:
        verify_hmac(self.webhook_secret, body, headers.get(SIGNATURE_HEADER))
        status = str(payload.get("status", "")).upper()
        return WebhookResult(
            event_id=str(payload.get("val_id") or payload.get("tran_id", "")),
            provider_ref=str(payload.get("tran_id", "")),
            succeeded=status in {"VALID", "VALIDATED"},
            amount=Decimal(str(payload["amount"])) if payload.get("amount") is not None else None,
            failure_reason="" if status in {"VALID", "VALIDATED"} else payload.get("error", status),
            raw=payload,
        )
