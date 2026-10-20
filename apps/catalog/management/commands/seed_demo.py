"""Populate a demo catalogue, coupons and a staff user for local exploration.

The catalogue is a small Bangladeshi retail assortment (grocery, fashion, home,
electronics) priced in BDT, with Bangla display names on products and categories.
The command is idempotent: re-running it updates existing rows instead of
duplicating them.
"""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from apps.catalog.models import Category, Inventory, Product, ProductImage, ProductVariant
from apps.promotions.models import Coupon

CATEGORIES = [
    ("Grocery", "মুদি", None),
    ("Rice & Grains", "চাল ও শস্য", "Grocery"),
    ("Cooking Oil & Spices", "তেল ও মসলা", "Grocery"),
    ("Fashion", "ফ্যাশন", None),
    ("Men's Clothing", "পুরুষদের পোশাক", "Fashion"),
    ("Women's Clothing", "মহিলাদের পোশাক", "Fashion"),
    ("Home & Kitchen", "ঘর ও রান্নাঘর", None),
    ("Electronics", "ইলেকট্রনিক্স", None),
]

# (name, name_bn, category, base_price, description, variants)
# variant: (sku, name, attributes, price_override, weight_grams, stock)
PRODUCTS = [
    (
        "Miniket Rice Premium",
        "মিনিকেট চাল প্রিমিয়াম",
        "Rice & Grains",
        "395.00",
        "Polished miniket rice from Dinajpur, ideal for everyday meals.",
        [
            ("RICE-MINI-5", "5 kg", {"size": "5 kg"}, None, 5000, 120),
            ("RICE-MINI-25", "25 kg", {"size": "25 kg"}, "1890.00", 25000, 30),
        ],
    ),
    (
        "Chinigura Aromatic Rice",
        "চিনিগুঁড়া সুগন্ধি চাল",
        "Rice & Grains",
        "180.00",
        "Short-grain aromatic rice for polao and biryani.",
        [("RICE-CHINI-1", "1 kg", {"size": "1 kg"}, None, 1000, 200)],
    ),
    (
        "Fresh Soybean Oil",
        "ফ্রেশ সয়াবিন তেল",
        "Cooking Oil & Spices",
        "175.00",
        "Refined soybean oil, fortified with vitamin A.",
        [
            ("OIL-SOY-1", "1 litre", {"size": "1 L"}, None, 950, 150),
            ("OIL-SOY-5", "5 litre", {"size": "5 L"}, "860.00", 4700, 60),
        ],
    ),
    (
        "Radhuni Turmeric Powder",
        "রাঁধুনি হলুদ গুঁড়া",
        "Cooking Oil & Spices",
        "95.00",
        "Pure ground turmeric, 200 g pouch.",
        [("SPICE-TURM-200", "200 g", {"size": "200 g"}, None, 220, 300)],
    ),
    (
        "Men's Cotton Panjabi",
        "পুরুষদের সুতি পাঞ্জাবি",
        "Men's Clothing",
        "1450.00",
        "Handloom cotton panjabi from Tangail, regular fit.",
        [
            ("PANJ-WHT-M", "White / M", {"color": "white", "size": "M"}, None, 350, 25),
            ("PANJ-WHT-L", "White / L", {"color": "white", "size": "L"}, None, 370, 25),
            ("PANJ-WHT-XL", "White / XL", {"color": "white", "size": "XL"}, "1550.00", 390, 15),
            ("PANJ-NAVY-L", "Navy / L", {"color": "navy", "size": "L"}, None, 370, 10),
        ],
    ),
    (
        "Jamdani Saree",
        "জামদানি শাড়ি",
        "Women's Clothing",
        "6500.00",
        "Handwoven Jamdani saree from Rupganj, Narayanganj. Includes blouse piece.",
        [
            ("SAREE-JAM-RED", "Red", {"color": "red"}, None, 600, 8),
            ("SAREE-JAM-TEAL", "Teal", {"color": "teal"}, "6900.00", 600, 5),
        ],
    ),
    (
        "Three-piece Lawn Set",
        "থ্রি-পিস লন সেট",
        "Women's Clothing",
        "2250.00",
        "Unstitched printed lawn three-piece: kameez, salwar and dupatta.",
        [
            ("3PC-LAWN-BLU", "Blue print", {"color": "blue"}, None, 700, 20),
            ("3PC-LAWN-GRN", "Green print", {"color": "green"}, None, 700, 20),
        ],
    ),
    (
        "Non-stick Karai 26 cm",
        "নন-স্টিক কড়াই ২৬ সেমি",
        "Home & Kitchen",
        "1290.00",
        "Aluminium karai with glass lid, induction compatible.",
        [("KIT-KARAI-26", "26 cm", {"size": "26 cm"}, None, 1800, 40)],
    ),
    (
        "Stainless Steel Tiffin Carrier",
        "স্টেইনলেস স্টিল টিফিন ক্যারিয়ার",
        "Home & Kitchen",
        "650.00",
        "Three-tier leak-proof tiffin box.",
        [("KIT-TIFFIN-3", "3 tier", {"tiers": 3}, None, 900, 75)],
    ),
    (
        "Walton Ceiling Fan 56 inch",
        "ওয়ালটন সিলিং ফ্যান ৫৬ ইঞ্চি",
        "Electronics",
        "3290.00",
        "56-inch ceiling fan with copper winding and 5-year motor warranty.",
        [("ELEC-FAN-56", "56 inch", {"size": "56 in"}, None, 6500, 18)],
    ),
    (
        "Smartphone Power Bank 10000 mAh",
        "পাওয়ার ব্যাংক ১০০০০ এমএএইচ",
        "Electronics",
        "1150.00",
        "Dual-output 10000 mAh power bank with USB-C fast charging.",
        [
            ("ELEC-PB-10K-BLK", "Black", {"color": "black"}, None, 240, 60),
            ("ELEC-PB-10K-WHT", "White", {"color": "white"}, None, 240, 0),
        ],
    ),
    (
        "Bluetooth Earbuds",
        "ব্লুটুথ ইয়ারবাড",
        "Electronics",
        "1890.00",
        "True wireless earbuds with 24-hour battery case.",
        [("ELEC-TWS-01", "Default", {}, None, 120, 45)],
    ),
]

