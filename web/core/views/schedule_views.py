"""Schedule visualization views with FullCalendar integration."""

import datetime

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render

from core.models import ShiftType, SolverRun, Worker

# Consistent color palette for shift categories
CATEGORY_COLORS = [
    "#3b82f6",  # blue
    "#10b981",  # emerald
    "#f59e0b",  # amber
    "#ef4444",  # red
    "#8b5cf6",  # violet
    "#ec4899",  # pink
    "#14b8a6",  # teal
    "#f97316",  # orange
]


def _color_for_category(category: str, categories: list[str]) -> str:
    """Return a consistent color for a shift category."""
    idx = categories.index(category) if category in categories else len(categories)
    return CATEGORY_COLORS[idx % len(CATEGORY_COLORS)]


def schedule_view(request: HttpRequest, pk: int) -> HttpResponse:
    """Display the schedule calendar view for a solver run."""
    solver_run = get_object_or_404(SolverRun, pk=pk)
    assignments = solver_run.assignments.select_related(
        "worker", "shift_type"
    ).all()

    # Get unique workers and shift types from assignments
    worker_ids = assignments.values_list("worker_id", flat=True).distinct()
    shift_type_ids = assignments.values_list(
        "shift_type_id", flat=True
    ).distinct()
    workers = Worker.objects.filter(pk__in=worker_ids).order_by("name")
    shift_types = ShiftType.objects.filter(pk__in=shift_type_ids).order_by(
        "name"
    )

    return render(
        request,
        "schedule/schedule_view.html",
        {
            "run": solver_run,
            "req": solver_run.schedule_request,
            "workers": workers,
            "shift_types": shift_types,
        },
    )


def schedule_events(request: HttpRequest, pk: int) -> HttpResponse:
    """Return schedule assignments as FullCalendar-compatible JSON events."""
    solver_run = get_object_or_404(SolverRun, pk=pk)
    assignments = solver_run.assignments.select_related(
        "worker", "shift_type"
    ).all()

    # Apply filters
    worker_id = request.GET.get("worker_id")
    if worker_id:
        assignments = assignments.filter(worker_id=worker_id)

    shift_type_id = request.GET.get("shift_type_id")
    if shift_type_id:
        assignments = assignments.filter(shift_type_id=shift_type_id)

    # Build category color map
    categories = list(
        ShiftType.objects.filter(
            pk__in=solver_run.assignments.values_list(
                "shift_type_id", flat=True
            ).distinct()
        )
        .values_list("category", flat=True)
        .distinct()
    )

    events = []
    for assignment in assignments:
        shift = assignment.shift_type
        worker = assignment.worker

        # Calculate start/end datetime
        start_dt = datetime.datetime.combine(
            assignment.date, shift.start_time
        )
        end_dt = start_dt + datetime.timedelta(hours=shift.duration_hours)

        category = shift.category or "Uncategorized"
        color = _color_for_category(category, categories)

        events.append(
            {
                "title": f"{worker.name} - {shift.name}",
                "start": start_dt.isoformat(),
                "end": end_dt.isoformat(),
                "color": color,
                "extendedProps": {
                    "worker_id": worker.pk,
                    "worker_name": worker.name,
                    "shift_type": shift.name,
                    "shift_type_id": shift.pk,
                    "shift_category": category,
                },
            }
        )

    return JsonResponse(events, safe=False)
