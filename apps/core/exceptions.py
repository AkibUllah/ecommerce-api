"""Domain exceptions shared by all apps.

Service-layer code raises these instead of DRF exceptions so the business logic
stays framework-agnostic; ``config.exceptions.api_exception_handler`` maps them
to HTTP responses.
"""

from __future__ import annotations

from typing import Any


class DomainError(Exception):
    code = "domain_error"
    http_status = 400

    def __init__(self, message: str, *, details: Any = None) -> None:
        super().__init__(message)
        self.details = details


class NotFound(DomainError):
    code = "not_found"
    http_status = 404


class Conflict(DomainError):
    code = "conflict"
    http_status = 409


class InvalidTransition(DomainError):
    code = "invalid_transition"
    http_status = 409


class InsufficientStock(DomainError):
    code = "insufficient_stock"
    http_status = 409


class CouponError(DomainError):
    code = "invalid_coupon"
    http_status = 400


class PaymentError(DomainError):
    code = "payment_error"
    http_status = 400


class SignatureError(DomainError):
    code = "invalid_signature"
    http_status = 400
