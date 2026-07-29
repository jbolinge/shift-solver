"""Tests for ScheduleValidator post-solve validation."""

from datetime import date, time

import pytest

from shift_solver.models import (
    Availability,
    PeriodAssignment,
    Schedule,
    SchedulingRequest,
    ShiftInstance,
    ShiftType,
    Worker,
)
from shift_solver.validation.schedule_validator import (
    ScheduleValidator,
    ValidationResult,
)


def make_schedule(
    periods: list[PeriodAssignment],
    workers: list[Worker],
    shift_types: list[ShiftType],
    schedule_id: str = "TEST",
) -> Schedule:
    """Build a Schedule spanning the given periods (helper to cut boilerplate)."""
    start = periods[0].period_start
    end = periods[-1].period_end
    return Schedule(
        schedule_id=schedule_id,
        start_date=start,
        end_date=end,
        period_type="week",
        periods=periods,
        workers=workers,
        shift_types=shift_types,
    )


@pytest.fixture
def workers() -> list[Worker]:
    """Sample workers."""
    return [
        Worker(id="W1", name="Alice"),
        Worker(id="W2", name="Bob"),
        Worker(id="W3", name="Charlie", restricted_shifts=frozenset(["night"])),
        Worker(id="W4", name="Diana"),
    ]


@pytest.fixture
def shift_types() -> list[ShiftType]:
    """Sample shift types."""
    return [
        ShiftType(
            id="day",
            name="Day Shift",
            category="day",
            start_time=time(7, 0),
            end_time=time(15, 0),
            duration_hours=8.0,
            workers_required=2,
        ),
        ShiftType(
            id="night",
            name="Night Shift",
            category="night",
            start_time=time(23, 0),
            end_time=time(7, 0),
            duration_hours=8.0,
            workers_required=1,
            is_undesirable=True,
        ),
    ]


@pytest.fixture
def valid_schedule(workers: list[Worker], shift_types: list[ShiftType]) -> Schedule:
    """
    A valid schedule with proper coverage, no double-booked workers, and no
    restricted assignments: W1 and W2 cover the two required day shifts, and
    W4 (unrestricted) covers the single required night shift.
    """
    periods = [
        PeriodAssignment(
            period_index=0,
            period_start=date(2026, 1, 1),
            period_end=date(2026, 1, 7),
            assignments={
                "W1": [
                    ShiftInstance(
                        shift_type_id="day",
                        period_index=0,
                        date=date(2026, 1, 1),
                        worker_id="W1",
                    ),
                ],
                "W2": [
                    ShiftInstance(
                        shift_type_id="day",
                        period_index=0,
                        date=date(2026, 1, 1),
                        worker_id="W2",
                    ),
                ],
                "W4": [
                    ShiftInstance(
                        shift_type_id="night",
                        period_index=0,
                        date=date(2026, 1, 1),
                        worker_id="W4",
                    ),
                ],
            },
        ),
    ]
    return make_schedule(periods, workers, shift_types, schedule_id="VALID-001")


class TestValidationResult:
    """Test ValidationResult data class."""

    def test_valid_result(self) -> None:
        """Valid result has no violations."""
        result = ValidationResult(is_valid=True, violations=[], warnings=[])
        assert result.is_valid
        assert len(result.violations) == 0

    def test_invalid_result_with_violations(self) -> None:
        """Invalid result contains violations."""
        violations = [
            {"type": "coverage", "message": "Shift not covered", "severity": "error"}
        ]
        result = ValidationResult(is_valid=False, violations=violations)
        assert not result.is_valid
        assert len(result.violations) == 1

    def test_result_statistics(self) -> None:
        """Result can include statistics."""
        stats = {
            "total_shifts": 100,
            "coverage_rate": 0.95,
            "request_fulfillment_rate": 0.8,
        }
        result = ValidationResult(is_valid=True, violations=[], statistics=stats)
        assert result.statistics["coverage_rate"] == 0.95


class TestScheduleValidator:
    """Test ScheduleValidator class."""

    def test_validator_creation(self, valid_schedule: Schedule) -> None:
        """Validator should be created with a schedule."""
        validator = ScheduleValidator(schedule=valid_schedule)
        assert validator is not None

    def test_valid_schedule_passes(self, valid_schedule: Schedule) -> None:
        """A valid schedule should pass validation."""
        validator = ScheduleValidator(schedule=valid_schedule)
        result = validator.validate()
        assert result.is_valid, f"Unexpected violations: {result.violations}"


