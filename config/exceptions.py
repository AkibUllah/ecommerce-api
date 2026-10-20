"""Uniform error envelope for the API.

Domain errors raised from the service layer (``apps.core.exceptions.DomainError``)
are translated into a consistent JSON shape so clients can rely on
``{"error": {"code": ..., "message": ..., "details": ...}}`` for every failure.
"""

from __future__ import annotations

import logging

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from apps.core.exceptions import DomainError

logger = logging.getLogger(__name__)


def api_exception_handler(exc: Exception, context: dict) -> Response | None:
    if isinstance(exc, DomainError):
        return Response(
            {"error": {"code": exc.code, "message": str(exc), "details": exc.details}},
            status=exc.http_status,
        )

    response = drf_exception_handler(exc, context)
    if response is None:
        logger.exception("Unhandled exception in %s", context.get("view"))
        return Response(
            {"error": {"code": "internal_error", "message": "Internal server error."}},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    detail = response.data
    if isinstance(detail, dict) and "detail" in detail and len(detail) == 1:
        message = str(detail["detail"])
        details = None
    else:
        message = "Validation failed."
        details = detail
    code = getattr(exc, "default_code", "error")
    response.data = {"error": {"code": code, "message": message, "details": details}}
    return response
