"""ScheduleRequest CRUD views with HTMX support."""

from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from core.forms import ScheduleRequestForm
from core.models import ScheduleRequest


def _is_htmx(request: HttpRequest) -> bool:
    """Check if the request was made via HTMX."""
    return request.headers.get("HX-Request") == "true"


def request_list(request: HttpRequest) -> HttpResponse:
    """List all schedule requests."""
    requests = ScheduleRequest.objects.all()
    return render(
        request, "requests/request_list.html", {"requests": requests}
    )


def request_create(request: HttpRequest) -> HttpResponse:
    """Create a new schedule request."""
    if request.method == "POST":
        form = ScheduleRequestForm(request.POST)
        if form.is_valid():
            schedule_request = form.save()
            if _is_htmx(request):
                return render(
                    request,
                    "requests/request_row.html",
                    {"req": schedule_request},
                )
            return redirect("request-list")
    else:
        form = ScheduleRequestForm()

    template = "requests/request_form.html"
    context = {"form": form, "title": "Create Schedule Request"}
    if _is_htmx(request):
        return render(request, template, context)
    return render(request, "requests/request_form_page.html", context)


def request_detail(request: HttpRequest, pk: int) -> HttpResponse:
    """Show schedule request details."""
    schedule_request = get_object_or_404(ScheduleRequest, pk=pk)
    workers = schedule_request.workers.all()
    shift_types = schedule_request.shift_types.all()
    return render(
        request,
        "requests/request_detail.html",
        {
            "req": schedule_request,
            "workers": workers,
            "shift_types": shift_types,
        },
    )


def request_update(request: HttpRequest, pk: int) -> HttpResponse:
    """Update an existing schedule request."""
    schedule_request = get_object_or_404(ScheduleRequest, pk=pk)

    if request.method == "POST":
        form = ScheduleRequestForm(request.POST, instance=schedule_request)
        if form.is_valid():
            schedule_request = form.save()
            if _is_htmx(request):
                return render(
                    request,
                    "requests/request_row.html",
                    {"req": schedule_request},
                )
            return redirect("request-detail", pk=schedule_request.pk)
    else:
        form = ScheduleRequestForm(instance=schedule_request)

    template = "requests/request_form.html"
    context = {
        "form": form,
        "req": schedule_request,
        "title": "Edit Schedule Request",
    }
    if _is_htmx(request):
        return render(request, template, context)
    return render(request, "requests/request_form_page.html", context)


def request_delete(request: HttpRequest, pk: int) -> HttpResponse:
    """Delete a schedule request."""
    schedule_request = get_object_or_404(ScheduleRequest, pk=pk)

    if request.method == "POST":
        schedule_request.delete()
        if _is_htmx(request):
            return HttpResponse("")
        return redirect("request-list")

    return render(
        request,
        "requests/request_confirm_delete.html",
        {"req": schedule_request},
    )
