"""Solver execution views: launch, progress tracking, and results."""

from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from core.models import ScheduleRequest, SolverRun, SolverSettings, Worker
from core.solver_runner import SolverRunner


def _is_htmx(request: HttpRequest) -> bool:
    """Check if the request was made via HTMX."""
    return request.headers.get("HX-Request") == "true"


def solve_launch(request: HttpRequest, pk: int) -> HttpResponse:
    """Launch a solver run for a schedule request."""
    schedule_request = get_object_or_404(ScheduleRequest, pk=pk)

    if request.method == "POST":
        # Validate request has workers
        has_workers = schedule_request.workers.exists() or Worker.objects.filter(
            is_active=True
        ).exists()
        has_shifts = schedule_request.shift_types.exists()

        errors = []
        if not has_workers:
            errors.append("No workers available. Add workers before solving.")
        if not has_shifts:
            errors.append("No shift types assigned. Add shift types before solving.")

        if errors:
            return render(
                request,
                "solver/solve_launch.html",
                {"req": schedule_request, "errors": errors},
            )

        # Ensure solver settings exist
        SolverSettings.objects.get_or_create(schedule_request=schedule_request)

        # Create solver run and start background execution
        solver_run = SolverRun.objects.create(
            schedule_request=schedule_request, status="pending"
        )
        runner = SolverRunner(solver_run_id=solver_run.id)
        runner.run()

        return redirect("solve-progress", pk=solver_run.pk)

    # GET: show launch confirmation
    workers = schedule_request.workers.all()
    shift_types = schedule_request.shift_types.all()
    return render(
        request,
        "solver/solve_launch.html",
        {
            "req": schedule_request,
            "workers": workers,
            "shift_types": shift_types,
        },
    )


def solve_progress(request: HttpRequest, pk: int) -> HttpResponse:
    """Show solver progress tracking page."""
    solver_run = get_object_or_404(SolverRun, pk=pk)
    return render(
        request,
        "solver/solve_progress.html",
        {"run": solver_run, "req": solver_run.schedule_request},
    )


def solve_progress_bar(request: HttpRequest, pk: int) -> HttpResponse:
    """Return progress bar partial for HTMX polling."""
    solver_run = get_object_or_404(SolverRun, pk=pk)

    if solver_run.status in ("completed", "failed"):
        response = render(
            request,
            "solver/solve_progress_bar.html",
            {"run": solver_run},
        )
        response["HX-Redirect"] = f"/solver-runs/{solver_run.pk}/results/"
        return response

    return render(
        request,
        "solver/solve_progress_bar.html",
        {"run": solver_run},
    )


def solve_results(request: HttpRequest, pk: int) -> HttpResponse:
    """Show solver run results summary."""
    solver_run = get_object_or_404(SolverRun, pk=pk)
    assignments = solver_run.assignments.select_related("worker", "shift_type").all()
    assignment_count = assignments.count()

    # Get duration from result_json if available
    result_json = solver_run.result_json or {}
    solve_time = result_json.get("solve_time_seconds")
    objective_value = result_json.get("objective_value")
    status_name = result_json.get("status", solver_run.status)

    # Count assignments by shift type
    shift_counts: dict[str, int] = {}
    for assignment in assignments:
        name = assignment.shift_type.name
        shift_counts[name] = shift_counts.get(name, 0) + 1

    return render(
        request,
        "solver/solve_results.html",
        {
            "run": solver_run,
            "req": solver_run.schedule_request,
            "assignments": assignments,
            "assignment_count": assignment_count,
            "solve_time": solve_time,
            "objective_value": objective_value,
            "status_name": status_name,
            "shift_counts": shift_counts,
        },
    )
