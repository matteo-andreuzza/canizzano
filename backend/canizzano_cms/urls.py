"""
Rotte del CMS: pannello admin, API di sola lettura per il build Astro e la
rotta dell'assistente AI (server MCP).
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

from . import views

admin.site.site_header = "Canizzano — Redazione contenuti"
admin.site.site_title = "Canizzano CMS"
admin.site.index_title = "Contenuti del sito"

urlpatterns = [
    path("", RedirectView.as_view(url="/admin/", permanent=False)),
    path("admin/", admin.site.urls),
    # La dashboard della redazione e le due rotte che la alimentano: la prima
    # mette in coda un comando, le altre raccontano come sta andando.
    path("riservata/", views.pagina_riservata, name="pagina_riservata"),
    path("riservata/azione/", views.esegui_azione, name="esegui_azione"),
    path("riservata/stato/", views.stato_azione, name="stato_azione"),
    path("riservata/storico/", views.storico, name="storico_attivita"),
    path("api/", include("eventi.urls")),
    # Il server MCP risponde con e senza barra finale: i client MCP scrivono
    # l'indirizzo a mano, e una POST non si puo' redirigere senza perderla.
    path("mcp/", include("assistente.urls")),
    path("mcp", include("assistente.urls")),
]

# In locale il CMS serve anche i media, cosi' l'anteprima in admin funziona.
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