class TestConstructorBackwardCompatibility:
    """The constructor must keep working for existing call sites (e.g. the CLI)."""

    def test_minimal_call_site_still_works(self, valid_schedule: Schedule) -> None:
        """Calling with only schedule/availabilities/requests keeps working."""
        validator = ScheduleValidator(
            schedule=valid_schedule, availabilities=[], requests=[]
        )
        result = validator.validate()
        assert result.is_valid

    def test_absent_metadata_degrades_gracefully(self) -> None:
        """
        Without richer shift_types metadata, a shift type with no
        required_attributes is unconstrained, so the skills check has
        nothing to flag (it degrades to a no-op rather than erroring).
        """
        bare_shift = ShiftType(
            id="icu",
            name="icu",
            category="unknown",
            start_time=time(0, 0),
            end_time=time(8, 0),
            duration_hours=8.0,
            workers_required=1,
        )
        periods = [
            PeriodAssignment(
                period_index=0,
                period_start=date(2026, 1, 1),
                period_end=date(2026, 1, 7),
                assignments={
                    "W1": [
                        ShiftInstance(
                            shift_type_id="icu",
                            period_index=0,
                            date=date(2026, 1, 1),
                            worker_id="W1",
                        ),
                    ],
                },
            ),
        ]
        schedule = make_schedule(
            periods, [Worker(id="W1", name="Alice")], [bare_shift]
        )

        result = ScheduleValidator(schedule=schedule).validate()
        assert not any(v["type"] == "skills" for v in result.violations)

    def test_shift_types_override_supplies_missing_metadata(self) -> None:
        """
        Passing richer shift_types metadata (e.g. loaded separately from
        config) activates checks the bare schedule couldn't support alone.
        """
        bare_shift = ShiftType(
            id="icu",
            name="icu",
            category="unknown",
            start_time=time(0, 0),
            end_time=time(8, 0),
            duration_hours=8.0,
            workers_required=1,
        )
        periods = [
            PeriodAssignment(
                period_index=0,
                period_start=date(2026, 1, 1),
                period_end=date(2026, 1, 7),
                assignments={
                    "W1": [
                        ShiftInstance(
                            shift_type_id="icu",
                            period_index=0,
                            date=date(2026, 1, 1),
                            worker_id="W1",
                        ),
                    ],
                },
            ),
        ]
        schedule = make_schedule(
            periods, [Worker(id="W1", name="Alice")], [bare_shift]
        )

        rich_shift = ShiftType(
            id="icu",
            name="ICU",
            category="day",
            start_time=time(7, 0),
            end_time=time(15, 0),
            duration_hours=8.0,
            workers_required=1,
            required_attributes={"license": "RN"},
        )
        result = ScheduleValidator(
            schedule=schedule, shift_types=[rich_shift]
        ).validate()
        assert any(v["type"] == "skills" for v in result.violations)

    def test_workers_override_supplies_missing_metadata(self) -> None:
        """Passing richer worker metadata also feeds into the skills check."""
        shift = ShiftType(
            id="icu",
            name="ICU",
            category="day",
            start_time=time(7, 0),
            end_time=time(15, 0),
            duration_hours=8.0,
            workers_required=1,
            required_attributes={"license": "RN"},
        )
        periods = [
            PeriodAssignment(
                period_index=0,
                period_start=date(2026, 1, 1),
                period_end=date(2026, 1, 7),
                assignments={
                    "W1": [
                        ShiftInstance(
                            shift_type_id="icu",
                            period_index=0,
                            date=date(2026, 1, 1),
                            worker_id="W1",
                        ),
                    ],
                },
            ),
        ]
        # Schedule embeds a bare worker with no attributes.
        bare_worker = Worker(id="W1", name="Alice")
        schedule = make_schedule(periods, [bare_worker], [shift])

        result = ScheduleValidator(schedule=schedule).validate()
        assert any(v["type"] == "skills" for v in result.violations)

        qualified_worker = Worker(
            id="W1", name="Alice", attributes={"license": "RN"}
        )
        result = ScheduleValidator(
            schedule=schedule, workers=[qualified_worker]
        ).validate()
        assert not any(v["type"] == "skills" for v in result.violations)


