"""Availability calendar views with FullCalendar + HTMX support."""

import datetime

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from core.models import Availability, Worker


def availability_page(request: HttpRequest) -> HttpResponse:
    """Render the availability calendar page with a worker selector."""
    workers = Worker.objects.filter(is_active=True)
    return render(
        request,
        "availability/availability_page.html",
        {"workers": workers},
    )


def availability_events(request: HttpRequest) -> HttpResponse:
    """Return availability entries as FullCalendar-compatible JSON events.

    Query params:
        worker_id: primary key of the worker (required)
        start: optional start date filter (ISO format)
        end: optional end date filter (ISO format)
    """
    worker_id = request.GET.get("worker_id")
    if not worker_id:
        return JsonResponse([], safe=False)

    entries = Availability.objects.filter(worker_id=worker_id)

    start = request.GET.get("start")
    end = request.GET.get("end")
    if start:
        entries = entries.filter(date__gte=start)
    if end:
        entries = entries.filter(date__lte=end)

    events = []
    for entry in entries:
        if entry.is_available:
            title = "Available"
            color = "#22c55e"
        else:
            title = "Unavailable"
            color = "#ef4444"

        events.append(
            {
                "title": title,
                "start": entry.date.isoformat(),
                "color": color,
                "extendedProps": {
                    "availability_id": entry.pk,
                    "worker_id": entry.worker_id,
                    "is_available": entry.is_available,
                    "preference": entry.preference,
                    "shift_type_id": entry.shift_type_id,
                },
            }
        )

    return JsonResponse(events, safe=False)


@csrf_exempt
@require_POST
def availability_update(request: HttpRequest) -> HttpResponse:
    """Create or toggle an availability entry for a worker on a date.

    POST params:
        worker_id: primary key of the worker (required)
        date: ISO date string (required)
        shift_type_id: primary key of the shift type (optional)
    """
    worker_id = request.POST.get("worker_id")
    date_str = request.POST.get("date")

    if not worker_id:
        return JsonResponse(
            {"error": "worker_id is required"}, status=400
        )
    if not date_str:
        return JsonResponse(
            {"error": "date is required"}, status=400
        )

    try:
        date = datetime.date.fromisoformat(date_str)
    except ValueError:
        return JsonResponse(
            {"error": "Invalid date format. Use YYYY-MM-DD."}, status=400
        )

    shift_type_id = request.POST.get("shift_type_id") or None

    lookup = {
        "worker_id": worker_id,
        "date": date,
        "shift_type_id": shift_type_id,
    }

    try:
        entry = Availability.objects.get(**lookup)
        entry.is_available = not entry.is_available
        entry.save()
    except Availability.DoesNotExist:
        entry = Availability.objects.create(
            **lookup, is_available=True
        )

    return JsonResponse(
        {
            "id": entry.pk,
            "is_available": entry.is_available,
            "date": entry.date.isoformat(),
        }
    )
