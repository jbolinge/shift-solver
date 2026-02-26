"""Root URL configuration for shift-solver web UI."""

from django.contrib import admin
from django.urls import include, path

from core.views import HomeView

urlpatterns = [
    path("", HomeView.as_view(), name="home"),
    path("", include("core.urls")),
    path("admin/", admin.site.urls),
]