class TestCoverageValidation:
    """Test coverage requirement validation (defect B)."""

    def test_missing_coverage_detected(
        self, workers: list[Worker], shift_types: list[ShiftType]
    ) -> None:
        """Should detect when coverage requirements not met (under-coverage)."""
        periods = [
            PeriodAssignment(
                period_index=0,
                period_start=date(2026, 1, 1),
                period_end=date(2026, 1, 7),
                assignments={
                    "W1": [
                        ShiftInstance(
                            shift_type_id="day",
                            period_index=0,
                            date=date(2026, 1, 1),
                            worker_id="W1",
                        ),
                    ],
                },
            ),
        ]
        schedule = make_schedule(periods, workers, shift_types)

        validator = ScheduleValidator(schedule=schedule)
        result = validator.validate()
        assert not result.is_valid
        assert any(v["type"] == "coverage" for v in result.violations)
        assert not any(v["type"] == "coverage_excess" for v in result.violations)

    def test_over_coverage_detected_distinctly(self, workers: list[Worker]) -> None:
        """
        Over-coverage must be flagged too (the solver enforces ==, not >=)
        and reported as a distinct kind of violation from under-coverage.
        """
        day_shift = [
            ShiftType(
                id="day",
                name="Day",
                category="day",
                start_time=time(7, 0),
                end_time=time(15, 0),
                duration_hours=8.0,
                workers_required=2,
            ),
        ]
        periods = [
            PeriodAssignment(
                period_index=0,
                period_start=date(2026, 1, 1),
                period_end=date(2026, 1, 7),
                assignments={
                    "W1": [
                        ShiftInstance(
                            shift_type_id="day",
                            period_index=0,
                            date=date(2026, 1, 1),
                            worker_id="W1",
                        ),
                    ],
                    "W2": [
                        ShiftInstance(
                            shift_type_id="day",
                            period_index=0,
                            date=date(2026, 1, 1),
                            worker_id="W2",
                        ),
                    ],
                    "W3": [
                        ShiftInstance(
                            shift_type_id="day",
                            period_index=0,
                            date=date(2026, 1, 1),
                            worker_id="W3",
                        ),
                    ],
                },
            ),
        ]
        schedule = make_schedule(periods, workers, day_shift)

        validator = ScheduleValidator(schedule=schedule)
        result = validator.validate()
        assert not result.is_valid
        assert any(v["type"] == "coverage_excess" for v in result.violations)
        assert not any(v["type"] == "coverage" for v in result.violations)

    def test_weekend_only_shift_with_no_weekday_coverage_is_valid(
        self, workers: list[Worker]
    ) -> None:
        """
        A shift type restricted to weekend days has zero applicable days in
        a Mon-Fri period, so zero assignments there is CORRECT, not a
        violation (previously this was flagged as invalid).
        """
        weekend_shift = ShiftType(
            id="weekend",
            name="Weekend Shift",
            category="weekend",
            start_time=time(9, 0),
            end_time=time(17, 0),
            duration_hours=8.0,
            workers_required=1,
            applicable_days=frozenset({5, 6}),  # Saturday, Sunday
        )
        # 2026-01-05 (Mon) through 2026-01-09 (Fri): no weekend days at all.
        periods = [
            PeriodAssignment(
                period_index=0,
                period_start=date(2026, 1, 5),
                period_end=date(2026, 1, 9),
                assignments={},
            ),
        ]
        schedule = make_schedule(periods, workers, [weekend_shift])

        validator = ScheduleValidator(schedule=schedule)
        result = validator.validate()
        assert result.is_valid, f"Unexpected violations: {result.violations}"

    def test_weekend_only_shift_still_requires_coverage_on_weekend(
        self, workers: list[Worker]
    ) -> None:
        """When the period DOES include an applicable day, coverage is required."""
        weekend_shift = ShiftType(
            id="weekend",
            name="Weekend Shift",
            category="weekend",
            start_time=time(9, 0),
            end_time=time(17, 0),
            duration_hours=8.0,
            workers_required=1,
            applicable_days=frozenset({5, 6}),
        )
        # 2026-01-10 (Sat) through 2026-01-11 (Sun): entirely weekend.
        periods = [
            PeriodAssignment(
                period_index=0,
                period_start=date(2026, 1, 10),
                period_end=date(2026, 1, 11),
                assignments={},
            ),
        ]
        schedule = make_schedule(periods, workers, [weekend_shift])

        validator = ScheduleValidator(schedule=schedule)
        result = validator.validate()
        assert not result.is_valid
        assert any(v["type"] == "coverage" for v in result.violations)

        # And the valid counterpart: covered as required.
        periods_ok = [
            PeriodAssignment(
                period_index=0,
                period_start=date(2026, 1, 10),
                period_end=date(2026, 1, 11),
                assignments={
                    "W1": [
                        ShiftInstance(
                            shift_type_id="weekend",
                            period_index=0,
                            date=date(2026, 1, 10),
                            worker_id="W1",
                        ),
                    ],
                },
            ),
        ]
        schedule_ok = make_schedule(periods_ok, workers, [weekend_shift])
        result_ok = ScheduleValidator(schedule=schedule_ok).validate()
        assert result_ok.is_valid, f"Unexpected violations: {result_ok.violations}"


