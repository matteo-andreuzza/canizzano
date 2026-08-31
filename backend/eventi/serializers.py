"""Serializzazione dei contenuti verso il builder Astro."""

from rest_framework import serializers

from .models import Attivita, Edizione, Evento, Foto, Giornata, ImpostazioniSito, Luogo


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
    immagine = serializers.SerializerMethodField()

    class Meta:
        model = Foto
        fields = (
            "id", "raccolta", "attivita", "immagine",
            "didascalia", "testo_alternativo", "ordine",
        )

    def get_immagine(self, obj: Foto) -> str | None:
        return percorso_media(obj.immagine)


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

    class Meta:
        model = Evento
        fields = (
            "id", "slug", "titolo", "sommario", "descrizione", "categoria", "icona",
            "inizio", "fine", "tutto_il_giorno", "etichetta_data", "stagione", "stagione_scelta", "tono",
            "attivita", "edizione", "luogo", "luogo_libero", "dove",
            "immagine", "immagine_alt",
            "piatto_del_giorno", "ingresso", "prenotazione_entro",
            "link", "link_etichetta", "in_evidenza", "risalto", "ordine",
        )

    def get_immagine(self, obj: Evento) -> str | None:
        return percorso_media(obj.immagine)


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
