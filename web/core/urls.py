"""URL patterns for the core app."""

from django.urls import path

from core.views.worker_views import (
    worker_create,
    worker_delete,
    worker_list,
    worker_update,
)

urlpatterns = [
    path("workers/", worker_list, name="worker-list"),
    path("workers/create/", worker_create, name="worker-create"),
    path("workers/<int:pk>/edit/", worker_update, name="worker-update"),
    path("workers/<int:pk>/delete/", worker_delete, name="worker-delete"),
]
