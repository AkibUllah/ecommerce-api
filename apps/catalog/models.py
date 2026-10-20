from __future__ import annotations

from decimal import Decimal

from django.db import models
from django.utils.text import slugify

from apps.core.models import TimeStampedModel


class Category(TimeStampedModel):
    name = models.CharField(max_length=120)
    name_bn = models.CharField("name (Bangla)", max_length=120, blank=True)
    slug = models.SlugField(max_length=140, unique=True)
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.CASCADE, related_name="children"
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("name",)
        verbose_name_plural = "categories"

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Product(TimeStampedModel):
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products")
    name = models.CharField(max_length=200)
    name_bn = models.CharField("name (Bangla)", max_length=200, blank=True)
    slug = models.SlugField(max_length=220, unique=True)
    description = models.TextField(blank=True)
    base_price = models.DecimalField(max_digits=12, decimal_places=2)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=["is_active", "category"])]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    @property
    def price_from(self) -> Decimal:
        prices = [v.effective_price for v in self.variants.all() if v.is_active]
        return min(prices) if prices else self.base_price


class ProductVariant(TimeStampedModel):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="variants")
    sku = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=120, help_text="e.g. 'Red / XL' or 'Default'")
    attributes = models.JSONField(default=dict, blank=True)
    price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Overrides the product base price when set.",
    )
    weight_grams = models.PositiveIntegerField(default=500)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("product", "sku")

    def __str__(self) -> str:
        return f"{self.product.name} - {self.name} ({self.sku})"

    @property
    def effective_price(self) -> Decimal:
        return self.price if self.price is not None else self.product.base_price


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images")
    url = models.URLField(max_length=500)
    alt_text = models.CharField(max_length=200, blank=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ("sort_order", "id")

    def __str__(self) -> str:
        return self.url


class Inventory(models.Model):
    """Stock on hand plus the quantity currently held by unpaid orders.

    ``available = quantity - reserved``. Rows are locked with ``select_for_update``
    during checkout so concurrent requests cannot oversell the last unit.
    """

    variant = models.OneToOneField(
        ProductVariant, on_delete=models.CASCADE, related_name="inventory"
    )
    quantity = models.PositiveIntegerField(default=0)
    reserved = models.PositiveIntegerField(default=0)
    low_stock_threshold = models.PositiveIntegerField(default=5)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "inventories"
        constraints = [
            models.CheckConstraint(
                check=models.Q(reserved__lte=models.F("quantity")),
                name="inventory_reserved_lte_quantity",
            )
        ]

    def __str__(self) -> str:
        return f"{self.variant.sku}: {self.available}/{self.quantity}"

    @property
    def available(self) -> int:
        return self.quantity - self.reserved

    @property
    def is_low(self) -> bool:
        return self.available <= self.low_stock_threshold
