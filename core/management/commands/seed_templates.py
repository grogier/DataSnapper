from django.core.management.base import BaseCommand

from correspondence.models import Template
from correspondence.seed_data import SEED_TEMPLATES


class Command(BaseCommand):
    help = "Create the built-in English and Dutch letter templates if missing."

    def handle(self, *args, **options):
        created = 0
        for item in SEED_TEMPLATES:
            if Template.objects.filter(slug=item["slug"], locale=item["locale"]).exists():
                continue
            Template.objects.create(version=1, is_active=True, **item)
            created += 1
        self.stdout.write(self.style.SUCCESS(f"Templates created: {created}."))
