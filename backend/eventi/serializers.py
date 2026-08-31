"""Serializzazione dei contenuti verso il builder Astro."""

from rest_framework import serializers

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


def percorso_media(campo) -> str | None:
    """URL relativa dell'immagine: sul sito statico i media stanno in /media/."""
    return campo.url if campo else None


class ImpostazioniSitoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ImpostazioniSito
        exclude = ("id",)


class LuogoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Luogo
        fields = ("id", "nome", "indirizzo", "mappa_url")


class FotoSerializer(serializers.ModelSerializer):
    attivita = serializers.SlugRelatedField(slug_field="slug", read_only=True)
    articolo = serializers.SlugRelatedField(slug_field="slug", read_only=True)
    album = serializers.SlugRelatedField(slug_field="slug", read_only=True)
    immagine = serializers.SerializerMethodField()

    class Meta:
        model = Foto
        fields = (
            "id", "raccolta", "attivita", "articolo", "album", "anno",
            "immagine", "url_esterna",
            "didascalia", "testo_alternativo", "ordine",
        )

    def get_immagine(self, obj: Foto) -> str | None:
        """Il file caricato se c'e', altrimenti il link al servizio esterno."""
        return percorso_media(obj.immagine) or obj.url_esterna or None


class GiornataSerializer(serializers.ModelSerializer):
    edizione = serializers.SlugRelatedField(slug_field="slug", read_only=True)
    etichetta = serializers.CharField(read_only=True)

    class Meta:
        model = Giornata
        fields = ("id", "edizione", "data", "titolo", "etichetta", "occhiello", "tono", "sfondo_chiaro")


class EventoSerializer(serializers.ModelSerializer):
    attivita = serializers.SlugRelatedField(slug_field="slug", read_only=True)
    edizione = serializers.SlugRelatedField(slug_field="slug", read_only=True)
    luogo = LuogoSerializer(read_only=True)
    dove = serializers.CharField(read_only=True)
    stagione = serializers.CharField(read_only=True)
    immagine = serializers.SerializerMethodField()
    articolo = serializers.SerializerMethodField()

    class Meta:
        model = Evento
        fields = (
            "id", "slug", "titolo", "sommario", "descrizione", "categoria", "icona",
            "inizio", "fine", "tutto_il_giorno", "etichetta_data", "stagione", "stagione_scelta", "tono",
            "attivita", "edizione", "luogo", "luogo_libero", "dove",
            "immagine", "immagine_alt",
            "piatto_del_giorno", "ingresso", "prenotazione_entro",
            "link", "link_etichetta", "in_evidenza", "risalto", "ordine",
            "articolo",
        )

    def get_immagine(self, obj: Evento) -> str | None:
        return percorso_media(obj.immagine)

    def get_articolo(self, obj: Evento) -> str | None:
        """Lo slug della pagina di approfondimento, quando l'evento ne ha una."""
        articolo = getattr(obj, "articolo", None)
        return articolo.slug if articolo and articolo.pubblicato else None


class EdizioneSerializer(serializers.ModelSerializer):
    attivita = serializers.SlugRelatedField(slug_field="slug", read_only=True)
    etichetta = serializers.CharField(read_only=True)
    immagine = serializers.SerializerMethodField()

    class Meta:
        model = Edizione
        fields = (
            "id", "slug", "anno", "titolo", "etichetta", "descrizione",
            "attivita", "immagine", "immagine_alt",
        )

    def get_immagine(self, obj: Edizione) -> str | None:
        return percorso_media(obj.immagine)


class AttivitaSerializer(serializers.ModelSerializer):
    immagine = serializers.SerializerMethodField()
    esterno = serializers.BooleanField(read_only=True)

    class Meta:
        model = Attivita
        fields = (
            "id", "slug", "nome", "sottotitolo", "descrizione", "descrizione_breve",
            "identita", "icona", "tono", "sfondo_caldo",
            "collegamento", "etichetta_collegamento", "esterno",
            "immagine", "immagine_alt", "email", "telefono",
            "ordine", "in_menu", "in_home",
        )

    def get_immagine(self, obj: Attivita) -> str | None:
        return percorso_media(obj.immagine)


class DettaglioArticoloSerializer(serializers.ModelSerializer):
    class Meta:
        model = DettaglioArticolo
        fields = ("id", "etichetta", "valore", "ordine")


class ArticoloSerializer(serializers.ModelSerializer):
    """L'articolo con tutto quello che serve a comporre la sua pagina."""

    evento = serializers.SlugRelatedField(slug_field="slug", read_only=True)
    intestazione = serializers.CharField(read_only=True)
    copertina = serializers.SerializerMethodField()
    dettagli = DettaglioArticoloSerializer(many=True, read_only=True)
    foto = serializers.SerializerMethodField()

    class Meta:
        model = Articolo
        fields = (
            "id", "slug", "evento", "occhiello", "titolo", "intestazione", "sottotitolo",
            "corpo", "copertina", "copertina_url", "copertina_alt",
            "identita", "tono", "firma", "data_pubblicazione",
            "dettagli", "foto",
        )

    def get_copertina(self, obj: Articolo) -> str | None:
        return percorso_media(obj.copertina) or obj.copertina_url or None

    def get_foto(self, obj: Articolo) -> list[dict]:
        return FotoSerializer(obj.foto.filter(pubblicato=True), many=True).data


class AlbumSerializer(serializers.ModelSerializer):
    """Una raccolta d'archivio: le foto stanno su un servizio esterno."""

    attivita = serializers.SlugRelatedField(slug_field="slug", read_only=True)
    etichetta = serializers.CharField(read_only=True)
    copertina = serializers.SerializerMethodField()
    foto = serializers.SerializerMethodField()

    class Meta:
        model = Album
        fields = (
            "id", "slug", "titolo", "etichetta", "anno", "periodo", "descrizione",
            "copertina", "copertina_url", "copertina_alt",
            "attivita", "album_url", "ordine", "foto",
        )

    def get_copertina(self, obj: Album) -> str | None:
        return percorso_media(obj.copertina) or obj.copertina_url or None

    def get_foto(self, obj: Album) -> list[dict]:
        return FotoSerializer(obj.foto.filter(pubblicato=True), many=True).data
