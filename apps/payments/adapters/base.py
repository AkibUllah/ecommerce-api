"""Provider adapter protocol.

Adapters translate between the generic payment flow (create an intent, interpret a
webhook) and a specific provider's wire format. The implementations shipped here
are **sandbox stubs**: they generate deterministic references and verify an
HMAC-SHA256 signature over the raw webhook body using a shared secret, which is
the same shape real integrations take once credentials are added.
"""

from __future__ import annotations

import hashlib
import hmac
from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Protocol

from apps.core.exceptions import SignatureError


@dataclass(frozen=True)
class IntentResult:
    provider_ref: str
    redirect_url: str
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class WebhookResult:
    event_id: str
    provider_ref: str
    succeeded: bool
    amount: Decimal | None = None
    failure_reason: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


class PaymentAdapter(Protocol):
    code: str
    requires_webhook: bool

    def create_intent(
        self, *, order_number: str, amount: Decimal, currency: str
    ) -> IntentResult: ...

    def parse_webhook(
        self, *, body: bytes, headers: Mapping[str, str], payload: dict
    ) -> WebhookResult: ...


def hmac_hex(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def verify_hmac(secret: str, body: bytes, provided: str | None) -> None:
    if not provided or not hmac.compare_digest(hmac_hex(secret, body), provided.strip().lower()):
        raise SignatureError("Webhook signature verification failed.")
