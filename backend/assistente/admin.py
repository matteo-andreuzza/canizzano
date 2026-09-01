"""
Dove si prende la chiave: admin → «Assistente AI» → «chiavi dell'assistente».

La pagina di una chiave non e' un modulo da compilare: e' un foglio di
istruzioni da copiare. Il campo importante e' in sola lettura — la chiave la
genera il CMS — e sotto ci sono i comandi gia' pronti per i client piu'
diffusi, perche' l'alternativa e' che qualcuno li ricomponga a mano
sbagliando l'indirizzo.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from .collegamento import comando_claude_code, configurazione_json, indirizzo_mcp, prova_curl
from .models import ChiaveAssistente


@admin.register(ChiaveAssistente)
class ChiaveAssistenteAdmin(admin.ModelAdmin):
    list_display = ("nome", "attiva", "sola_lettura", "ultimo_uso", "creata_il")
    list_filter = ("attiva", "sola_lettura")
    readonly_fields = ("istruzioni", "chiave_leggibile", "creata_il", "ultimo_uso")
    fieldsets = (
        (
            "Come si collega l'agente",
            {
                "description": (
                    "Copia questi valori nel tuo assistente. La chiave vale come una "
                    "password: chi ce l'ha può cambiare il sito."
                ),
                "fields": ("chiave_leggibile", "istruzioni"),
            },
        ),
        (None, {"fields": ("nome", "attiva", "sola_lettura")}),
        ("Storia", {"fields": ("creata_il", "ultimo_uso")}),
    )

    def get_fieldsets(self, request, obj=None):
        # Finche' la chiave non esiste non c'e' niente da copiare: si chiede
        # solo il nome, e le istruzioni compaiono subito dopo il salvataggio.
        if obj is None:
            return ((None, {"fields": ("nome", "attiva", "sola_lettura")}),)
        return super().get_fieldsets(request, obj)

    @admin.display(description="chiave")
    def chiave_leggibile(self, obj: ChiaveAssistente) -> str:
        return format_html(
            '<code style="user-select:all;font-size:15px;background:#f3f0ea;'
            'padding:6px 10px;border-radius:8px;display:inline-block">{}</code>'
            '<p class="help">Clicca sulla chiave per selezionarla tutta.</p>',
            obj.chiave,
        )

    @admin.display(description="istruzioni")
    def istruzioni(self, obj: ChiaveAssistente) -> str:
        indirizzo = indirizzo_mcp()
        stile = (
            "background:#f3f0ea;padding:12px 14px;border-radius:10px;"
            "white-space:pre-wrap;user-select:all;font-size:13px;line-height:1.5"
        )
        return format_html(
            "<p><b>Indirizzo del server:</b> <code style='user-select:all'>{indirizzo}</code></p>"
            "<p><b>Claude Code</b> — una riga nel terminale:</p><pre style='{stile}'>{claude}</pre>"
            "<p><b>Claude Desktop, Cursor e simili</b> — nel file di configurazione MCP:</p>"
            "<pre style='{stile}'>{json}</pre>"
            "<p><b>Client che accettano solo un indirizzo</b> (niente intestazioni):</p>"
            "<pre style='{stile}'>{url_chiave}</pre>"
            "<p class='help'>Funziona, ma così la chiave finisce nei log del server: "
            "preferisci l'intestazione «Authorization» quando il client la supporta.</p>"
            "<p><b>Prova che risponda:</b></p><pre style='{stile}'>{curl}</pre>"
            "{avviso}",
            indirizzo=indirizzo,
            stile=stile,
            claude=comando_claude_code(obj.chiave, indirizzo),
            json=configurazione_json(obj.chiave, indirizzo),
            url_chiave=f"{indirizzo}?chiave={obj.chiave}",
            curl=prova_curl(obj.chiave, indirizzo),
            avviso=self._avviso(obj),
        )

    @staticmethod
    def _avviso(obj: ChiaveAssistente):
        if not obj.attiva:
            return mark_safe(
                "<p style='color:#8c491a'><b>Questa chiave è revocata:</b> l'agente "
                "riceve «401» finché non rimetti la spunta «attiva».</p>"
            )
        if obj.sola_lettura:
            return mark_safe(
                "<p style='color:#8c491a'><b>Sola lettura:</b> l'agente può guardare il "
                "sito ma non modificarlo.</p>"
            )
        return ""