COUPONS = [
    ("EID10", "10% off up to 500 BDT", Coupon.Type.PERCENT, "10", "1000", "500", 500, 2),
    (
        "WELCOME150",
        "150 BDT off first order over 1500",
        Coupon.Type.FIXED,
        "150",
        "1500",
        None,
        None,
        1,
    ),
    (
        "FREESHIP",
        "Free delivery on orders over 2000",
        Coupon.Type.FREE_SHIPPING,
        "0",
        "2000",
        None,
        None,
        None,
    ),
]


class Command(BaseCommand):
    help = "Seed a demo catalogue, coupons and a staff user (admin / admin12345)."

    @transaction.atomic
    def handle(self, *args, **options):
        categories = self._seed_categories()
        product_count, variant_count = self._seed_products(categories)
        coupon_count = self._seed_coupons()
        self._seed_staff()
        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {len(categories)} categories, {product_count} products, "
                f"{variant_count} variants, {coupon_count} coupons. Staff login: admin / admin12345"
            )
        )

    def _seed_categories(self) -> dict[str, Category]:
        categories: dict[str, Category] = {}
        for name, name_bn, parent in CATEGORIES:
            cat, _ = Category.objects.update_or_create(
                slug=slugify(name),
                defaults={
                    "name": name,
                    "name_bn": name_bn,
                    "parent": categories[parent] if parent else None,
                },
            )
            categories[name] = cat
        return categories

    def _seed_products(self, categories: dict[str, Category]) -> tuple[int, int]:
        variant_total = 0
        for name, name_bn, category, price, description, variants in PRODUCTS:
            product, _ = Product.objects.update_or_create(
                slug=slugify(name),
                defaults={
                    "name": name,
                    "name_bn": name_bn,
                    "category": categories[category],
                    "base_price": Decimal(price),
                    "description": description,
                    "is_active": True,
                },
            )
            ProductImage.objects.update_or_create(
                product=product,
                sort_order=0,
                defaults={
                    "url": f"https://cdn.example.com/products/{product.slug}.jpg",
                    "alt_text": name,
                },
            )
            for sku, vname, attrs, override, weight, stock in variants:
                variant, _ = ProductVariant.objects.update_or_create(
                    sku=sku,
                    defaults={
                        "product": product,
                        "name": vname,
                        "attributes": attrs,
                        "price": Decimal(override) if override else None,
                        "weight_grams": weight,
                        "is_active": True,
                    },
                )
                inventory, created = Inventory.objects.get_or_create(
                    variant=variant, defaults={"quantity": stock}
                )
                if not created and inventory.quantity < stock:
                    inventory.quantity = stock
                    inventory.save(update_fields=["quantity"])
                variant_total += 1
        return len(PRODUCTS), variant_total

    def _seed_coupons(self) -> int:
        for code, desc, ctype, value, min_amount, max_discount, limit, per_user in COUPONS:
            Coupon.objects.update_or_create(
                code=code,
                defaults={
                    "description": desc,
                    "type": ctype,
                    "value": Decimal(value),
                    "min_order_amount": Decimal(min_amount),
                    "max_discount": Decimal(max_discount) if max_discount else None,
                    "usage_limit": limit,
                    "per_user_limit": per_user,
                    "expires_at": timezone.now() + timezone.timedelta(days=90),
                    "is_active": True,
                },
            )
        return len(COUPONS)

    def _seed_staff(self) -> None:
        User = get_user_model()
        if not User.objects.filter(username="admin").exists():
            User.objects.create_superuser("admin", "admin@example.com", "admin12345")