class TestRestrictionValidation:
    """Test restriction and data-integrity violation detection (defect E)."""

    def test_restricted_assignment_detected(
        self, workers: list[Worker], shift_types: list[ShiftType]
    ) -> None:
        """Should detect when worker assigned to restricted shift."""
        # W3 is restricted from night shifts
        periods = [
            PeriodAssignment(
                period_index=0,
                period_start=date(2026, 1, 1),
                period_end=date(2026, 1, 7),
                assignments={
                    "W1": [
                        ShiftInstance(
                            shift_type_id="day",
                            period_index=0,
                            date=date(2026, 1, 1),
                            worker_id="W1",
                        ),
                    ],
                    "W2": [
                        ShiftInstance(
                            shift_type_id="day",
                            period_index=0,
                            date=date(2026, 1, 1),
                            worker_id="W2",
                        ),
                    ],
                    "W3": [
                        ShiftInstance(
                            shift_type_id="night",  # W3 is restricted!
                            period_index=0,
                            date=date(2026, 1, 1),
                            worker_id="W3",
                        ),
                    ],
                },
            ),
        ]
        schedule = make_schedule(periods, workers, shift_types)

        validator = ScheduleValidator(schedule=schedule)
        result = validator.validate()
        assert not result.is_valid
        assert any(v["type"] == "restriction" for v in result.violations)

    def test_unknown_worker_flagged_as_data_violation(
        self, shift_types: list[ShiftType]
    ) -> None:
        """An assignment referencing a worker id absent from the roster is invalid."""
        periods = [
            PeriodAssignment(
                period_index=0,
                period_start=date(2026, 1, 1),
                period_end=date(2026, 1, 7),
                assignments={
                    "GHOST": [
                        ShiftInstance(
                            shift_type_id="day",
                            period_index=0,
                            date=date(2026, 1, 1),
                            worker_id="GHOST",
                        ),
                    ],
                },
            ),
        ]
        schedule = make_schedule(periods, [], shift_types)

        result = ScheduleValidator(schedule=schedule).validate()
        assert not result.is_valid
        assert any(
            v["type"] == "data" and v.get("worker_id") == "GHOST"
            for v in result.violations
        )

    def test_unknown_shift_type_flagged_as_data_violation(
        self, workers: list[Worker]
    ) -> None:
        """
        An assignment referencing a shift_type_id absent from the schedule's
        shift types must be flagged, matching how unknown workers are
        already flagged (previously this was silently tolerated).
        """
        periods = [
            PeriodAssignment(
                period_index=0,
                period_start=date(2026, 1, 1),
                period_end=date(2026, 1, 7),
                assignments={
                    "W1": [
                        ShiftInstance(
                            shift_type_id="mystery",
                            period_index=0,
                            date=date(2026, 1, 1),
                            worker_id="W1",
                        ),
                    ],
                },
            ),
        ]
        schedule = make_schedule(periods, workers, [])

        result = ScheduleValidator(schedule=schedule).validate()
        assert not result.is_valid
        assert any(
            v["type"] == "data" and v.get("shift_type_id") == "mystery"
            for v in result.violations
        )


