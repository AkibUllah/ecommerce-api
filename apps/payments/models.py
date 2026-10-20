from __future__ import annotations

import uuid

from django.db import models

from apps.core.models import TimeStampedModel
from apps.orders.models import Order


class PaymentIntent(TimeStampedModel):
    """One attempt to collect payment for an order through a provider."""

    class Status(models.TextChoices):
        CREATED = "created", "Created"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name="payment_intents")
    provider = models.CharField(max_length=20, db_index=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default="BDT")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.CREATED)
    provider_ref = models.CharField(max_length=100, blank=True, db_index=True)
    redirect_url = models.URLField(max_length=500, blank=True)
    failure_reason = models.CharField(max_length=255, blank=True)
    raw_response = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.provider}:{self.provider_ref or self.id} ({self.status})"


class WebhookEvent(models.Model):
    """Every inbound provider notification, kept for auditing and replay safety."""

    provider = models.CharField(max_length=20, db_index=True)
    event_id = models.CharField(max_length=120, db_index=True)
    intent = models.ForeignKey(
        PaymentIntent, null=True, blank=True, on_delete=models.SET_NULL, related_name="events"
    )
    payload = models.JSONField()
    signature_valid = models.BooleanField(default=False)
    processed = models.BooleanField(default=False)
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-received_at",)
        unique_together = ("provider", "event_id")

    def __str__(self) -> str:
        return f"{self.provider}:{self.event_id}"
