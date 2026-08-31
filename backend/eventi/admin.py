"""Pannello di redazione: e' qui che il quartiere aggiorna il sito."""

from django.contrib import admin
from django.utils.html import format_html

from .models import (
    Album,
    Articolo,
    Attivita,
    DettaglioArticolo,
    Edizione,
    Evento,
    Foto,
    Giornata,
    ImpostazioniSito,
    Luogo,
)


def anteprima_indirizzo(indirizzo: str, altezza: int = 120) -> str:
    """Anteprima di un'immagine, sia caricata qui sia ospitata altrove."""
    if not indirizzo:
        return "—"
    return format_html(
        '<img src="{}" style="max-height:{}px;border-radius:10px">', indirizzo, altezza
    )


def anteprima_immagine(campo, altezza: int = 120) -> str:
    return anteprima_indirizzo(campo.url if campo else "", altezza)


class EventoInline(admin.TabularInline):
    model = Evento
    extra = 0
    fields = ("titolo", "inizio", "fine", "luogo", "categoria", "in_evidenza", "pubblicato")
    show_change_link = True
    ordering = ("inizio",)


class FotoInline(admin.TabularInline):
    model = Foto
    extra = 0
    fields = ("immagine", "url_esterna", "raccolta", "didascalia", "ordine", "pubblicato")


