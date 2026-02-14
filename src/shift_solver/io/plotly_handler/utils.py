"""Shared utilities for Plotly charts."""

from typing import Any

from shift_solver.models.schedule import Schedule
from shift_solver.models.worker import Worker

# 20 visually distinct colors for worker assignments
WORKER_COLORS = [
    "#1f77b4",
    "#ff7f0e",
    "#2ca02c",
    "#d62728",
    "#9467bd",
    "#8c564b",
    "#e377c2",
    "#7f7f7f",
    "#bcbd22",
    "#17becf",
    "#aec7e8",
    "#ffbb78",
    "#98df8a",
    "#ff9896",
    "#c5b0d5",
    "#c49c94",
    "#f7b6d2",
    "#c7c7c7",
    "#dbdb8d",
    "#9edae5",
]

CATEGORY_COLORS: dict[str, str] = {
    "day": "#4CAF50",
    "night": "#3F51B5",
    "weekend": "#FF9800",
    "evening": "#9C27B0",
}

_FALLBACK_COLOR = "#607D8B"


def get_worker_color_map(workers: list[Worker]) -> dict[str, str]:
    """Map worker IDs to consistent colors."""
    return {
        worker.id: WORKER_COLORS[i % len(WORKER_COLORS)]
        for i, worker in enumerate(workers)
    }


def get_category_color(category: str) -> str:
    """Get color for a shift category, with fallback for unknown categories."""
    return CATEGORY_COLORS.get(category, _FALLBACK_COLOR)


def get_default_layout(**overrides: Any) -> dict[str, Any]:
    """Base layout dict with font, margins, theme."""
    layout: dict[str, Any] = {
        "font": {"family": "Arial, sans-serif", "size": 12},
        "margin": {"l": 60, "r": 30, "t": 60, "b": 60},
        "template": "plotly_white",
    }
    layout.update(overrides)
    return layout


def flatten_assignments(schedule: Schedule) -> list[dict[str, Any]]:
    """Convert schedule to list of flat assignment records.

    Each record: {worker_id, worker_name, shift_type_id, category,
                  date, period_index, is_undesirable}
    """
    records: list[dict[str, Any]] = []
    shift_type_map = {st.id: st for st in schedule.shift_types}
    worker_map = {w.id: w for w in schedule.workers}

    for period in schedule.periods:
        for worker_id, shifts in period.assignments.items():
            worker = worker_map.get(worker_id)
            for shift in shifts:
                st = shift_type_map.get(shift.shift_type_id)
                records.append(
                    {
                        "worker_id": worker_id,
                        "worker_name": worker.name if worker else worker_id,
                        "shift_type_id": shift.shift_type_id,
                        "category": st.category if st else "unknown",
                        "date": shift.date,
                        "period_index": shift.period_index,
                        "is_undesirable": st.is_undesirable if st else False,
                    }
                )
    return records
