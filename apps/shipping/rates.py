"""Courier rate calculators (sandbox rate cards, not live API integrations).

Each calculator implements ``RateCalculator`` so the checkout only knows about the
protocol. Rate cards are modelled on public Pathao / RedX merchant pricing:
a base fee for the first kilogram, a per-kilogram surcharge above it and a COD
collection fee as a percentage of the collected amount.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from apps.core.exceptions import DomainError
from apps.core.money import ZERO, percent_of, quantize

from .zones import Zone


@dataclass(frozen=True)
class ShippingQuote:
    courier: str
    zone: Zone
    fee: Decimal
    cod_fee: Decimal
    eta_days: int

    @property
    def total(self) -> Decimal:
        return quantize(self.fee + self.cod_fee)


class RateCalculator(Protocol):
    code: str
    label: str

    def quote(self, zone: Zone, weight_grams: int, cod_amount: Decimal = ZERO) -> ShippingQuote: ...


@dataclass(frozen=True)
class _RateCard:
    base_fee: dict[Zone, Decimal]
    per_extra_kg: dict[Zone, Decimal]
    eta_days: dict[Zone, int]
    cod_rate: Decimal  # fraction of COD amount
    included_grams: int = 1000


class _CardCalculator:
    code = ""
    label = ""
    card: _RateCard

    def quote(self, zone: Zone, weight_grams: int, cod_amount: Decimal = ZERO) -> ShippingQuote:
        if weight_grams <= 0:
            raise DomainError("Parcel weight must be positive.")
        extra_grams = max(0, weight_grams - self.card.included_grams)
        extra_kg = math.ceil(extra_grams / 1000)
        fee = self.card.base_fee[zone] + self.card.per_extra_kg[zone] * extra_kg
        cod_fee = percent_of(cod_amount, self.card.cod_rate) if cod_amount > 0 else ZERO
        return ShippingQuote(
            courier=self.code,
            zone=zone,
            fee=quantize(fee),
            cod_fee=cod_fee,
            eta_days=self.card.eta_days[zone],
        )


class PathaoRateCalculator(_CardCalculator):
    code = "pathao"
    label = "Pathao Courier"
    card = _RateCard(
        base_fee={Zone.INSIDE_DHAKA: Decimal("60"), Zone.OUTSIDE_DHAKA: Decimal("120")},
        per_extra_kg={Zone.INSIDE_DHAKA: Decimal("15"), Zone.OUTSIDE_DHAKA: Decimal("20")},
        eta_days={Zone.INSIDE_DHAKA: 1, Zone.OUTSIDE_DHAKA: 3},
        cod_rate=Decimal("0.01"),
    )


class RedXRateCalculator(_CardCalculator):
    code = "redx"
    label = "RedX"
    card = _RateCard(
        base_fee={Zone.INSIDE_DHAKA: Decimal("60"), Zone.OUTSIDE_DHAKA: Decimal("130")},
        per_extra_kg={Zone.INSIDE_DHAKA: Decimal("10"), Zone.OUTSIDE_DHAKA: Decimal("25")},
        eta_days={Zone.INSIDE_DHAKA: 1, Zone.OUTSIDE_DHAKA: 4},
        cod_rate=Decimal("0.01"),
    )


CALCULATORS: dict[str, RateCalculator] = {
    PathaoRateCalculator.code: PathaoRateCalculator(),
    RedXRateCalculator.code: RedXRateCalculator(),
}


def get_calculator(courier: str) -> RateCalculator:
    try:
        return CALCULATORS[courier]
    except KeyError:
        raise DomainError(
            f"Unknown courier '{courier}'.", details={"available": sorted(CALCULATORS)}
        )


def quote_all(zone: Zone, weight_grams: int, cod_amount: Decimal = ZERO) -> list[ShippingQuote]:
    quotes = [calc.quote(zone, weight_grams, cod_amount) for calc in CALCULATORS.values()]
    return sorted(quotes, key=lambda q: (q.total, q.eta_days))
