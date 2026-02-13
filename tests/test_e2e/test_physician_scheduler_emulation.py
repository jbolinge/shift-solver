"""E2E test emulating a multi-site medical scheduling scenario.

Generates a full 52-week schedule for 8 workers across 6 shift sites,
reproducing a realistic medical scheduling setup: coverage, restrictions,
vacations, scheduling requests, frequency requirements, fairness
constraints, and shift order preferences.
"""

from collections import defaultdict
from datetime import date, time

import pytest

from shift_solver.constraints.base import ConstraintConfig
from shift_solver.models import (
    Availability,
    SchedulingRequest,
    ShiftFrequencyRequirement,
    ShiftOrderPreference,
    ShiftType,
    Worker,
)
from shift_solver.solver import ShiftSolver

from .conftest import create_period_dates


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _create_workers() -> list[Worker]:
    """8 workers with site restrictions."""
    return [
        Worker(id="doctor1", name="Doctor 1", restricted_shifts=frozenset({"site_c"})),
        Worker(id="doctor2", name="Doctor 2", restricted_shifts=frozenset()),
        Worker(id="doctor3", name="Doctor 3", restricted_shifts=frozenset({"site_b"})),
        Worker(id="doctor4", name="Doctor 4", restricted_shifts=frozenset({"hospital_day"})),
        Worker(id="doctor5", name="Doctor 5", restricted_shifts=frozenset({"site_a"})),
        Worker(id="doctor6", name="Doctor 6", restricted_shifts=frozenset({"site_a"})),
        Worker(id="doctor7", name="Doctor 7", restricted_shifts=frozenset({"site_b"})),
        Worker(id="doctor8", name="Doctor 8", restricted_shifts=frozenset()),
    ]


def _create_shift_types() -> list[ShiftType]:
    """6 shift types across hospital and satellite sites."""
    return [
        ShiftType(
            id="hospital_day",
            name="Hospital Day",
            category="day",
            start_time=time(7, 0),
            end_time=time(17, 0),
            duration_hours=10.0,
            workers_required=2,
        ),
        ShiftType(
            id="night",
            name="Hospital Night",
            category="night",
            start_time=time(17, 0),
            end_time=time(7, 0),
            duration_hours=14.0,
            workers_required=1,
            is_undesirable=True,
        ),
        ShiftType(
            id="weekend",
            name="Hospital Weekend",
            category="weekend",
            start_time=time(7, 0),
            end_time=time(19, 0),
            duration_hours=12.0,
            workers_required=1,
            is_undesirable=True,
        ),
        ShiftType(
            id="site_a",
            name="Site A",
            category="ambulatory",
            start_time=time(8, 0),
            end_time=time(17, 0),
            duration_hours=9.0,
            workers_required=1,
        ),
        ShiftType(
            id="site_b",
            name="Site B",
            category="ambulatory",
            start_time=time(8, 0),
            end_time=time(17, 0),
            duration_hours=9.0,
            workers_required=1,
        ),
        ShiftType(
            id="site_c",
            name="Site C",
            category="ambulatory",
            start_time=time(8, 0),
            end_time=time(17, 0),
            duration_hours=9.0,
            workers_required=1,
        ),
    ]


def _create_period_dates() -> list[tuple[date, date]]:
    """52 weekly periods starting Monday Jan 5, 2026 (ISO week 2)."""
    return create_period_dates(
        start_date=date(2026, 1, 5),
        num_periods=52,
        period_length_days=7,
    )


