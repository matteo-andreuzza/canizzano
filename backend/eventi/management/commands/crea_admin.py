"""Crea il superuser di redazione da variabili d'ambiente, senza prompt."""

import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Crea (o aggiorna la password del) superuser definito nel file .env"

    def handle(self, *args, **options):
        utente = os.environ.get("DJANGO_SUPERUSER_USERNAME")
        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD")
        email = os.environ.get("DJANGO_SUPERUSER_EMAIL", "")

        if not utente or not password:
            self.stdout.write(
                "DJANGO_SUPERUSER_USERNAME/PASSWORD non impostati: salto la creazione."
            )
            return

        Utente = get_user_model()
        account, creato = Utente.objects.get_or_create(
            username=utente, defaults={"email": email, "is_staff": True, "is_superuser": True}
        )
        account.email = email or account.email
        account.is_staff = True
        account.is_superuser = True
        account.set_password(password)
        account.save()

        self.stdout.write(
            self.style.SUCCESS(f"Superuser «{utente}» {'creato' if creato else 'aggiornato'}.")
        )
