"""Cash on delivery: no provider round-trip, the order is confirmed at checkout."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from apps.core.exceptions import PaymentError

from .base import IntentResult, WebhookResult


class CashOnDeliveryAdapter:
    code = "cod"
    requires_webhook = False

    def __init__(self, **_: object) -> None:
        pass

    def create_intent(self, *, order_number: str, amount: Decimal, currency: str) -> IntentResult:
        return IntentResult(
            provider_ref=f"COD-{order_number}",
            redirect_url="",
            raw={"collect_on_delivery": str(amount), "currency": currency},
        )

    def parse_webhook(
        self, *, body: bytes, headers: Mapping[str, str], payload: dict
    ) -> WebhookResult:
        raise PaymentError("Cash on delivery does not receive provider webhooks.")
