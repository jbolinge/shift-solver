"""Integration test replicating a physician-style scheduling scenario.

Mirrors the structure of a real-world hospital/clinic rotation: a small pool
of interchangeable-but-restricted workers covering one hospital (day, night,
weekend) and three ambulatory clinics over a full year, with rotating
vacations, fairness over undesirable shifts, per-worker location frequency
requirements, rotation preferences, and scheduling requests.

All identifiers are intentionally generic (doc_1..doc_8, hospital_*,
clinic_*); the scenario exercises the engine, not any specific workplace.

Engine notes that shape the assertions:
- worker_shift_limit is enabled by default (hard, max_shifts_per_period=1),
  giving the engine at-most-one-shift-per-worker-per-period exclusivity. The
  scenario is sized so a one-shift-per-worker solution exists (7 available
  workers for 7 weekly slots) and is in fact the only kind of solution the
  solver can produce now.
- Only one fairness instance exists per solve, so night and weekend counts
  are POOLED into a single per-worker spread objective; separate
  equal-nights / equal-weekends objectives are not expressible.
"""

from datetime import date, time, timedelta

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

pytestmark = [pytest.mark.integration, pytest.mark.slow]

NUM_WEEKS = 52
START = date(2026, 1, 5)  # a Monday

# (worker id, restricted shift type ids) — same restriction shape as the
# reference scenario: six workers each barred from one location, two free.
WORKERS = [
    ("doc_1", frozenset({"clinic_c"})),
    ("doc_2", frozenset({"clinic_b"})),
    ("doc_3", frozenset({"hospital_day"})),
    ("doc_4", frozenset({"clinic_a"})),
    ("doc_5", frozenset({"clinic_a"})),
    ("doc_6", frozenset({"clinic_b"})),
    ("doc_7", frozenset()),
    ("doc_8", frozenset()),
]

UNDESIRABLE_SHIFTS = {"hospital_night", "hospital_weekend"}


def _shift(
    sid: str,
    name: str,
    category: str,
    undesirable: bool = False,
    required: int = 1,
) -> ShiftType:
    return ShiftType(
        id=sid,
        name=name,
        category=category,
        start_time=time(7, 0),
        end_time=time(19, 0),
        duration_hours=12.0,
        is_undesirable=undesirable,
        workers_required=required,
    )


@pytest.fixture(scope="module")
def scenario() -> dict:
    """Build and solve the full-year physician-style scenario once."""
    workers = [
        Worker(id=wid, name=wid.replace("_", " ").title(), restricted_shifts=r)
        for wid, r in WORKERS
    ]
    shift_types = [
        _shift("hospital_day", "Hospital Day", "day", required=2),
        _shift("hospital_night", "Hospital Night", "night", undesirable=True),
        _shift("hospital_weekend", "Hospital Weekend", "weekend", undesirable=True),
        _shift("clinic_a", "Clinic A", "ambulatory"),
        _shift("clinic_b", "Clinic B", "ambulatory"),
        _shift("clinic_c", "Clinic C", "ambulatory"),
    ]
    period_dates = [
        (START + timedelta(weeks=w), START + timedelta(weeks=w, days=6))
        for w in range(NUM_WEEKS)
    ]

    # Rotating vacations: one worker off each week, so 7 workers remain for
    # the 7 weekly slots (hospital_day x2 + 5 single-coverage shifts).
    availabilities = [
        Availability(
            worker_id=workers[w % len(workers)].id,
            start_date=period_dates[w][0],
            end_date=period_dates[w][1],
            availability_type="unavailable",
        )
        for w in range(NUM_WEEKS)
    ]

    requests = [
        # Hard requests — must be honored exactly.
        SchedulingRequest(
            worker_id="doc_8",
            start_date=period_dates[10][0],
            end_date=period_dates[10][1],
            request_type="positive",
            shift_type_id="hospital_night",
            priority=3,
            is_hard=True,
        ),
        SchedulingRequest(
            worker_id="doc_4",
            start_date=period_dates[20][0],
            end_date=period_dates[20][1],
            request_type="negative",
            shift_type_id="hospital_weekend",
            priority=3,
            is_hard=True,
        ),
        # Soft requests — preferences with penalties.
        SchedulingRequest(
            worker_id="doc_5",
            start_date=period_dates[5][0],
            end_date=period_dates[5][1],
            request_type="positive",
            shift_type_id="clinic_c",
            priority=2,
        ),
        SchedulingRequest(
            worker_id="doc_7",
            start_date=period_dates[30][0],
            end_date=period_dates[30][1],
            request_type="negative",
            shift_type_id="hospital_night",
            priority=2,
        ),
    ]

    # Each of these workers must visit their key location at least once in
    # every 4-week sliding window (soft, weight 500).
    frequency_requirements = [
        ShiftFrequencyRequirement("doc_1", frozenset({"clinic_b"}), 4),
        ShiftFrequencyRequirement("doc_7", frozenset({"hospital_day"}), 4),
        ShiftFrequencyRequirement("doc_2", frozenset({"clinic_c"}), 4),
        ShiftFrequencyRequirement("doc_3", frozenset({"clinic_a"}), 4),
    ]

    order_preferences = [
        ShiftOrderPreference(
            rule_id="night_after_weekend",
            trigger_type="category",
            trigger_value="weekend",
            direction="after",
            preferred_type="category",
            preferred_value="night",
            priority=2,
        ),
        ShiftOrderPreference(
            rule_id="night_before_vacation",
            trigger_type="unavailability",
            trigger_value=None,
            direction="before",
            preferred_type="shift_type",
            preferred_value="hospital_night",
        ),
    ]

    constraint_configs = {
        "coverage": ConstraintConfig(enabled=True, is_hard=True),
        "restriction": ConstraintConfig(enabled=True, is_hard=True),
        "availability": ConstraintConfig(enabled=True, is_hard=True),
        "fairness": ConstraintConfig(
            enabled=True,
            is_hard=False,
            weight=1000,
            parameters={"categories": ["night", "weekend"]},
        ),
        "shift_frequency": ConstraintConfig(enabled=True, is_hard=False, weight=500),
        "max_absence": ConstraintConfig(
            enabled=True,
            is_hard=False,
            weight=200,
            parameters={"max_periods_absent": 8},
        ),
        "request": ConstraintConfig(enabled=True, is_hard=False, weight=150),
        "sequence": ConstraintConfig(
            enabled=True,
            is_hard=False,
            weight=100,
            parameters={"categories": ["ambulatory"]},
        ),
        "shift_order_preference": ConstraintConfig(
            enabled=True, is_hard=False, weight=50
        ),
    }

    solver = ShiftSolver(
        workers=workers,
        shift_types=shift_types,
        period_dates=period_dates,
        schedule_id="PHYSICIAN-STYLE-2026",
        availabilities=availabilities,
        requests=requests,
        constraint_configs=constraint_configs,
        shift_frequency_requirements=frequency_requirements,
        shift_order_preferences=order_preferences,
    )
    # Tight gap: with weight-1000 fairness, a 5% gap can admit an extra
    # spread unit, which made the spread assertion flaky. The model is small
    # enough that near-optimal solves stay fast.
    result = solver.solve(time_limit_seconds=120, relative_gap_limit=0.01)
    return {
        "workers": workers,
        "shift_types": shift_types,
        "result": result,
    }


