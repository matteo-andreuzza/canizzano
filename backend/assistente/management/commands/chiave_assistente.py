"""
«Dammi la chiave per collegare l'agente», dal terminale.

    python manage.py chiave_assistente            mostra quella che c'e'
    python manage.py chiave_assistente --nuova    ne aggiunge un'altra

Le stesse istruzioni della pagina d'admin: chi lavora da terminale non deve
aprire il browser per una riga da copiare.
"""

from django.core.management.base import BaseCommand

from assistente.collegamento import istruzioni
from assistente.models import ChiaveAssistente


class Command(BaseCommand):
    help = "Mostra o crea la chiave con cui un agente AI si collega al CMS."

    def add_arguments(self, parser):
        parser.add_argument(
            "--nuova", action="store_true", help="Crea una chiave nuova invece di mostrare quelle che ci sono."
        )
        parser.add_argument("--nome", default="Il mio assistente", help="Come chiamarla.")
        parser.add_argument(
            "--sola-lettura", action="store_true", help="La chiave potrà guardare ma non modificare."
        )

    def handle(self, *args, **opzioni):
        if opzioni["nuova"]:
            chiave = ChiaveAssistente.objects.create(
                nome=opzioni["nome"], sola_lettura=opzioni["sola_lettura"]
            )
            self.stdout.write(self.style.SUCCESS(f"Creata la chiave «{chiave.nome}».\n"))
        else:
            chiave = ChiaveAssistente.objects.filter(attiva=True).order_by("creata_il").first()
            if chiave is None:
                chiave = ChiaveAssistente.objects.create(nome=opzioni["nome"])
                self.stdout.write(
                    self.style.SUCCESS("Non c'era nessuna chiave attiva: ne ho creata una.\n")
                )

        self.stdout.write(istruzioni(chiave.chiave, chiave.nome))

        altre = ChiaveAssistente.objects.filter(attiva=True).exclude(pk=chiave.pk).count()
        if altre:
            self.stdout.write(
                f"\nCi sono altre {altre} chiavi attive: le vedi tutte in admin → "
                "Assistente AI → chiavi dell'assistente.\n"
            )
