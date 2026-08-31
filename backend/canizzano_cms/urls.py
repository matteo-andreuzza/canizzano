"""Rotte del CMS: pannello admin + API di sola lettura per il build Astro."""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

admin.site.site_header = "Canizzano — Redazione contenuti"
admin.site.site_title = "Canizzano CMS"
admin.site.index_title = "Contenuti del sito"

urlpatterns = [
    path("", RedirectView.as_view(url="/admin/", permanent=False)),
    path("admin/", admin.site.urls),
    path("api/", include("eventi.urls")),
]

# In locale il CMS serve anche i media, cosi' l'anteprima in admin funziona.
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
