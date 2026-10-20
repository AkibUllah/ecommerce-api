"""Inventory operations. Every function expects to run inside ``transaction.atomic``.

Reservations are a two-phase affair:

1. ``reserve`` bumps ``Inventory.reserved`` while holding a row lock, failing if
   ``available`` would go negative.
2. On payment ``commit`` moves the quantity out of both ``quantity`` and
   ``reserved`` (the goods leave the shelf); on cancellation/expiry ``release``
   only decrements ``reserved``.
"""

from __future__ import annotations

from collections.abc import Iterable

from django.db import transaction

from apps.core.exceptions import InsufficientStock

from .models import Inventory


def lock_inventories(variant_ids: Iterable[int]) -> dict[int, Inventory]:
    """Lock inventory rows in a stable order (by PK) to avoid deadlocks between checkouts."""
    rows = (
        Inventory.objects.select_for_update()
        .filter(variant_id__in=list(variant_ids))
        .order_by("pk")
    )
    return {inv.variant_id: inv for inv in rows}


def reserve(inventory: Inventory, quantity: int) -> None:
    if quantity <= 0:
        raise ValueError("quantity must be positive")
    if inventory.available < quantity:
        raise InsufficientStock(
            f"Only {inventory.available} unit(s) of {inventory.variant.sku} available.",
            details={
                "sku": inventory.variant.sku,
                "requested": quantity,
                "available": inventory.available,
            },
        )
    inventory.reserved += quantity
    inventory.save(update_fields=["reserved", "updated_at"])


def release(inventory: Inventory, quantity: int) -> None:
    inventory.reserved = max(0, inventory.reserved - quantity)
    inventory.save(update_fields=["reserved", "updated_at"])


def commit(inventory: Inventory, quantity: int) -> None:
    inventory.reserved = max(0, inventory.reserved - quantity)
    inventory.quantity = max(0, inventory.quantity - quantity)
    inventory.save(update_fields=["reserved", "quantity", "updated_at"])


@transaction.atomic
def adjust_stock(inventory_id: int, delta: int) -> Inventory:
    """Manual stock correction (receiving goods, stock count), locked for safety."""
    inv = Inventory.objects.select_for_update().get(pk=inventory_id)
    new_qty = inv.quantity + delta
    if new_qty < inv.reserved:
        raise InsufficientStock("Cannot reduce stock below the reserved quantity.")
    inv.quantity = new_qty
    inv.save(update_fields=["quantity", "updated_at"])
    return inv
