"""URL patterns for the core app."""

from django.urls import path

from core.views.availability_views import (
    availability_events,
    availability_page,
    availability_update,
)
from core.views.constraint_views import (
    constraint_list,
    constraint_seed,
    constraint_update,
)
from core.views.export_views import (
    export_download,
    export_page,
)
from core.views.import_views import (
    import_confirm,
    import_page,
    import_upload,
)
from core.views.plotly_views import (
    chart_download,
    chart_download_single,
    chart_page,
    chart_view,
)
from core.views.request_views import (
    request_create,
    request_delete,
    request_detail,
    request_list,
    request_update,
)
from core.views.schedule_views import (
    schedule_events,
    schedule_view,
)
from core.views.settings_views import (
    solver_settings,
    solver_settings_edit,
)
from core.views.shift_views import (
    shift_create,
    shift_delete,
    shift_list,
    shift_update,
)
from core.views.solver_views import (
    solve_launch,
    solve_progress,
    solve_progress_bar,
    solve_results,
)
from core.views.worker_request_views import (
    worker_request_create,
    worker_request_delete,
    worker_request_list,
    worker_request_update,
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
    path("constraints/", constraint_list, name="constraint-list"),
    path("constraints/<int:pk>/edit/", constraint_update, name="constraint-update"),
    path("constraints/seed/", constraint_seed, name="constraint-seed"),
    path("requests/", request_list, name="request-list"),
    path("requests/create/", request_create, name="request-create"),
    path("requests/<int:pk>/", request_detail, name="request-detail"),
    path("requests/<int:pk>/edit/", request_update, name="request-update"),
    path("requests/<int:pk>/delete/", request_delete, name="request-delete"),
    path(
        "requests/<int:schedule_request_pk>/worker-requests/",
        worker_request_list,
        name="worker-request-list",
    ),
    path(
        "requests/<int:schedule_request_pk>/worker-requests/create/",
        worker_request_create,
        name="worker-request-create",
    ),
    path(
        "requests/<int:schedule_request_pk>/worker-requests/<int:pk>/edit/",
        worker_request_update,
        name="worker-request-update",
    ),
    path(
        "requests/<int:schedule_request_pk>/worker-requests/<int:pk>/delete/",
        worker_request_delete,
        name="worker-request-delete",
    ),
    path("requests/<int:pk>/settings/", solver_settings, name="solver-settings"),
    path(
        "requests/<int:pk>/settings/edit/",
        solver_settings_edit,
        name="solver-settings-edit",
    ),
    path("requests/<int:pk>/solve/", solve_launch, name="solve-launch"),
    path(
        "solver-runs/<int:pk>/progress/", solve_progress, name="solve-progress"
    ),
    path(
        "solver-runs/<int:pk>/progress-bar/",
        solve_progress_bar,
        name="solve-progress-bar",
    ),
    path(
        "solver-runs/<int:pk>/results/", solve_results, name="solve-results"
    ),
    path(
        "solver-runs/<int:pk>/schedule/",
        schedule_view,
        name="schedule-view",
    ),
    path(
        "solver-runs/<int:pk>/schedule/events/",
        schedule_events,
        name="schedule-events",
    ),
    path(
        "solver-runs/<int:pk>/charts/",
        chart_page,
        name="chart-page",
    ),
    path(
        "solver-runs/<int:pk>/charts/download/",
        chart_download,
        name="chart-download",
    ),
    path(
        "solver-runs/<int:pk>/charts/download/<str:chart_type>/",
        chart_download_single,
        name="chart-download-single",
    ),
    path(
        "solver-runs/<int:pk>/charts/<str:chart_type>/",
        chart_view,
        name="chart-view",
    ),
    path("import/", import_page, name="import-page"),
    path("import/upload/", import_upload, name="import-upload"),
    path("import/confirm/", import_confirm, name="import-confirm"),
    path(
        "solver-runs/<int:pk>/export/",
        export_page,
        name="export-page",
    ),
    path(
        "solver-runs/<int:pk>/export/<str:fmt>/",
        export_download,
        name="export-download",
    ),
]
