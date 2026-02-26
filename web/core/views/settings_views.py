"""SolverSettings views for configuring solver parameters per-request."""

from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render

from core.forms import SolverSettingsForm
from core.models import ScheduleRequest, SolverSettings


def _is_htmx(request: HttpRequest) -> bool:
    """Check if the request was made via HTMX."""
    return request.headers.get("HX-Request") == "true"


def _get_or_create_settings(schedule_request: ScheduleRequest) -> SolverSettings:
    """Get existing SolverSettings or create with defaults."""
    settings, _created = SolverSettings.objects.get_or_create(
        schedule_request=schedule_request,
    )
    return settings


def solver_settings(request: HttpRequest, pk: int) -> HttpResponse:
    """Display solver settings for a schedule request."""
    schedule_request = get_object_or_404(ScheduleRequest, pk=pk)
    settings = _get_or_create_settings(schedule_request)
    form = SolverSettingsForm(instance=settings)
    return render(
        request,
        "settings/solver_settings.html",
        {
            "req": schedule_request,
            "settings": settings,
            "form": form,
        },
    )


def solver_settings_edit(request: HttpRequest, pk: int) -> HttpResponse:
    """Update solver settings for a schedule request."""
    schedule_request = get_object_or_404(ScheduleRequest, pk=pk)
    settings = _get_or_create_settings(schedule_request)

    if request.method == "POST":
        form = SolverSettingsForm(request.POST, instance=settings)
        if form.is_valid():
            form.save()
            if _is_htmx(request):
                return render(
                    request,
                    "settings/settings_form.html",
                    {
                        "req": schedule_request,
                        "settings": settings,
                        "form": SolverSettingsForm(instance=settings),
                    },
                )
            return render(
                request,
                "settings/solver_settings.html",
                {
                    "req": schedule_request,
                    "settings": settings,
                    "form": SolverSettingsForm(instance=settings),
                },
            )
        # Form has errors -- re-render with errors
        return render(
            request,
            "settings/solver_settings.html",
            {
                "req": schedule_request,
                "settings": settings,
                "form": form,
            },
        )

    # GET on the edit URL just redirects to the settings page
    form = SolverSettingsForm(instance=settings)
    return render(
        request,
        "settings/solver_settings.html",
        {
            "req": schedule_request,
            "settings": settings,
            "form": form,
        },
    )