class TestAvailabilityValidation:
    """Test availability violation detection (defect C)."""

    def test_unavailable_assignment_detected(
        self, workers: list[Worker], shift_types: list[ShiftType]
    ) -> None:
        """Should detect when worker assigned during unavailability."""
        periods = [
            PeriodAssignment(
                period_index=0,
                period_start=date(2026, 1, 1),
                period_end=date(2026, 1, 7),
                assignments={
                    "W1": [
                        ShiftInstance(
                            shift_type_id="day",
                            period_index=0,
                            date=date(2026, 1, 1),
                            worker_id="W1",
                        ),
                    ],
                },
            ),
        ]
        schedule = make_schedule(periods, workers, shift_types)

        availabilities = [
            Availability(
                worker_id="W1",
                start_date=date(2026, 1, 1),
                end_date=date(2026, 1, 1),
                availability_type="unavailable",
            ),
        ]

        validator = ScheduleValidator(
            schedule=schedule, availabilities=availabilities
        )
        result = validator.validate()
        assert not result.is_valid
        assert any(v["type"] == "availability" for v in result.violations)

    def test_mid_period_unavailability_detected(
        self, workers: list[Worker], shift_types: list[ShiftType]
    ) -> None:
        """
        SolutionExtractor always stamps ShiftInstance.date as period_start,
        so an unavailability range that overlaps the period but doesn't
        happen to cover period_start must still be caught (period-granular
        check), not missed as it was when compared only against shift.date.
        """
        periods = [
            PeriodAssignment(
                period_index=0,
                period_start=date(2026, 1, 1),
                period_end=date(2026, 1, 7),
                assignments={
                    "W1": [
                        ShiftInstance(
                            shift_type_id="day",
                            period_index=0,
                            date=date(2026, 1, 1),  # stamped as period_start
                            worker_id="W1",
                        ),
                    ],
                },
            ),
        ]
        schedule = make_schedule(periods, workers, shift_types)

        # Unavailable Jan 4th only - mid-period, NOT on the stamped date.
        availabilities = [
            Availability(
                worker_id="W1",
                start_date=date(2026, 1, 4),
                end_date=date(2026, 1, 4),
                availability_type="unavailable",
            ),
        ]

        result = ScheduleValidator(
            schedule=schedule, availabilities=availabilities
        ).validate()
        assert not result.is_valid
        assert any(
            v["type"] == "availability" and v.get("worker_id") == "W1"
            for v in result.violations
        )

    def test_unavailability_outside_period_not_flagged(
        self, workers: list[Worker], shift_types: list[ShiftType]
    ) -> None:
        """Unavailability entirely outside the period must not be a false positive."""
        periods = [
            PeriodAssignment(
                period_index=0,
                period_start=date(2026, 1, 1),
                period_end=date(2026, 1, 7),
                assignments={
                    "W1": [
                        ShiftInstance(
                            shift_type_id="day",
                            period_index=0,
                            date=date(2026, 1, 1),
                            worker_id="W1",
                        ),
                    ],
                },
            ),
        ]
        schedule = make_schedule(periods, workers, shift_types)

        availabilities = [
            Availability(
                worker_id="W1",
                start_date=date(2026, 1, 10),
                end_date=date(2026, 1, 10),
                availability_type="unavailable",
            ),
        ]

        result = ScheduleValidator(
            schedule=schedule, availabilities=availabilities
        ).validate()
        assert not any(v["type"] == "availability" for v in result.violations)

    def test_shift_type_scoped_unavailability_detected(
        self, workers: list[Worker], shift_types: list[ShiftType]
    ) -> None:
        """Scoped unavailability (shift_type_id set) must still be honored."""
        periods = [
            PeriodAssignment(
                period_index=0,
                period_start=date(2026, 1, 1),
                period_end=date(2026, 1, 7),
                assignments={
                    "W4": [
                        ShiftInstance(
                            shift_type_id="night",
                            period_index=0,
                            date=date(2026, 1, 1),
                            worker_id="W4",
                        ),
                    ],
                },
            ),
        ]
        schedule = make_schedule(periods, workers, shift_types)

        availabilities = [
            Availability(
                worker_id="W4",
                start_date=date(2026, 1, 1),
                end_date=date(2026, 1, 7),
                availability_type="unavailable",
                shift_type_id="night",
            ),
        ]

        result = ScheduleValidator(
            schedule=schedule, availabilities=availabilities
        ).validate()
        assert not result.is_valid
        assert any(v["type"] == "availability" for v in result.violations)

    def test_shift_type_scoped_unavailability_does_not_block_other_shifts(
        self, valid_schedule: Schedule
    ) -> None:
        """Scoped unavailability for a different shift type must not false-positive."""
        # W1 is only assigned to "day" in valid_schedule; scoping the
        # unavailability to "night" must not affect W1's day assignment.
        availabilities = [
            Availability(
                worker_id="W1",
                start_date=date(2026, 1, 1),
                end_date=date(2026, 1, 7),
                availability_type="unavailable",
                shift_type_id="night",
            ),
        ]

        result = ScheduleValidator(
            schedule=valid_schedule, availabilities=availabilities
        ).validate()
        assert result.is_valid, f"Unexpected violations: {result.violations}"


