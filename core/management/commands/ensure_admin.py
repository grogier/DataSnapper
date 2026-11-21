from __future__ import annotations

import os
import secrets

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create the first admin user from environment variables if no user exists."

    def handle(self, *args, **options):
        User = get_user_model()
        if User.objects.exists():
            self.stdout.write("A user already exists; not creating another one.")
            return

        username = os.environ.get("ADMIN_USERNAME", "admin")
        email = os.environ.get("ADMIN_EMAIL", "")
        password = os.environ.get("ADMIN_PASSWORD", "")
        generated = False
        if not password:
            password = secrets.token_urlsafe(18)
            generated = True

        User.objects.create_superuser(username=username, email=email, password=password)
        self.stdout.write(self.style.SUCCESS(f"Created admin user '{username}'."))
        if generated:
            self.stdout.write(
                self.style.WARNING("ADMIN_PASSWORD was not set. Generated password: " + password)
            )
            self.stdout.write(
                "Change it after signing in, or set ADMIN_PASSWORD before the first start."
            )
