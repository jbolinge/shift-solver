"""WorkerRequest CRUD views scoped under a ScheduleRequest, with HTMX support."""

from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from core.forms import WorkerRequestForm
from core.models import ScheduleRequest, WorkerRequest


def _is_htmx(request: HttpRequest) -> bool:
    """Check if the request was made via HTMX."""
    return request.headers.get("HX-Request") == "true"


def worker_request_list(
    request: HttpRequest, schedule_request_pk: int
) -> HttpResponse:
    """List all worker requests for a schedule request."""
    schedule_request = get_object_or_404(ScheduleRequest, pk=schedule_request_pk)
    worker_requests = schedule_request.worker_requests.select_related(
        "worker", "shift_type"
    ).all()
    return render(
        request,
        "worker_requests/worker_request_list.html",
        {
            "req": schedule_request,
            "worker_requests": worker_requests,
        },
    )


def worker_request_create(
    request: HttpRequest, schedule_request_pk: int
) -> HttpResponse:
    """Create a new worker request for a schedule request."""
    schedule_request = get_object_or_404(ScheduleRequest, pk=schedule_request_pk)

    if request.method == "POST":
        form = WorkerRequestForm(request.POST, schedule_request=schedule_request)
        if form.is_valid():
            worker_request = form.save(commit=False)
            worker_request.schedule_request = schedule_request
            worker_request.save()
            if _is_htmx(request):
                return render(
                    request,
                    "worker_requests/worker_request_row.html",
                    {"wr": worker_request, "req": schedule_request},
                )
            return redirect(
                "worker-request-list",
                schedule_request_pk=schedule_request.pk,
            )
    else:
        form = WorkerRequestForm(
            schedule_request=schedule_request,
            initial={
                "start_date": schedule_request.start_date,
                "end_date": schedule_request.end_date,
            },
        )

    template = "worker_requests/worker_request_form.html"
    context = {"form": form, "req": schedule_request, "title": "Add Worker Request"}
    if _is_htmx(request):
        return render(request, template, context)
    return render(request, "worker_requests/worker_request_form_page.html", context)


def worker_request_update(
    request: HttpRequest, schedule_request_pk: int, pk: int
) -> HttpResponse:
    """Update an existing worker request."""
    schedule_request = get_object_or_404(ScheduleRequest, pk=schedule_request_pk)
    worker_request = get_object_or_404(
        WorkerRequest, pk=pk, schedule_request=schedule_request
    )

    if request.method == "POST":
        form = WorkerRequestForm(
            request.POST, instance=worker_request, schedule_request=schedule_request
        )
        if form.is_valid():
            worker_request = form.save()
            if _is_htmx(request):
                return render(
                    request,
                    "worker_requests/worker_request_row.html",
                    {"wr": worker_request, "req": schedule_request},
                )
            return redirect(
                "worker-request-list",
                schedule_request_pk=schedule_request.pk,
            )
    else:
        form = WorkerRequestForm(
            instance=worker_request, schedule_request=schedule_request
        )

    template = "worker_requests/worker_request_form.html"
    context = {
        "form": form,
        "req": schedule_request,
        "wr": worker_request,
        "title": "Edit Worker Request",
    }
    if _is_htmx(request):
        return render(request, template, context)
    return render(request, "worker_requests/worker_request_form_page.html", context)


def worker_request_delete(
    request: HttpRequest, schedule_request_pk: int, pk: int
) -> HttpResponse:
    """Delete a worker request."""
    schedule_request = get_object_or_404(ScheduleRequest, pk=schedule_request_pk)
    worker_request = get_object_or_404(
        WorkerRequest, pk=pk, schedule_request=schedule_request
    )

    if request.method == "POST":
        worker_request.delete()
        if _is_htmx(request):
            return HttpResponse("")
        return redirect(
            "worker-request-list",
            schedule_request_pk=schedule_request.pk,
        )

    return render(
        request,
        "worker_requests/worker_request_confirm_delete.html",
        {"wr": worker_request, "req": schedule_request},
    )