class TestWorkerShiftLimitValidation:
    """Test the per-(worker, period) exclusivity check (defect A)."""

    def test_overlapping_shifts_exceeding_default_limit_detected(
        self, workers: list[Worker], shift_types: list[ShiftType]
    ) -> None:
        """A worker with 3 shifts in one period must be caught (default limit 1)."""
        periods = [
            PeriodAssignment(
                period_index=0,
                period_start=date(2026, 1, 1),
                period_end=date(2026, 1, 7),
                assignments={
                    "W1": [
                        ShiftInstance(
                            shift_type_id="day",
                            period_index=0,
                            date=date(2026, 1, 1),
                            worker_id="W1",
                        ),
                        ShiftInstance(
                            shift_type_id="day",
                            period_index=0,
                            date=date(2026, 1, 1),
                            worker_id="W1",
                        ),
                        ShiftInstance(
                            shift_type_id="night",
                            period_index=0,
                            date=date(2026, 1, 1),
                            worker_id="W1",
                        ),
                    ],
                },
            ),
        ]
        schedule = make_schedule(periods, workers, shift_types)

        validator = ScheduleValidator(schedule=schedule)
        result = validator.validate()
        assert not result.is_valid
        assert any(v["type"] == "worker_shift_limit" for v in result.violations)

    def test_one_shift_per_worker_per_period_passes(
        self, valid_schedule: Schedule
    ) -> None:
        """The baseline valid schedule has no worker double-booked."""
        result = ScheduleValidator(schedule=valid_schedule).validate()
        assert not any(v["type"] == "worker_shift_limit" for v in result.violations)

    def test_custom_max_shifts_per_period_relaxes_the_check(
        self, workers: list[Worker], shift_types: list[ShiftType]
    ) -> None:
        """A configurable limit lets callers allow more than 1 shift per period."""
        periods = [
            PeriodAssignment(
                period_index=0,
                period_start=date(2026, 1, 1),
                period_end=date(2026, 1, 7),
                assignments={
                    "W1": [
                        ShiftInstance(
                            shift_type_id="day",
                            period_index=0,
                            date=date(2026, 1, 1),
                            worker_id="W1",
                        ),
                        ShiftInstance(
                            shift_type_id="night",
                            period_index=0,
                            date=date(2026, 1, 1),
                            worker_id="W1",
                        ),
                    ],
                },
            ),
        ]
        schedule = make_schedule(periods, workers, shift_types)

        default_result = ScheduleValidator(schedule=schedule).validate()
        assert any(
            v["type"] == "worker_shift_limit" for v in default_result.violations
        )

        lenient_result = ScheduleValidator(
            schedule=schedule, max_shifts_per_period=2
        ).validate()
        assert not any(
            v["type"] == "worker_shift_limit" for v in lenient_result.violations
        )