def _create_vacations() -> list[Availability]:
    """104 vacation records across all 8 workers."""
    raw = [
        # Doctor 1 (13 records)
        ("doctor1", "2026-01-17", "2026-01-25"),
        ("doctor1", "2026-03-07", "2026-03-15"),
        ("doctor1", "2026-03-14", "2026-03-22"),
        ("doctor1", "2026-03-28", "2026-04-05"),
        ("doctor1", "2026-04-18", "2026-04-26"),
        ("doctor1", "2026-05-02", "2026-05-10"),
        ("doctor1", "2026-06-13", "2026-06-21"),
        ("doctor1", "2026-07-18", "2026-07-26"),
        ("doctor1", "2026-08-01", "2026-08-09"),
        ("doctor1", "2026-08-08", "2026-08-16"),
        ("doctor1", "2026-09-12", "2026-09-20"),
        ("doctor1", "2026-10-10", "2026-10-18"),
        ("doctor1", "2026-11-28", "2026-12-06"),
        # Doctor 2 (13 records)
        ("doctor2", "2026-01-03", "2026-01-11"),
        ("doctor2", "2026-01-31", "2026-02-08"),
        ("doctor2", "2026-03-21", "2026-03-29"),
        ("doctor2", "2026-04-25", "2026-05-03"),
        ("doctor2", "2026-06-20", "2026-06-28"),
        ("doctor2", "2026-07-11", "2026-07-19"),
        ("doctor2", "2026-07-18", "2026-07-26"),
        ("doctor2", "2026-08-08", "2026-08-16"),
        ("doctor2", "2026-08-15", "2026-08-23"),
        ("doctor2", "2026-09-26", "2026-10-04"),
        ("doctor2", "2026-10-24", "2026-11-01"),
        ("doctor2", "2026-11-28", "2026-12-06"),
        ("doctor2", "2026-12-26", "2027-01-03"),
        # Doctor 3 (13 records)
        ("doctor3", "2026-01-10", "2026-01-18"),
        ("doctor3", "2026-02-07", "2026-02-15"),
        ("doctor3", "2026-02-28", "2026-03-08"),
        ("doctor3", "2026-04-18", "2026-04-26"),
        ("doctor3", "2026-05-09", "2026-05-17"),
        ("doctor3", "2026-05-30", "2026-06-07"),
        ("doctor3", "2026-08-22", "2026-08-30"),
        ("doctor3", "2026-09-19", "2026-09-27"),
        ("doctor3", "2026-10-03", "2026-10-11"),
        ("doctor3", "2026-10-17", "2026-10-25"),
        ("doctor3", "2026-10-31", "2026-11-08"),
        ("doctor3", "2026-11-14", "2026-11-22"),
        ("doctor3", "2026-12-05", "2026-12-13"),
        # Doctor 4 (13 records)
        ("doctor4", "2026-01-03", "2026-01-11"),
        ("doctor4", "2026-01-24", "2026-02-01"),
        ("doctor4", "2026-02-14", "2026-02-22"),
        ("doctor4", "2026-03-07", "2026-03-15"),
        ("doctor4", "2026-04-04", "2026-04-12"),
        ("doctor4", "2026-05-16", "2026-05-24"),
        ("doctor4", "2026-06-13", "2026-06-21"),
        ("doctor4", "2026-07-25", "2026-08-02"),
        ("doctor4", "2026-08-22", "2026-08-30"),
        ("doctor4", "2026-09-12", "2026-09-20"),
        ("doctor4", "2026-09-26", "2026-10-04"),
        ("doctor4", "2026-11-21", "2026-11-29"),
        ("doctor4", "2026-12-19", "2026-12-27"),
        # Doctor 5 (13 records)
        ("doctor5", "2026-01-10", "2026-01-18"),
        ("doctor5", "2026-02-07", "2026-02-15"),
        ("doctor5", "2026-03-21", "2026-03-29"),
        ("doctor5", "2026-04-11", "2026-04-19"),
        ("doctor5", "2026-05-16", "2026-05-24"),
        ("doctor5", "2026-05-23", "2026-05-31"),
        ("doctor5", "2026-06-20", "2026-06-28"),
        ("doctor5", "2026-07-04", "2026-07-12"),
        ("doctor5", "2026-08-15", "2026-08-23"),
        ("doctor5", "2026-09-05", "2026-09-13"),
        ("doctor5", "2026-10-24", "2026-11-01"),
        ("doctor5", "2026-11-07", "2026-11-15"),
        ("doctor5", "2026-12-12", "2026-12-20"),
        # Doctor 6 (13 records)
        ("doctor6", "2026-01-24", "2026-02-01"),
        ("doctor6", "2026-02-21", "2026-03-01"),
        ("doctor6", "2026-02-28", "2026-03-08"),
        ("doctor6", "2026-04-25", "2026-05-03"),
        ("doctor6", "2026-06-06", "2026-06-14"),
        ("doctor6", "2026-07-04", "2026-07-12"),
        ("doctor6", "2026-09-05", "2026-09-13"),
        ("doctor6", "2026-09-19", "2026-09-27"),
        ("doctor6", "2026-10-17", "2026-10-25"),
        ("doctor6", "2026-11-07", "2026-11-15"),
        ("doctor6", "2026-11-21", "2026-11-29"),
        ("doctor6", "2026-12-05", "2026-12-13"),
        ("doctor6", "2026-12-12", "2026-12-20"),
        # Doctor 7 (13 records)
        ("doctor7", "2026-01-17", "2026-01-25"),
        ("doctor7", "2026-02-14", "2026-02-22"),
        ("doctor7", "2026-02-21", "2026-03-01"),
        ("doctor7", "2026-03-28", "2026-04-05"),
        ("doctor7", "2026-04-04", "2026-04-12"),
        ("doctor7", "2026-05-09", "2026-05-17"),
        ("doctor7", "2026-05-30", "2026-06-07"),
        ("doctor7", "2026-06-27", "2026-07-05"),
        ("doctor7", "2026-07-25", "2026-08-02"),
        ("doctor7", "2026-08-29", "2026-09-06"),
        ("doctor7", "2026-10-03", "2026-10-11"),
        ("doctor7", "2026-10-31", "2026-11-08"),
        ("doctor7", "2026-12-26", "2027-01-03"),
        # Doctor 8 (13 records)
        ("doctor8", "2026-01-31", "2026-02-08"),
        ("doctor8", "2026-03-14", "2026-03-22"),
        ("doctor8", "2026-04-11", "2026-04-19"),
        ("doctor8", "2026-05-02", "2026-05-10"),
        ("doctor8", "2026-05-23", "2026-05-31"),
        ("doctor8", "2026-06-06", "2026-06-14"),
        ("doctor8", "2026-06-27", "2026-07-05"),
        ("doctor8", "2026-07-11", "2026-07-19"),
        ("doctor8", "2026-08-01", "2026-08-09"),
        ("doctor8", "2026-08-29", "2026-09-06"),
        ("doctor8", "2026-10-10", "2026-10-18"),
        ("doctor8", "2026-11-14", "2026-11-22"),
        ("doctor8", "2026-12-19", "2026-12-27"),
    ]
    return [
        Availability(
            worker_id=wid,
            start_date=date.fromisoformat(s),
            end_date=date.fromisoformat(e),
            availability_type="unavailable",
        )
        for wid, s, e in raw
    ]