class TestPhysicianScenario:
    """Assertions over the solved full-year scenario."""

    def test_solver_succeeds(self, scenario: dict) -> None:
        result = scenario["result"]
        assert result.success, f"Solve failed: {result.status_name}"
        assert result.status_name in ("OPTIMAL", "FEASIBLE")
        assert result.schedule is not None

    def test_exact_coverage_every_week(self, scenario: dict) -> None:
        schedule = scenario["result"].schedule
        assert len(schedule.periods) == NUM_WEEKS
        total = 0
        for period in schedule.periods:
            for st in scenario["shift_types"]:
                assigned = period.get_shifts_by_type(st.id)
                assert len(assigned) == st.workers_required, (
                    f"Week {period.period_index}: {st.id} has {len(assigned)} "
                    f"workers, expected {st.workers_required}"
                )
                total += len(assigned)
        assert total == 7 * NUM_WEEKS  # 2 + 1*5 slots per week

    def test_restrictions_honored(self, scenario: dict) -> None:
        schedule = scenario["result"].schedule
        restricted = {w.id: w.restricted_shifts for w in scenario["workers"]}
        for period in schedule.periods:
            for worker_id, shifts in period.assignments.items():
                for shift in shifts:
                    assert shift.shift_type_id not in restricted[worker_id], (
                        f"Week {period.period_index}: {worker_id} assigned "
                        f"restricted shift {shift.shift_type_id}"
                    )

    def test_vacations_honored(self, scenario: dict) -> None:
        schedule = scenario["result"].schedule
        workers = scenario["workers"]
        for w in range(NUM_WEEKS):
            on_vacation = workers[w % len(workers)].id
            shifts = schedule.periods[w].get_worker_shifts(on_vacation)
            assert shifts == [], (
                f"Week {w}: {on_vacation} is on vacation but assigned "
                f"{[s.shift_type_id for s in shifts]}"
            )

    def test_pooled_undesirable_fairness(self, scenario: dict) -> None:
        # Night + weekend pooled: 104 undesirable slots / 8 workers = 13 each,
        # so a spread of 0 is attainable; allow slack for the 5% gap limit.
        schedule = scenario["result"].schedule
        counts = dict.fromkeys((w.id for w in scenario["workers"]), 0)
        for period in schedule.periods:
            for worker_id, shifts in period.assignments.items():
                counts[worker_id] += sum(
                    1 for s in shifts if s.shift_type_id in UNDESIRABLE_SHIFTS
                )
        spread = max(counts.values()) - min(counts.values())
        assert spread <= 2, f"Undesirable-shift spread too wide: {counts}"

    def test_hard_requests_honored(self, scenario: dict) -> None:
        schedule = scenario["result"].schedule
        week10 = [
            s.shift_type_id for s in schedule.periods[10].get_worker_shifts("doc_8")
        ]
        assert "hospital_night" in week10, (
            f"doc_8's hard positive request for hospital_night in week 10 "
            f"was not honored (got {week10})"
        )
        week20 = [
            s.shift_type_id for s in schedule.periods[20].get_worker_shifts("doc_4")
        ]
        assert "hospital_weekend" not in week20, (
            "doc_4's hard negative request to avoid hospital_weekend in "
            "week 20 was not honored"
        )
