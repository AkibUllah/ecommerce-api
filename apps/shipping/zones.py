"""Delivery zones used by every courier rate card.

Bangladeshi couriers price by two broad zones: inside Dhaka metro and everywhere
else. District matching is case-insensitive and tolerant of common spellings.
"""

from __future__ import annotations

from enum import Enum


class Zone(str, Enum):
    INSIDE_DHAKA = "inside_dhaka"
    OUTSIDE_DHAKA = "outside_dhaka"

    def __str__(self) -> str:
        return self.value


_DHAKA_ALIASES = {"dhaka", "ঢাকা", "dhaka city", "dhaka metro", "dhaka metropolitan"}


def zone_for_district(district: str) -> Zone:
    normalized = (district or "").strip().lower()
    return Zone.INSIDE_DHAKA if normalized in _DHAKA_ALIASES else Zone.OUTSIDE_DHAKA
