"""URL patterns for the core app."""

from django.urls import path

from core.views.availability_views import (
    availability_events,
    availability_page,
    availability_update,
)
from core.views.shift_views import (
    shift_create,
    shift_delete,
    shift_list,
    shift_update,
)
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
    path("shifts/", shift_list, name="shift-list"),
    path("shifts/create/", shift_create, name="shift-create"),
    path("shifts/<int:pk>/edit/", shift_update, name="shift-update"),
    path("shifts/<int:pk>/delete/", shift_delete, name="shift-delete"),
    path("availability/", availability_page, name="availability-page"),
    path("availability/events/", availability_events, name="availability-events"),
    path("availability/update/", availability_update, name="availability-update"),
]