class TestSkillsValidation:
    """Test the required-attributes (skills) check."""

    def test_missing_required_attribute_detected(self) -> None:
        """A worker lacking a required attribute must not be assignable."""
        icu_shift = ShiftType(
            id="icu",
            name="ICU Shift",
            category="day",
            start_time=time(7, 0),
            end_time=time(15, 0),
            duration_hours=8.0,
            workers_required=1,
            required_attributes={"license": "RN"},
        )
        worker = Worker(id="W1", name="Alice", attributes={"license": "LPN"})
        periods = [
            PeriodAssignment(
                period_index=0,
                period_start=date(2026, 1, 1),
                period_end=date(2026, 1, 7),
                assignments={
                    "W1": [
                        ShiftInstance(
                            shift_type_id="icu",
                            period_index=0,
                            date=date(2026, 1, 1),
                            worker_id="W1",
                        ),
                    ],
                },
            ),
        ]
        schedule = make_schedule(periods, [worker], [icu_shift])

        result = ScheduleValidator(schedule=schedule).validate()
        assert not result.is_valid
        assert any(v["type"] == "skills" for v in result.violations)

    def test_satisfied_required_attribute_passes(self) -> None:
        """A worker with the matching attribute value is assignable."""
        icu_shift = ShiftType(
            id="icu",
            name="ICU Shift",
            category="day",
            start_time=time(7, 0),
            end_time=time(15, 0),
            duration_hours=8.0,
            workers_required=1,
            required_attributes={"license": "RN"},
        )
        worker = Worker(id="W1", name="Alice", attributes={"license": "RN"})
        periods = [
            PeriodAssignment(
                period_index=0,
                period_start=date(2026, 1, 1),
                period_end=date(2026, 1, 7),
                assignments={
                    "W1": [
                        ShiftInstance(
                            shift_type_id="icu",
                            period_index=0,
                            date=date(2026, 1, 1),
                            worker_id="W1",
                        ),
                    ],
                },
            ),
        ]
        schedule = make_schedule(periods, [worker], [icu_shift])

        result = ScheduleValidator(schedule=schedule).validate()
        assert result.is_valid, f"Unexpected violations: {result.violations}"

    def test_unrestricted_shift_type_is_unconstrained(self) -> None:
        """A shift type with no required_attributes accepts any worker."""
        any_shift = ShiftType(
            id="general",
            name="General Shift",
            category="day",
            start_time=time(7, 0),
            end_time=time(15, 0),
            duration_hours=8.0,
            workers_required=1,
        )
        worker = Worker(id="W1", name="Alice")
        periods = [
            PeriodAssignment(
                period_index=0,
                period_start=date(2026, 1, 1),
                period_end=date(2026, 1, 7),
                assignments={
                    "W1": [
                        ShiftInstance(
                            shift_type_id="general",
                            period_index=0,
                            date=date(2026, 1, 1),
                            worker_id="W1",
                        ),
                    ],
                },
            ),
        ]
        schedule = make_schedule(periods, [worker], [any_shift])

        result = ScheduleValidator(schedule=schedule).validate()
        assert result.is_valid

    def test_collection_valued_attribute_requires_strict_equality(self) -> None:
        """A worker holding a set of certifications does not satisfy a scalar
        requirement via membership -- the validator mirrors SkillsConstraint's
        strict `worker.attributes.get(key) == value` equality check, under which
        the engine would refuse to assign this worker (and thus so must the
        validator)."""
        icu_shift = ShiftType(
            id="icu",
            name="ICU Shift",
            category="day",
            start_time=time(7, 0),
            end_time=time(15, 0),
            duration_hours=8.0,
            workers_required=1,
            required_attributes={"certifications": "ACLS"},
        )
        worker = Worker(
            id="W1",
            name="Alice",
            attributes={"certifications": {"ACLS", "BLS"}},
        )
        periods = [
            PeriodAssignment(
                period_index=0,
                period_start=date(2026, 1, 1),
                period_end=date(2026, 1, 7),
                assignments={
                    "W1": [
                        ShiftInstance(
                            shift_type_id="icu",
                            period_index=0,
                            date=date(2026, 1, 1),
                            worker_id="W1",
                        ),
                    ],
                },
            ),
        ]
        schedule = make_schedule(periods, [worker], [icu_shift])

        result = ScheduleValidator(schedule=schedule).validate()
        assert not result.is_valid
        assert any(v["type"] == "skills" for v in result.violations)


class TestStatistics:
    """Test statistics computation."""

    def test_statistics_computed(self, valid_schedule: Schedule) -> None:
        """Validator should compute schedule statistics."""
        validator = ScheduleValidator(schedule=valid_schedule)
        result = validator.validate()

        assert "total_assignments" in result.statistics
        assert "assignments_per_worker" in result.statistics

    def test_fairness_metrics_computed(self, valid_schedule: Schedule) -> None:
        """Validator should compute fairness metrics."""
        validator = ScheduleValidator(schedule=valid_schedule)
        result = validator.validate()

        assert "fairness" in result.statistics