def _create_requests() -> list[SchedulingRequest]:
    """17 scheduling requests across workers."""
    raw = [
        ("doctor2", "2026-12-18", "2026-12-20", "negative", "weekend"),
        ("doctor2", "2026-03-13", "2026-03-15", "negative", "weekend"),
        ("doctor4", "2026-01-23", "2026-01-25", "negative", "weekend"),
        ("doctor6", "2026-08-03", "2026-08-06", "positive", "night"),
        ("doctor6", "2026-11-30", "2026-12-03", "positive", "night"),
        ("doctor5", "2026-01-23", "2026-01-25", "negative", "weekend"),
        ("doctor7", "2026-02-06", "2026-02-08", "negative", "weekend"),
        ("doctor7", "2026-02-09", "2026-02-12", "negative", "night"),
        ("doctor1", "2026-03-23", "2026-03-26", "positive", "night"),
        ("doctor1", "2026-02-13", "2026-02-15", "negative", "weekend"),
        ("doctor1", "2026-02-06", "2026-02-08", "negative", "weekend"),
        ("doctor1", "2026-04-24", "2026-04-26", "negative", "weekend"),
        ("doctor1", "2026-01-30", "2026-02-01", "negative", "weekend"),
        ("doctor1", "2026-07-10", "2026-07-12", "negative", "weekend"),
        ("doctor1", "2026-07-13", "2026-07-16", "negative", "night"),
        ("doctor8", "2026-03-06", "2026-03-08", "positive", "weekend"),
        ("doctor8", "2026-03-09", "2026-03-12", "positive", "night"),
    ]
    return [
        SchedulingRequest(
            worker_id=wid,
            start_date=date.fromisoformat(s),
            end_date=date.fromisoformat(e),
            request_type=rtype,
            shift_type_id=shift,
            priority=1,
        )
        for wid, s, e, rtype, shift in raw
    ]