@admin.register(ImpostazioniSito)
class ImpostazioniSitoAdmin(admin.ModelAdmin):
    """Un solo record: gli interruttori delle sezioni condizionali."""

    fieldsets = (
        (
            "Banner in home — l'appuntamento del momento",
            {
                "description": (
                    "La fascia terracotta in cima alla home: la prima cosa che vede "
                    "chi arriva. Usala per l'appuntamento piu' imminente — la sagra, "
                    "le iscrizioni al Grest o al catechismo, una serata speciale."
                ),
                "fields": (
                    "mostra_banner_sagra",
                    "banner_occhiello",
                    "banner_titolo",
                    "banner_testo",
                    "banner_collegamento",
                    "banner_etichetta_bottone",
                ),
            },
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
    list_display = (
        "titolo", "attivita", "inizio", "dove_mostrato", "ha_articolo", "in_evidenza", "pubblicato"
    )
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

    @admin.display(description="pagina dedicata", boolean=True)
    def ha_articolo(self, obj: Evento) -> bool:
        return hasattr(obj, "articolo")


@admin.register(Foto)
class FotoAdmin(admin.ModelAdmin):
    list_display = (
        "__str__", "raccolta", "attivita", "album", "articolo", "dove_sta",
        "ordine", "pubblicato", "miniatura",
    )
    list_editable = ("ordine", "pubblicato")
    list_filter = ("raccolta", "attivita", "album", "pubblicato")
    search_fields = ("didascalia", "url_esterna")
    readonly_fields = ("miniatura",)
    fieldsets = (
        ("Immagine", {
            "fields": ("immagine", "url_esterna", "miniatura", "testo_alternativo"),
            "description": (
                "Carica il file <em>oppure</em> incolla l'indirizzo dell'immagine su "
                "un servizio esterno. Per l'archivio storico usa sempre il link: lo "
                "spazio sull'hosting non basterebbe."
            ),
        }),
        ("Dove compare", {"fields": ("raccolta", "attivita", "articolo", "album")}),
        ("Testi", {"fields": ("didascalia", "anno")}),
        ("Pubblicazione", {"fields": ("ordine", "pubblicato")}),
    )

    @admin.display(description="anteprima")
    def miniatura(self, obj: Foto) -> str:
        return anteprima_indirizzo(obj.sorgente, 80)

    @admin.display(description="ospitata")
    def dove_sta(self, obj: Foto) -> str:
        return "hosting" if obj.immagine else "cloud"


@admin.register(Luogo)
class LuogoAdmin(admin.ModelAdmin):
    list_display = ("nome", "indirizzo")
    search_fields = ("nome", "indirizzo")


class DettaglioArticoloInline(admin.TabularInline):
    model = DettaglioArticolo
    extra = 3
    fields = ("etichetta", "valore", "ordine")


class FotoArticoloInline(admin.TabularInline):
    model = Foto
    fk_name = "articolo"
    extra = 0
    fields = ("immagine", "url_esterna", "didascalia", "testo_alternativo", "ordine", "pubblicato")
    verbose_name = "foto dell'articolo"
    verbose_name_plural = "foto dell'articolo"


@admin.register(Articolo)
class ArticoloAdmin(admin.ModelAdmin):
    """
    La pagina di approfondimento di un evento: si crea solo quando serve.

    «Apertura degli stand» non ne ha bisogno; «Gita sul Cansiglio» o «Ama il
    tuo quartiere» si', perche' hanno un ritrovo, una quota e una storia.
    """

    list_display = ("intestazione", "evento", "data_pubblicazione", "pubblicato", "indirizzo")
    list_filter = ("pubblicato", "identita", "evento__attivita")
    search_fields = ("titolo", "sottotitolo", "corpo", "evento__titolo")
    autocomplete_fields = ("evento",)
    prepopulated_fields = {"slug": ("titolo",)}
    inlines = (DettaglioArticoloInline, FotoArticoloInline)
    fieldsets = (
        (None, {"fields": ("evento", "slug", "occhiello", "titolo", "sottotitolo")}),
        ("Il testo", {
            "fields": ("corpo",),
            "description": (
                "Riga vuota = nuovo paragrafo · «## » = sottotitolo · "
                "«- » = voce di elenco · «&gt; » = nota in evidenza."
            ),
        }),
        ("Copertina", {"fields": ("copertina", "copertina_url", "anteprima", "copertina_alt")}),
        ("Aspetto", {"fields": ("identita", "tono")}),
        ("Pubblicazione", {"fields": ("firma", "data_pubblicazione", "pubblicato")}),
    )
    readonly_fields = ("anteprima",)

    @admin.display(description="anteprima")
    def anteprima(self, obj: Articolo) -> str:
        return anteprima_indirizzo(obj.copertina_sorgente, 160)

    @admin.display(description="indirizzo sul sito")
    def indirizzo(self, obj: Articolo) -> str:
        return f"/eventi/{obj.slug}"


class FotoAlbumInline(admin.TabularInline):
    model = Foto
    fk_name = "album"
    extra = 0
    fields = ("url_esterna", "immagine", "didascalia", "anno", "ordine", "pubblicato")
    verbose_name = "foto dell'album"
    verbose_name_plural = "foto dell'album"


@admin.register(Album)
class AlbumAdmin(admin.ModelAdmin):
    """L'archivio storico: le foto stanno su un servizio esterno, qui i link."""

    list_display = ("titolo", "anno", "periodo", "numero_foto", "ordine", "pubblicato")
    list_editable = ("ordine", "pubblicato")
    list_filter = ("pubblicato", "attivita")
    search_fields = ("titolo", "descrizione")
    prepopulated_fields = {"slug": ("titolo",)}
    inlines = (FotoAlbumInline,)
    fieldsets = (
        (None, {"fields": ("titolo", "slug", "anno", "periodo", "descrizione")}),
        ("Copertina", {"fields": ("copertina_url", "copertina", "anteprima", "copertina_alt")}),
        ("Collegamenti", {
            "fields": ("attivita", "album_url"),
            "description": (
                "«Album completo» rimanda al servizio che ospita le foto "
                "(Google Foto, Flickr, Immich…)."
            ),
        }),
        ("Pubblicazione", {"fields": ("ordine", "pubblicato")}),
    )
    readonly_fields = ("anteprima",)

    @admin.display(description="anteprima")
    def anteprima(self, obj: Album) -> str:
        return anteprima_indirizzo(obj.copertina_sorgente, 160)

    @admin.display(description="foto")
    def numero_foto(self, obj: Album) -> int:
        return obj.foto.count()
