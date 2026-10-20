from __future__ import annotations

import json
import logging
from collections.abc import Mapping

from django.db import transaction

from apps.core.exceptions import DomainError, PaymentError
from apps.orders import services as order_services
from apps.orders.models import Order, OrderStatus

from .models import PaymentIntent, WebhookEvent
from .registry import get_adapter

logger = logging.getLogger(__name__)


@transaction.atomic
def create_intent(order: Order, provider: str) -> PaymentIntent:
    if order.status != OrderStatus.PENDING:
        raise PaymentError(
            f"Order {order.number} is not awaiting payment (status '{order.status}')."
        )
    if order.is_expired:
        raise PaymentError("The stock reservation for this order has expired. Place a new order.")
    if provider != order.payment_method:
        raise PaymentError(
            f"Order was placed with '{order.payment_method}', cannot pay with '{provider}'."
        )
    adapter = get_adapter(provider)
    result = adapter.create_intent(
        order_number=order.number, amount=order.total, currency=order.currency
    )
    intent = PaymentIntent.objects.create(
        order=order,
        provider=provider,
        amount=order.total,
        currency=order.currency,
        provider_ref=result.provider_ref,
        redirect_url=result.redirect_url,
        raw_response=result.raw,
    )
    logger.info(
        "payment intent created provider=%s order=%s ref=%s",
        provider,
        order.number,
        result.provider_ref,
    )
    return intent


def handle_webhook(provider: str, *, body: bytes, headers: Mapping[str, str]) -> WebhookEvent:
    """Verify, record and apply a provider notification. Safe to call more than once."""
    adapter = get_adapter(provider)
    try:
        payload = json.loads(body or b"{}")
    except json.JSONDecodeError:
        raise DomainError("Webhook body must be JSON.")
    if not isinstance(payload, dict):
        raise DomainError("Webhook body must be a JSON object.")

    result = adapter.parse_webhook(body=body, headers=headers, payload=payload)  # raises on bad sig

    with transaction.atomic():
        event, created = WebhookEvent.objects.get_or_create(
            provider=provider,
            event_id=result.event_id or "unknown",
            defaults={"payload": payload, "signature_valid": True},
        )
        if not created and event.processed:
            logger.info("duplicate webhook ignored provider=%s event=%s", provider, event.event_id)
            return event

        intent = (
            PaymentIntent.objects.select_for_update()
            .filter(provider=provider, provider_ref=result.provider_ref)
            .order_by("-created_at")
            .first()
        )
        if intent is None:
            raise PaymentError(
                f"No payment intent found for reference '{result.provider_ref}'.",
                details={"provider": provider, "provider_ref": result.provider_ref},
            )
        event.intent = intent

        if result.succeeded:
            if result.amount is not None and result.amount != intent.amount:
                intent.status = PaymentIntent.Status.FAILED
                intent.failure_reason = (
                    f"Amount mismatch: expected {intent.amount}, got {result.amount}"
                )
                intent.save(update_fields=["status", "failure_reason", "updated_at"])
                event.processed = True
                event.save()
                raise PaymentError(intent.failure_reason)
            intent.status = PaymentIntent.Status.SUCCEEDED
            intent.raw_response = {**intent.raw_response, "webhook": result.raw}
            intent.save(update_fields=["status", "raw_response", "updated_at"])
            order_services.mark_paid(intent.order, note=f"{provider} payment {result.event_id}")
        else:
            intent.status = PaymentIntent.Status.FAILED
            intent.failure_reason = result.failure_reason[:255]
            intent.save(update_fields=["status", "failure_reason", "updated_at"])

        event.processed = True
        event.save()
    logger.info(
        "webhook processed provider=%s event=%s succeeded=%s",
        provider,
        event.event_id,
        result.succeeded,
    )
    return event
