"""
La chiave con cui un agente entra nel CMS.

Non c'e' un utente e una password: un agente non compila moduli. C'e' una
chiave lunga da mettere in un'intestazione HTTP, che si crea e si revoca
dall'admin — «Assistente AI → chiavi». Chi ha la chiave puo' fare quello che
farebbe un redattore, quindi si tratta come una password: una per ogni
agente, cosi' si puo' spegnere quella sbagliata senza spegnere le altre.
"""

from __future__ import annotations

import secrets

from django.db import models
from django.utils import timezone


def genera_chiave() -> str:
    """Una chiave nuova: 43 caratteri, casuali sul serio."""
    return secrets.token_urlsafe(32)


class ChiaveAssistente(models.Model):
    nome = models.CharField(
        max_length=80,
        help_text="A chi la dai: «Claude sul portatile», «l'assistente del telefono»…",
    )
    chiave = models.CharField(
        max_length=64,
        unique=True,
        default=genera_chiave,
        editable=False,
        help_text="Generata dal CMS: si copia, non si sceglie.",
    )
    attiva = models.BooleanField(
        default=True,
        help_text="Togli la spunta per revocarla: l'agente smette di entrare, subito.",
    )
    sola_lettura = models.BooleanField(
        default=False,
        help_text=(
            "L'agente può guardare il sito ma non cambiarlo. Utile per provare un "
            "assistente nuovo senza rischiare niente."
        ),
    )
    creata_il = models.DateTimeField(auto_now_add=True)
    ultimo_uso = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        verbose_name = "chiave dell'assistente"
        verbose_name_plural = "chiavi dell'assistente"
        ordering = ("-creata_il",)

    def __str__(self) -> str:
        return self.nome or f"chiave #{self.pk}"

    @classmethod
    def riconosci(cls, presentata: str) -> "ChiaveAssistente | None":
        """
        La chiave presentata, se e' una delle nostre.

        Il confronto e' a tempo costante: le chiavi sono poche e il paragone
        ingenuo (``==``) racconta, a chi sa ascoltare, quanti caratteri ha
        indovinato.
        """
        if not presentata:
            return None
        for chiave in cls.objects.filter(attiva=True):
            if secrets.compare_digest(chiave.chiave, presentata):
                return chiave
        return None

    def registra_uso(self) -> None:
        """Segna che e' stata usata, senza toccare il resto del record."""
        adesso = timezone.now()
        type(self).objects.filter(pk=self.pk).update(ultimo_uso=adesso)
        self.ultimo_uso = adesso
