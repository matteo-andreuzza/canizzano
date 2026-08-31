"""API di sola lettura consumate da Astro durante il build statico."""

from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import (
    Album,
    Articolo,
    Attivita,
    Edizione,
    Evento,
    Foto,
    Giornata,
    ImpostazioniSito,
    Luogo,
)
from .serializers import (
    AlbumSerializer,
    ArticoloSerializer,
    AttivitaSerializer,
    EdizioneSerializer,
    EventoSerializer,
    FotoSerializer,
    GiornataSerializer,
    ImpostazioniSitoSerializer,
    LuogoSerializer,
)


class AttivitaViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Attivita.visibili.all()
    serializer_class = AttivitaSerializer
    lookup_field = "slug"


class EdizioneViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Edizione.visibili.select_related("attivita")
    serializer_class = EdizioneSerializer
    lookup_field = "slug"


class EventoViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Evento.visibili.select_related("attivita", "edizione", "luogo", "articolo")
    serializer_class = EventoSerializer
    lookup_field = "slug"

    def get_queryset(self):
        qs = super().get_queryset()
        attivita = self.request.query_params.get("attivita")
        if attivita:
            qs = qs.filter(attivita__slug=attivita)
        if self.request.query_params.get("futuri") == "1":
            qs = qs.filter(inizio__gte=timezone.now())
        return qs


class GiornataViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Giornata.visibili.select_related("edizione")
    serializer_class = GiornataSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        edizione = self.request.query_params.get("edizione")
        return qs.filter(edizione__slug=edizione) if edizione else qs


class FotoViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Foto.visibili.select_related("attivita")
    serializer_class = FotoSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        raccolta = self.request.query_params.get("raccolta")
        return qs.filter(raccolta=raccolta) if raccolta else qs


class ArticoloViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Articolo.visibili.select_related("evento").prefetch_related("dettagli", "foto")
    serializer_class = ArticoloSerializer
    lookup_field = "slug"


class AlbumViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Album.visibili.select_related("attivita").prefetch_related("foto")
    serializer_class = AlbumSerializer
    lookup_field = "slug"


class LuogoViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Luogo.objects.all()
    serializer_class = LuogoSerializer


@api_view(["GET"])
def snapshot(request):
    """
    Tutti i contenuti pubblicati in una sola risposta.

    Astro fa una singola chiamata a build time invece di una per pagina:
    meno round-trip e uno stato coerente fra tutte le pagine generate.
    """
    return Response(
        {
            "generato_il": timezone.now(),
            "impostazioni": ImpostazioniSitoSerializer(ImpostazioniSito.caricate()).data,
            "attivita": AttivitaSerializer(Attivita.visibili.all(), many=True).data,
            "edizioni": EdizioneSerializer(
                Edizione.visibili.select_related("attivita"), many=True
            ).data,
            "eventi": EventoSerializer(
                Evento.visibili.select_related("attivita", "edizione", "luogo", "articolo"),
                many=True,
            ).data,
            "articoli": ArticoloSerializer(
                Articolo.visibili.select_related("evento").prefetch_related("dettagli", "foto"),
                many=True,
            ).data,
            "album": AlbumSerializer(
                Album.visibili.select_related("attivita").prefetch_related("foto"), many=True
            ).data,
            "giornate": GiornataSerializer(
                Giornata.visibili.select_related("edizione"), many=True
            ).data,
            "foto": FotoSerializer(Foto.visibili.select_related("attivita"), many=True).data,
            "luoghi": LuogoSerializer(Luogo.objects.all(), many=True).data,
        }
    )