def _create_frequency_requirements() -> list[ShiftFrequencyRequirement]:
    """4 worker-specific frequency rules."""
    return [
        ShiftFrequencyRequirement(
            worker_id="doctor1",
            shift_types=frozenset({"site_b"}),
            max_periods_between=4,
        ),
        ShiftFrequencyRequirement(
            worker_id="doctor2",
            shift_types=frozenset({"hospital_day"}),
            max_periods_between=4,
        ),
        ShiftFrequencyRequirement(
            worker_id="doctor3",
            shift_types=frozenset({"site_c"}),
            max_periods_between=4,
        ),
        ShiftFrequencyRequirement(
            worker_id="doctor4",
            shift_types=frozenset({"site_a"}),
            max_periods_between=4,
        ),
    ]


def _create_order_preferences() -> list[ShiftOrderPreference]:
    """2 shift order preference rules."""
    return [
        ShiftOrderPreference(
            rule_id="night_before_vacation",
            trigger_type="unavailability",
            trigger_value=None,
            direction="before",
            preferred_type="shift_type",
            preferred_value="night",
            priority=1,
        ),
        ShiftOrderPreference(
            rule_id="night_after_weekend",
            trigger_type="shift_type",
            trigger_value="weekend",
            direction="after",
            preferred_type="shift_type",
            preferred_value="night",
            priority=1,
        ),
    ]


def _create_constraint_configs() -> dict[str, ConstraintConfig]:
    """Constraint configuration with realistic weights."""
    return {
        # Hard constraints
        "coverage": ConstraintConfig(enabled=True, is_hard=True),
        "restriction": ConstraintConfig(enabled=True, is_hard=True),
        "availability": ConstraintConfig(enabled=True, is_hard=True),
        # Soft constraints
        "fairness": ConstraintConfig(enabled=True, is_hard=False, weight=1000),
        "shift_frequency": ConstraintConfig(enabled=True, is_hard=False, weight=500),
        "request": ConstraintConfig(enabled=True, is_hard=False, weight=150),
        "sequence": ConstraintConfig(
            enabled=True,
            is_hard=False,
            weight=100,
            parameters={"categories": ["ambulatory"]},
        ),
        "max_absence": ConstraintConfig(
            enabled=True,
            is_hard=False,
            weight=200,
            parameters={"max_periods_absent": 8},
        ),
        "shift_order_preference": ConstraintConfig(
            enabled=True, is_hard=False, weight=50
        ),
    }


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------


