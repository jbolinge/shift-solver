"""Shared schedule reconstruction logic for CLI commands."""

from datetime import date, time
from typing import Any

from shift_solver.models import (
    PeriodAssignment,
    Schedule,
    ShiftInstance,
    ShiftType,
    Worker,
)


def infer_workers(schedule_data: dict[str, Any]) -> list[Worker]:
    """
    Infer workers from schedule JSON data.

    Args:
        schedule_data: Schedule JSON dict

    Returns:
        List of Worker objects with minimal info
    """
    worker_ids: set[str] = set()
    for period in schedule_data.get("periods", []):
        worker_ids.update(period.get("assignments", {}).keys())

    return [Worker(id=wid, name=wid) for wid in sorted(worker_ids)]


def infer_shift_types(schedule_data: dict[str, Any]) -> list[ShiftType]:
    """
    Infer shift types from schedule JSON data.

    Args:
        schedule_data: Schedule JSON dict

    Returns:
        List of ShiftType objects with minimal info
    """
    shift_type_ids: set[str] = set()
    for period in schedule_data.get("periods", []):
        for shift_list in period.get("assignments", {}).values():
            for a in shift_list:
                shift_type_ids.add(a.get("shift_type_id"))

    return [
        ShiftType(
            id=stid,
            name=stid,
            category="unknown",
            start_time=time(0, 0),
            end_time=time(8, 0),
            duration_hours=8.0,
            workers_required=1,
        )
        for stid in sorted(shift_type_ids)
    ]


def build_schedule_from_json(
    schedule_data: dict[str, Any],
    workers: list[Worker] | None = None,
    shift_types: list[ShiftType] | None = None,
) -> Schedule:
    """
    Build a Schedule object from JSON data.

    Args:
        schedule_data: Schedule JSON dict
        workers: Optional worker list (inferred if not provided)
        shift_types: Optional shift type list (inferred if not provided)

    Returns:
        Schedule object
    """
    # Use provided or infer
    if workers is None:
        workers = infer_workers(schedule_data)
    if shift_types is None:
        shift_types = infer_shift_types(schedule_data)

    # Reconstruct periods
    periods = []
    for p in schedule_data.get("periods", []):
        assignments: dict[str, list[ShiftInstance]] = {}
        for worker_id, shifts in p.get("assignments", {}).items():
            assignments[worker_id] = [
                ShiftInstance(
                    shift_type_id=s["shift_type_id"],
                    period_index=p["period_index"],
                    date=date.fromisoformat(s["date"]),
                    worker_id=worker_id,
                )
                for s in shifts
            ]
        periods.append(
            PeriodAssignment(
                period_index=p["period_index"],
                period_start=date.fromisoformat(p["period_start"]),
                period_end=date.fromisoformat(p["period_end"]),
                assignments=assignments,
            )
        )

    return Schedule(
        schedule_id=schedule_data.get("schedule_id", "UNKNOWN"),
        start_date=date.fromisoformat(schedule_data["start_date"]),
        end_date=date.fromisoformat(schedule_data["end_date"]),
        period_type="week",
        periods=periods,
        workers=workers,
        shift_types=shift_types,
    )
