from __future__ import annotations

from functools import cache

from django.conf import settings
from django.utils.module_loading import import_string

from apps.core.exceptions import NotFound

from .adapters.base import PaymentAdapter


@cache
def get_adapter(provider: str) -> PaymentAdapter:
    config = settings.PAYMENT_PROVIDERS.get(provider)
    if config is None:
        raise NotFound(
            f"Unknown payment provider '{provider}'.",
            details={"available": sorted(settings.PAYMENT_PROVIDERS)},
        )
    adapter_cls = import_string(config["adapter"])
    return adapter_cls(webhook_secret=config.get("webhook_secret", ""))


def available_providers() -> list[str]:
    return sorted(settings.PAYMENT_PROVIDERS)
