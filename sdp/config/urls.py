from django.contrib.auth.decorators import login_required
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

# DRF views are exempt from LoginRequiredMiddleware (and drf-spectacular defaults to AllowAny),
# so the API docs are gated explicitly here.
urlpatterns = [
    path("", include("predictor.urls")),
    path("api/schema/", login_required(SpectacularAPIView.as_view()), name="schema"),
    path("api/docs/", login_required(SpectacularSwaggerView.as_view(url_name="schema")), name="swagger-ui"),
]
