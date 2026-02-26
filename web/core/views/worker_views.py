"""Worker CRUD views with HTMX support."""

from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from core.forms import WorkerForm
from core.models import Worker


def _is_htmx(request: HttpRequest) -> bool:
    """Check if the request was made via HTMX."""
    return request.headers.get("HX-Request") == "true"


def worker_list(request: HttpRequest) -> HttpResponse:
    """List all workers."""
    workers = Worker.objects.all()
    return render(request, "workers/worker_list.html", {"workers": workers})


def worker_create(request: HttpRequest) -> HttpResponse:
    """Create a new worker."""
    if request.method == "POST":
        form = WorkerForm(request.POST)
        if form.is_valid():
            worker = form.save()
            if _is_htmx(request):
                return render(
                    request,
                    "workers/worker_row.html",
                    {"worker": worker},
                )
            return redirect("worker-list")
    else:
        form = WorkerForm()

    template = "workers/worker_form.html"
    context = {"form": form, "title": "Add Worker"}
    if _is_htmx(request):
        return render(request, template, context)
    return render(request, "workers/worker_form_page.html", context)


def worker_update(request: HttpRequest, pk: int) -> HttpResponse:
    """Update an existing worker."""
    worker = get_object_or_404(Worker, pk=pk)

    if request.method == "POST":
        form = WorkerForm(request.POST, instance=worker)
        if form.is_valid():
            worker = form.save()
            if _is_htmx(request):
                return render(
                    request,
                    "workers/worker_row.html",
                    {"worker": worker},
                )
            return redirect("worker-list")
    else:
        form = WorkerForm(instance=worker)

    template = "workers/worker_form.html"
    context = {"form": form, "worker": worker, "title": "Edit Worker"}
    if _is_htmx(request):
        return render(request, template, context)
    return render(request, "workers/worker_form_page.html", context)


def worker_delete(request: HttpRequest, pk: int) -> HttpResponse:
    """Delete a worker."""
    worker = get_object_or_404(Worker, pk=pk)

    if request.method == "POST":
        worker.delete()
        if _is_htmx(request):
            return HttpResponse("")
        return redirect("worker-list")

    return render(
        request, "workers/worker_confirm_delete.html", {"worker": worker}
    )
