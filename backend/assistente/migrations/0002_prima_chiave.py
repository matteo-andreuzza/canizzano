"""
La prima chiave, creata da sola al primo avvio.

Senza questa migrazione il primo collegamento sarebbe un giro a vuoto: apri
l'admin, non trovi niente, devi capire che una chiave va creata. Cosi'
invece la chiave c'e' gia' e l'unica cosa da fare e' copiarla — che e' quello
che uno si aspetta trovando una voce «Assistente AI» nel pannello.

Non si torna indietro: cancellare chiavi in un rollback spegnerebbe agenti
che stanno lavorando, e una chiave in piu' non ha mai fatto danni.
"""

import secrets

from django.db import migrations


def crea_prima_chiave(apps, schema_editor):
    ChiaveAssistente = apps.get_model("assistente", "ChiaveAssistente")
    if ChiaveAssistente.objects.exists():
        return
    ChiaveAssistente.objects.create(
        nome="Il mio assistente", chiave=secrets.token_urlsafe(32)
    )


class Migration(migrations.Migration):
    dependencies = [("assistente", "0001_initial")]

    operations = [migrations.RunPython(crea_prima_chiave, migrations.RunPython.noop)]
