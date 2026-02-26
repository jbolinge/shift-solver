"""Plotly chart embedding and export views."""

import io
import zipfile
from collections.abc import Callable
from typing import Any

from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render

from core.converters import solver_run_to_schedule
from core.models import SolverRun

# Lazy import chart functions to avoid import issues at module level
_CHART_TYPES: dict[str, str] = {
    "heatmap": "shift_solver.io.plotly_handler.charts.heatmap",
    "gantt": "shift_solver.io.plotly_handler.charts.gantt",
    "fairness": "shift_solver.io.plotly_handler.charts.fairness",
    "sunburst": "shift_solver.io.plotly_handler.charts.sunburst",
    "coverage": "shift_solver.io.plotly_handler.charts.coverage",
}

_CHART_FUNC_NAMES: dict[str, str] = {
    "heatmap": "create_heatmap",
    "gantt": "create_gantt",
    "fairness": "create_fairness_chart",
    "sunburst": "create_sunburst",
    "coverage": "create_coverage_chart",
}

_CHART_LABELS: dict[str, str] = {
    "heatmap": "Heatmap",
    "gantt": "Gantt",
    "fairness": "Fairness",
    "sunburst": "Sunburst",
    "coverage": "Coverage",
}


def _get_chart_func(chart_type: str) -> Callable[..., Any]:
    """Import and return the chart creation function for a chart type."""
    import importlib

    module_path = _CHART_TYPES.get(chart_type)
    func_name = _CHART_FUNC_NAMES.get(chart_type)
    if not module_path or not func_name:
        raise Http404(f"Unknown chart type: {chart_type}")
    module = importlib.import_module(module_path)
    return getattr(module, func_name)  # type: ignore[no-any-return]


def _generate_chart_html(solver_run: SolverRun, chart_type: str) -> str:
    """Generate Plotly chart HTML for a solver run."""
    schedule = solver_run_to_schedule(solver_run)
    chart_func = _get_chart_func(chart_type)
    fig = chart_func(schedule)
    return fig.to_html(include_plotlyjs="cdn", full_html=False)  # type: ignore[no-any-return]


def chart_page(request: HttpRequest, pk: int) -> HttpResponse:
    """Display the analytics page with tabbed Plotly charts."""
    solver_run = get_object_or_404(SolverRun, pk=pk)

    # Generate default chart (heatmap)
    default_chart = "heatmap"
    chart_html = _generate_chart_html(solver_run, default_chart)

    return render(
        request,
        "plotly/chart_page.html",
        {
            "run": solver_run,
            "req": solver_run.schedule_request,
            "chart_types": _CHART_LABELS,
            "active_chart": default_chart,
            "chart_html": chart_html,
        },
    )


def chart_view(request: HttpRequest, pk: int, chart_type: str) -> HttpResponse:
    """Return a single chart as HTML partial for HTMX tab switching."""
    solver_run = get_object_or_404(SolverRun, pk=pk)

    if chart_type not in _CHART_TYPES:
        raise Http404(f"Unknown chart type: {chart_type}")

    chart_html = _generate_chart_html(solver_run, chart_type)

    return render(
        request,
        "plotly/chart_embed.html",
        {
            "chart_html": chart_html,
            "chart_type": chart_type,
            "chart_label": _CHART_LABELS.get(chart_type, chart_type),
        },
    )


def chart_download(request: HttpRequest, pk: int) -> HttpResponse:  # noqa: ARG001
    """Download all charts as a ZIP bundle."""
    solver_run = get_object_or_404(SolverRun, pk=pk)
    schedule = solver_run_to_schedule(solver_run)

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for chart_type in _CHART_TYPES:
            chart_func = _get_chart_func(chart_type)
            fig = chart_func(schedule)
            html = fig.to_html(include_plotlyjs="cdn", full_html=True)
            zf.writestr(f"{chart_type}.html", html)

    buffer.seek(0)
    response = HttpResponse(buffer.read(), content_type="application/zip")
    response["Content-Disposition"] = (
        f'attachment; filename="charts-run-{solver_run.pk}.zip"'
    )
    return response


def chart_download_single(
    request: HttpRequest,  # noqa: ARG001
    pk: int,
    chart_type: str,
) -> HttpResponse:
    """Download a single chart as an HTML file."""
    solver_run = get_object_or_404(SolverRun, pk=pk)

    if chart_type not in _CHART_TYPES:
        raise Http404(f"Unknown chart type: {chart_type}")

    schedule = solver_run_to_schedule(solver_run)
    chart_func = _get_chart_func(chart_type)
    fig = chart_func(schedule)
    html = fig.to_html(include_plotlyjs="cdn", full_html=True)

    response = HttpResponse(html, content_type="text/html")
    response["Content-Disposition"] = (
        f'attachment; filename="{chart_type}-run-{solver_run.pk}.html"'
    )
    return response
