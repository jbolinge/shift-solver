"""Schedule export views for downloading solver results."""

import json
import tempfile
from pathlib import Path

from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render

from core.converters import solver_run_to_schedule
from core.models import SolverRun

VALID_FORMATS = {"excel", "json"}


def export_page(request: HttpRequest, pk: int) -> HttpResponse:
    """Display the export options page."""
    solver_run = get_object_or_404(SolverRun, pk=pk)
    return render(
        request,
        "io/export_page.html",
        {
            "run": solver_run,
            "req": solver_run.schedule_request,
        },
    )


def export_download(
    request: HttpRequest,  # noqa: ARG001
    pk: int,
    fmt: str,
) -> HttpResponse:
    """Download solver results in the specified format."""
    solver_run = get_object_or_404(SolverRun, pk=pk)

    if fmt not in VALID_FORMATS:
        return HttpResponse(
            f"Unsupported export format: {fmt}. Valid formats: {', '.join(sorted(VALID_FORMATS))}",
            status=400,
        )

    if fmt == "excel":
        return _export_excel(solver_run)
    elif fmt == "json":
        return _export_json(solver_run)

    return HttpResponse("Unknown format", status=400)


def _export_excel(solver_run: SolverRun) -> HttpResponse:
    """Export schedule as Excel file."""
    schedule = solver_run_to_schedule(solver_run)

    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        from shift_solver.io import ExcelExporter

        exporter = ExcelExporter()
        exporter.export_schedule(schedule, tmp_path)

        with open(tmp_path, "rb") as f:
            content = f.read()
    finally:
        tmp_path.unlink(missing_ok=True)

    response = HttpResponse(
        content,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = (
        f'attachment; filename="schedule-run-{solver_run.pk}.xlsx"'
    )
    return response


def _export_json(solver_run: SolverRun) -> HttpResponse:
    """Export schedule as JSON file."""
    assignments = solver_run.assignments.select_related(
        "worker", "shift_type"
    ).all()

    data = {
        "solver_run_id": solver_run.pk,
        "schedule_request": solver_run.schedule_request.name,
        "status": solver_run.status,
        "result": solver_run.result_json,
        "assignments": [
            {
                "worker_id": a.worker.worker_id,
                "worker_name": a.worker.name,
                "shift_type_id": a.shift_type.shift_type_id,
                "shift_type_name": a.shift_type.name,
                "date": a.date.isoformat(),
            }
            for a in assignments
        ],
    }

    content = json.dumps(data, indent=2, default=str)
    response = HttpResponse(content, content_type="application/json")
    response["Content-Disposition"] = (
        f'attachment; filename="schedule-run-{solver_run.pk}.json"'
    )
    return response
