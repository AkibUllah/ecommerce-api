from __future__ import annotations

from django.db.models import Avg, Count

from apps.catalog.models import Product
from apps.orders.models import OrderStatus

from .models import Review


def has_purchased(user, product: Product) -> bool:
    """A purchase counts once the order has been delivered."""
    if not user.is_authenticated:
        return False
    return user.orders.filter(
        status=OrderStatus.DELIVERED, items__variant__product=product
    ).exists()


def rating_summary(product: Product) -> dict:
    agg = Review.objects.filter(product=product, is_approved=True).aggregate(
        average=Avg("rating"), count=Count("id")
    )
    average = agg["average"]
    return {
        "average": round(float(average), 2) if average is not None else None,
        "count": agg["count"],
    }
