"""Shared schedule reconstruction logic for CLI commands."""

from collections import defaultdict
from datetime import date, time
from typing import Any

from shift_solver.config import ShiftTypeConfig
from shift_solver.models import (
    PeriodAssignment,
    Schedule,
    ShiftInstance,
    ShiftType,
    Worker,
)


def shift_type_from_config(st: ShiftTypeConfig) -> ShiftType:
    """
    Build a solver-side ShiftType from a validated config ShiftTypeConfig.

    Carries through ``required_attributes`` and ``applicable_days``, which
    earlier ad-hoc ShiftType(...) call sites in the CLI silently dropped even
    though the config schema validates them.

    Args:
        st: The Pydantic ShiftTypeConfig loaded from a config file

    Returns:
        Equivalent ShiftType domain object
    """
    return ShiftType(
        id=st.id,
        name=st.name,
        category=st.category,
        start_time=st.start_time,
        end_time=st.end_time,
        duration_hours=st.duration_hours,
        is_undesirable=st.is_undesirable,
        workers_required=st.workers_required,
        required_attributes=dict(st.required_attributes),
        applicable_days=(
            frozenset(st.applicable_days) if st.applicable_days is not None else None
        ),
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

    ``workers_required`` is derived from the max number of workers actually
    assigned to a given shift type within any single period, rather than
    hardcoded to 1, so a coverage check run against these inferred shift
    types doesn't spuriously flag every real assignment beyond the first as
    excess coverage. Everything else (category, times, duration) has no
    signal in the schedule JSON and stays a placeholder.

    Args:
        schedule_data: Schedule JSON dict

    Returns:
        List of ShiftType objects with minimal (approximate) metadata
    """
    counts_per_period: dict[str, dict[int, int]] = defaultdict(
        lambda: defaultdict(int)
    )
    for period in schedule_data.get("periods", []):
        period_index = period.get("period_index")
        for shift_list in period.get("assignments", {}).values():
            for a in shift_list:
                counts_per_period[a.get("shift_type_id")][period_index] += 1

    return [
        ShiftType(
            id=stid,
            name=stid,
            category="unknown",
            start_time=time(0, 0),
            end_time=time(8, 0),
            duration_hours=8.0,
            workers_required=max(period_counts.values(), default=1),
        )
        for stid, period_counts in sorted(counts_per_period.items())
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
