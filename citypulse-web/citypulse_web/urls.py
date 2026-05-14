from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from apps.api.views import health_check

urlpatterns = [
    path("admin/", admin.site.urls),
    # Portails distincts : chauffeur & client + logout
    path("", include("apps.accounts.urls")),
    # Allauth conserve pour admin et recover password uniquement
    path("accounts/", include("allauth.urls")),
    path("api/health/", health_check, name="api-health"),
    path("api/", include("apps.api.urls")),
    path("", include("apps.routes.urls")),
    path("", include("apps.tracking.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
