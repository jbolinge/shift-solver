"""ShiftType CRUD views with HTMX support."""

from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from core.forms import ShiftTypeForm
from core.models import ShiftType


def _is_htmx(request: HttpRequest) -> bool:
    """Check if the request was made via HTMX."""
    return request.headers.get("HX-Request") == "true"


def shift_list(request: HttpRequest) -> HttpResponse:
    """List all shift types."""
    shifts = ShiftType.objects.all()
    return render(request, "shifts/shift_list.html", {"shifts": shifts})


def shift_create(request: HttpRequest) -> HttpResponse:
    """Create a new shift type."""
    if request.method == "POST":
        form = ShiftTypeForm(request.POST)
        if form.is_valid():
            shift = form.save()
            if _is_htmx(request):
                return render(
                    request,
                    "shifts/shift_row.html",
                    {"shift": shift},
                )
            return redirect("shift-list")
    else:
        form = ShiftTypeForm()

    template = "shifts/shift_form.html"
    context = {"form": form, "title": "Add Shift Type"}
    if _is_htmx(request):
        return render(request, template, context)
    return render(request, "shifts/shift_form_page.html", context)


def shift_update(request: HttpRequest, pk: int) -> HttpResponse:
    """Update an existing shift type."""
    shift = get_object_or_404(ShiftType, pk=pk)

    if request.method == "POST":
        form = ShiftTypeForm(request.POST, instance=shift)
        if form.is_valid():
            shift = form.save()
            if _is_htmx(request):
                return render(
                    request,
                    "shifts/shift_row.html",
                    {"shift": shift},
                )
            return redirect("shift-list")
    else:
        form = ShiftTypeForm(instance=shift)

    template = "shifts/shift_form.html"
    context = {"form": form, "shift": shift, "title": "Edit Shift Type"}
    if _is_htmx(request):
        return render(request, template, context)
    return render(request, "shifts/shift_form_page.html", context)


def shift_delete(request: HttpRequest, pk: int) -> HttpResponse:
    """Delete a shift type."""
    shift = get_object_or_404(ShiftType, pk=pk)

    if request.method == "POST":
        shift.delete()
        if _is_htmx(request):
            return HttpResponse("")
        return redirect("shift-list")

    return render(
        request, "shifts/shift_confirm_delete.html", {"shift": shift}
    )