class TestRequestValidation:
    """Test request fulfillment tracking (defect D)."""

    def test_request_fulfillment_tracked(
        self, workers: list[Worker], shift_types: list[ShiftType]
    ) -> None:
        """Should track request fulfillment rate."""
        periods = [
            PeriodAssignment(
                period_index=0,
                period_start=date(2026, 1, 1),
                period_end=date(2026, 1, 7),
                assignments={
                    "W1": [
                        ShiftInstance(
                            shift_type_id="day",
                            period_index=0,
                            date=date(2026, 1, 1),
                            worker_id="W1",
                        ),
                    ],
                    "W2": [
                        ShiftInstance(
                            shift_type_id="day",
                            period_index=0,
                            date=date(2026, 1, 1),
                            worker_id="W2",
                        ),
                        ShiftInstance(
                            shift_type_id="night",
                            period_index=0,
                            date=date(2026, 1, 1),
                            worker_id="W2",
                        ),
                    ],
                },
            ),
        ]
        schedule = make_schedule(periods, workers, shift_types)

        # W1 wants day shift (fulfilled), W2 doesn't want night (violated)
        requests = [
            SchedulingRequest(
                worker_id="W1",
                start_date=date(2026, 1, 1),
                end_date=date(2026, 1, 1),
                request_type="positive",
                shift_type_id="day",
            ),
            SchedulingRequest(
                worker_id="W2",
                start_date=date(2026, 1, 1),
                end_date=date(2026, 1, 1),
                request_type="negative",
                shift_type_id="night",
            ),
        ]

        validator = ScheduleValidator(schedule=schedule, requests=requests)
        result = validator.validate()

        assert "request_fulfillment" in result.statistics
        # One fulfilled, one violated = 50%
        assert result.statistics["request_fulfillment"]["rate"] == 0.5

    def test_full_period_positive_request_fully_fulfilled(
        self, workers: list[Worker], shift_types: list[ShiftType]
    ) -> None:
        """
        A request spanning an entire week-long period must be scored on a
        per-period, at-least-once basis: previously walking every calendar
        day against day-stamped keys diluted a fully-honored week-long
        request down to ~14% (1 matching day out of 7). One overlapping
        period with the shift assigned is 100% fulfilled.
        """
        periods = [
            PeriodAssignment(
                period_index=0,
                period_start=date(2026, 1, 1),
                period_end=date(2026, 1, 7),
                assignments={
                    "W1": [
                        ShiftInstance(
                            shift_type_id="day",
                            period_index=0,
                            date=date(2026, 1, 1),  # always stamped period_start
                            worker_id="W1",
                        ),
                    ],
                },
            ),
        ]
        schedule = make_schedule(periods, workers, shift_types)

        requests = [
            SchedulingRequest(
                worker_id="W1",
                start_date=date(2026, 1, 1),
                end_date=date(2026, 1, 7),
                request_type="positive",
                shift_type_id="day",
            ),
        ]

        result = ScheduleValidator(schedule=schedule, requests=requests).validate()
        stats = result.statistics["request_fulfillment"]
        assert stats["total_requests"] == 1
        assert stats["fulfilled"] == 1
        assert stats["violated"] == 0
        assert stats["rate"] == 1.0

    def test_negative_request_violated_if_assigned_in_any_overlapping_period(
        self, workers: list[Worker], shift_types: list[ShiftType]
    ) -> None:
        """A negative request spanning multiple periods is violated by even one hit."""
        periods = [
            PeriodAssignment(
                period_index=0,
                period_start=date(2026, 1, 1),
                period_end=date(2026, 1, 7),
                assignments={
                    "W2": [
                        ShiftInstance(
                            shift_type_id="day",
                            period_index=0,
                            date=date(2026, 1, 1),
                            worker_id="W2",
                        ),
                    ],
                },
            ),
            PeriodAssignment(
                period_index=1,
                period_start=date(2026, 1, 8),
                period_end=date(2026, 1, 14),
                assignments={
                    "W2": [
                        ShiftInstance(
                            shift_type_id="night",
                            period_index=1,
                            date=date(2026, 1, 8),
                            worker_id="W2",
                        ),
                    ],
                },
            ),
        ]
        schedule = make_schedule(periods, workers, shift_types)

        requests = [
            SchedulingRequest(
                worker_id="W2",
                start_date=date(2026, 1, 1),
                end_date=date(2026, 1, 14),
                request_type="negative",
                shift_type_id="night",
            ),
        ]

        result = ScheduleValidator(schedule=schedule, requests=requests).validate()
        stats = result.statistics["request_fulfillment"]
        assert stats["fulfilled"] == 0
        assert stats["violated"] == 1

    def test_negative_request_fulfilled_when_avoided_in_every_period(
        self, workers: list[Worker], shift_types: list[ShiftType]
    ) -> None:
        """A negative request is only fulfilled if avoided in EVERY overlapping period."""
        periods = [
            PeriodAssignment(
                period_index=0,
                period_start=date(2026, 1, 1),
                period_end=date(2026, 1, 7),
                assignments={
                    "W2": [
                        ShiftInstance(
                            shift_type_id="day",
                            period_index=0,
                            date=date(2026, 1, 1),
                            worker_id="W2",
                        ),
                    ],
                },
            ),
            PeriodAssignment(
                period_index=1,
                period_start=date(2026, 1, 8),
                period_end=date(2026, 1, 14),
                assignments={
                    "W2": [
                        ShiftInstance(
                            shift_type_id="day",
                            period_index=1,
                            date=date(2026, 1, 8),
                            worker_id="W2",
                        ),
                    ],
                },
            ),
        ]
        schedule = make_schedule(periods, workers, shift_types)

        requests = [
            SchedulingRequest(
                worker_id="W2",
                start_date=date(2026, 1, 1),
                end_date=date(2026, 1, 14),
                request_type="negative",
                shift_type_id="night",
            ),
        ]

        result = ScheduleValidator(schedule=schedule, requests=requests).validate()
        stats = result.statistics["request_fulfillment"]
        assert stats["fulfilled"] == 1
        assert stats["violated"] == 0
        assert stats["rate"] == 1.0
