"""Pannello di redazione: e' qui che il quartiere aggiorna il sito."""

from django.contrib import admin
from django.utils.html import format_html

from .models import Attivita, Edizione, Evento, Foto, Giornata, ImpostazioniSito, Luogo


def anteprima_immagine(campo, altezza: int = 120) -> str:
    if not campo:
        return "—"
    return format_html(
        '<img src="{}" style="max-height:{}px;border-radius:10px">', campo.url, altezza
    )


class EventoInline(admin.TabularInline):
    model = Evento
    extra = 0
    fields = ("titolo", "inizio", "fine", "luogo", "categoria", "in_evidenza", "pubblicato")
    show_change_link = True
    ordering = ("inizio",)


class FotoInline(admin.TabularInline):
    model = Foto
    extra = 0
    fields = ("immagine", "raccolta", "didascalia", "ordine", "pubblicato")


@admin.register(ImpostazioniSito)
class ImpostazioniSitoAdmin(admin.ModelAdmin):
    """Un solo record: gli interruttori delle sezioni condizionali."""

    fieldsets = (
        (
            "Banner della sagra in home",
            {"fields": ("mostra_banner_sagra", "banner_occhiello", "banner_titolo", "banner_testo")},
        ),
        (
            "Sagra",
            {
                "fields": (
                    "modalita_sagra",
                    "data_inizio_sagra",
                    "mostra_conto_rovescia",
                    "mostra_sponsor",
                )
            },
        ),
        ("Pro Loco", {"fields": ("mostra_galleria_proloco",)}),
        ("Grest", {"fields": ("iscrizioni_grest_aperte", "mostra_foto_grest")}),
    )

    def has_add_permission(self, request):
        return not ImpostazioniSito.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Attivita)
class AttivitaAdmin(admin.ModelAdmin):
    list_display = ("nome", "identita", "ordine", "in_menu", "in_home", "pubblicato", "numero_eventi")
    list_editable = ("ordine", "in_menu", "in_home", "pubblicato")
    list_filter = ("identita", "in_menu", "in_home", "pubblicato")
    search_fields = ("nome", "sottotitolo", "descrizione")
    prepopulated_fields = {"slug": ("nome",)}
    inlines = (EventoInline, FotoInline)
    fieldsets = (
        (None, {"fields": ("nome", "slug", "sottotitolo")}),
        ("Testi", {"fields": ("descrizione_breve", "descrizione")}),
        ("Aspetto", {"fields": ("identita", "icona", "tono", "sfondo_caldo")}),
        ("Card in home", {"fields": ("collegamento", "etichetta_collegamento")}),
        ("Immagine", {"fields": ("immagine", "anteprima", "immagine_alt")}),
        ("Contatti", {"fields": ("email", "telefono")}),
        ("Pubblicazione", {"fields": ("ordine", "in_menu", "in_home", "pubblicato")}),
    )
    readonly_fields = ("anteprima",)

    @admin.display(description="anteprima")
    def anteprima(self, obj: Attivita) -> str:
        return anteprima_immagine(obj.immagine)

    @admin.display(description="eventi")
    def numero_eventi(self, obj: Attivita) -> int:
        return obj.eventi.count()


class GiornataInline(admin.TabularInline):
    model = Giornata
    extra = 0
    fields = ("data", "titolo", "occhiello", "tono", "sfondo_chiaro", "pubblicato")
    ordering = ("data",)


@admin.register(Giornata)
class GiornataAdmin(admin.ModelAdmin):
    list_display = ("etichetta_giorno", "edizione", "data", "occhiello", "tono", "pubblicato")
    list_filter = ("edizione", "pubblicato")

    @admin.display(description="giornata", ordering="data")
    def etichetta_giorno(self, obj: Giornata) -> str:
        return obj.etichetta


@admin.register(Edizione)
class EdizioneAdmin(admin.ModelAdmin):
    list_display = ("nome_edizione", "attivita", "anno", "pubblicato")
    list_filter = ("attivita", "anno", "pubblicato")
    search_fields = ("titolo", "descrizione")
    inlines = (GiornataInline, EventoInline)

    @admin.display(description="edizione", ordering="anno")
    def nome_edizione(self, obj: Edizione) -> str:
        return obj.etichetta


@admin.register(Evento)
class EventoAdmin(admin.ModelAdmin):
    list_display = ("titolo", "attivita", "inizio", "dove_mostrato", "in_evidenza", "pubblicato")
    list_editable = ("in_evidenza", "pubblicato")
    list_filter = ("attivita", "edizione", "categoria", "in_evidenza", "risalto", "pubblicato")
    search_fields = ("titolo", "sommario", "descrizione", "piatto_del_giorno")
    date_hierarchy = "inizio"
    autocomplete_fields = ("luogo",)
    prepopulated_fields = {"slug": ("titolo",)}
    fieldsets = (
        (None, {"fields": ("attivita", "edizione", "titolo", "slug")}),
        ("Testi", {"fields": ("sommario", "descrizione", "categoria", "icona", "tono")}),
        ("Quando", {"fields": ("inizio", "fine", "tutto_il_giorno", "etichetta_data", "stagione_scelta")}),
        ("Dove", {"fields": ("luogo", "luogo_libero")}),
        ("Immagine", {"fields": ("immagine", "anteprima", "immagine_alt")}),
        (
            "Sagra e prenotazioni",
            {"fields": ("piatto_del_giorno", "ingresso", "prenotazione_entro")},
        ),
        ("Collegamento", {"fields": ("link", "link_etichetta")}),
        ("Pubblicazione", {"fields": ("in_evidenza", "risalto", "ordine", "pubblicato")}),
    )
    readonly_fields = ("anteprima",)

    @admin.display(description="anteprima")
    def anteprima(self, obj: Evento) -> str:
        return anteprima_immagine(obj.immagine, 160)

    @admin.display(description="dove")
    def dove_mostrato(self, obj: Evento) -> str:
        return obj.dove or "—"


@admin.register(Foto)
class FotoAdmin(admin.ModelAdmin):
    list_display = ("__str__", "raccolta", "attivita", "ordine", "pubblicato", "miniatura")
    list_editable = ("ordine", "pubblicato")
    list_filter = ("raccolta", "attivita", "pubblicato")
    search_fields = ("didascalia",)
    readonly_fields = ("miniatura",)

    @admin.display(description="anteprima")
    def miniatura(self, obj: Foto) -> str:
        return anteprima_immagine(obj.immagine, 80)


@admin.register(Luogo)
class LuogoAdmin(admin.ModelAdmin):
    list_display = ("nome", "indirizzo")
    search_fields = ("nome", "indirizzo")
