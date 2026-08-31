from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("attivita", views.AttivitaViewSet, basename="attivita")
router.register("edizioni", views.EdizioneViewSet, basename="edizione")
router.register("eventi", views.EventoViewSet, basename="evento")
router.register("giornate", views.GiornataViewSet, basename="giornata")
router.register("foto", views.FotoViewSet, basename="foto")
router.register("articoli", views.ArticoloViewSet, basename="articolo")
router.register("album", views.AlbumViewSet, basename="album")
router.register("luoghi", views.LuogoViewSet, basename="luogo")

urlpatterns = [
    path("snapshot/", views.snapshot, name="snapshot"),
    path("", include(router.urls)),
]
