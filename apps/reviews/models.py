from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.catalog.models import Product
from apps.core.models import TimeStampedModel


class Review(TimeStampedModel):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="reviews")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reviews"
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    title = models.CharField(max_length=120, blank=True)
    body = models.TextField(blank=True)
    is_verified_purchase = models.BooleanField(default=False)
    is_approved = models.BooleanField(default=True)

    class Meta:
        unique_together = ("product", "user")
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.product.name}: {self.rating}/5 by {self.user.username}"
