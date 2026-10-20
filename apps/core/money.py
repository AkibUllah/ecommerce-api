"""Money helpers. All monetary values are ``Decimal`` with two places."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

ZERO = Decimal("0.00")
CENT = Decimal("0.01")


def quantize(value: Decimal | int | str) -> Decimal:
    """Round to two decimal places using bankers-unfriendly half-up (what receipts show)."""
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def percent_of(amount: Decimal, rate: Decimal) -> Decimal:
    """``amount * rate`` rounded to the cent. ``rate`` is a fraction, e.g. ``Decimal('0.05')``."""
    return quantize(Decimal(amount) * Decimal(rate))