@pytest.mark.e2e
@pytest.mark.slow
class TestPhysicianSchedulerEmulation:
    """Full multi-site scheduling emulation over a 52-week horizon."""

    def test_generates_full_year_schedule(self) -> None:
        """Solve a 52-week, 8-worker, 6-site schedule and verify constraints."""
        # --- Setup ---
        workers = _create_workers()
        shift_types = _create_shift_types()
        period_dates = _create_period_dates()
        vacations = _create_vacations()
        requests = _create_requests()
        frequency_requirements = _create_frequency_requirements()
        order_preferences = _create_order_preferences()
        constraint_configs = _create_constraint_configs()

        solver = ShiftSolver(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            schedule_id="MULTI-SITE-EMULATION-2026",
            availabilities=vacations,
            requests=requests,
            constraint_configs=constraint_configs,
            shift_frequency_requirements=frequency_requirements,
            shift_order_preferences=order_preferences,
        )
        result = solver.solve(time_limit_seconds=300)

        # --- Basic feasibility ---
        assert result.success, f"Solver failed: {result.status_name}"
        assert result.schedule is not None
        assert len(result.schedule.periods) == 52

        schedule = result.schedule
        shift_type_map = {st.id: st for st in shift_types}
        worker_map = {w.id: w for w in workers}

        # --- Coverage verification ---
        for period in schedule.periods:
            assigned_counts: dict[str, int] = defaultdict(int)
            for shifts in period.assignments.values():
                for shift in shifts:
                    assigned_counts[shift.shift_type_id] += 1
            for st in shift_types:
                assert assigned_counts[st.id] >= st.workers_required, (
                    f"Period {period.period_index}: {st.id} has "
                    f"{assigned_counts[st.id]} workers, needs {st.workers_required}"
                )

        # --- Restriction verification ---
        for period in schedule.periods:
            for worker_id, shifts in period.assignments.items():
                w = worker_map[worker_id]
                for shift in shifts:
                    assert shift.shift_type_id not in w.restricted_shifts, (
                        f"Period {period.period_index}: {worker_id} assigned to "
                        f"restricted shift {shift.shift_type_id}"
                    )

        # --- Vacation verification ---
        vacation_lookup: dict[str, list[Availability]] = defaultdict(list)
        for v in vacations:
            vacation_lookup[v.worker_id].append(v)

        for period in schedule.periods:
            p_start, p_end = period.period_start, period.period_end
            for worker_id, shifts in period.assignments.items():
                if not shifts:
                    continue
                for v in vacation_lookup[worker_id]:
                    overlaps = v.start_date <= p_end and v.end_date >= p_start
                    assert not overlaps, (
                        f"Period {period.period_index}: {worker_id} assigned "
                        f"during vacation {v.start_date}--{v.end_date}"
                    )

        # --- Fairness check (night + weekend spread) ---
        night_counts: dict[str, int] = defaultdict(int)
        weekend_counts: dict[str, int] = defaultdict(int)
        for period in schedule.periods:
            for worker_id, shifts in period.assignments.items():
                for shift in shifts:
                    if shift.shift_type_id == "night":
                        night_counts[worker_id] += 1
                    elif shift.shift_type_id == "weekend":
                        weekend_counts[worker_id] += 1

        night_values = [night_counts.get(w.id, 0) for w in workers]
        weekend_values = [weekend_counts.get(w.id, 0) for w in workers]
        night_spread = max(night_values) - min(night_values)
        weekend_spread = max(weekend_values) - min(weekend_values)
        assert night_spread <= 4, f"Night spread too large: {night_spread}"
        assert weekend_spread <= 4, f"Weekend spread too large: {weekend_spread}"

        # --- Statistics reporting (informational) ---
        print(f"\n{'='*70}")
        print("Multi-Site Scheduling Emulation Results")
        print(f"{'='*70}")
        print(f"Solve time: {result.solve_time_seconds:.1f}s")
        print(f"Objective value: {result.objective_value}")
        print()

        # Per-worker shift counts
        worker_shift_counts: dict[str, dict[str, int]] = {
            w.id: defaultdict(int) for w in workers
        }
        for period in schedule.periods:
            for worker_id, shifts in period.assignments.items():
                for shift in shifts:
                    worker_shift_counts[worker_id][shift.shift_type_id] += 1

        header = f"{'Worker':<12}" + "".join(
            f"{st.id:<14}" for st in shift_types
        ) + "Total"
        print(header)
        print("-" * len(header))
        for w in workers:
            counts = worker_shift_counts[w.id]
            total = sum(counts.values())
            row = f"{w.id:<12}" + "".join(
                f"{counts.get(st.id, 0):<14}" for st in shift_types
            ) + str(total)
            print(row)

        # Night+weekend co-assignments
        night_weekend_coassign = 0
        for period in schedule.periods:
            for worker_id, shifts in period.assignments.items():
                types = {s.shift_type_id for s in shifts}
                if "night" in types and "weekend" in types:
                    night_weekend_coassign += 1

        print(f"\nNight+weekend co-assignments: {night_weekend_coassign} (goal: 0)")
        print(f"Night spread: {night_spread} (max-min across workers)")
        print(f"Weekend spread: {weekend_spread} (max-min across workers)")
        print(f"{'='*70}")
