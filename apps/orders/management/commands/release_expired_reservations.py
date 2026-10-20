"""Release stock held by unpaid orders whose reservation window has passed.

Run from cron (e.g. every minute) instead of a Celery beat worker:

    * * * * * cd /app && python manage.py release_expired_reservations
"""

from django.core.management.base import BaseCommand

from apps.orders.services import release_expired_reservations


class Command(BaseCommand):
    help = "Expire unpaid orders past their reservation deadline and release their stock."

    def handle(self, *args, **options):
        count = release_expired_reservations()
        self.stdout.write(self.style.SUCCESS(f"Released {count} expired reservation(s)."))
