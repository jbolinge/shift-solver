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


@pytest.fixture
def workers() -> list[Worker]:
    """Sample workers."""
    return [
        Worker(id="W1", name="Alice"),
        Worker(id="W2", name="Bob"),
        Worker(id="W3", name="Charlie", restricted_shifts=frozenset(["night"])),
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
def valid_schedule(
    workers: list[Worker], shift_types: list[ShiftType]
) -> Schedule:
    """A valid schedule with proper coverage."""
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
    return Schedule(
        schedule_id="TEST-001",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 8),
        period_type="week",
        periods=periods,
        workers=workers,
        shift_types=shift_types,
    )


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
        assert result.is_valid


class TestCoverageValidation:
    """Test coverage requirement validation."""

    def test_missing_coverage_detected(
        self, workers: list[Worker], shift_types: list[ShiftType]
    ) -> None:
        """Should detect when coverage requirements not met."""
        # Only 1 worker assigned to day shift (requires 2)
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
        schedule = Schedule(
            schedule_id="TEST-001",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 8),
            period_type="week",
            periods=periods,
            workers=workers,
            shift_types=shift_types,
        )

        validator = ScheduleValidator(schedule=schedule)
        result = validator.validate()
        assert not result.is_valid
        assert any(v["type"] == "coverage" for v in result.violations)


class TestRestrictionValidation:
    """Test restriction violation detection."""

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
        schedule = Schedule(
            schedule_id="TEST-001",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 8),
            period_type="week",
            periods=periods,
            workers=workers,
            shift_types=shift_types,
        )

        validator = ScheduleValidator(schedule=schedule)
        result = validator.validate()
        assert not result.is_valid
        assert any(v["type"] == "restriction" for v in result.violations)


class TestAvailabilityValidation:
    """Test availability violation detection."""

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
        schedule = Schedule(
            schedule_id="TEST-001",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 8),
            period_type="week",
            periods=periods,
            workers=workers,
            shift_types=shift_types,
        )

        # W1 is unavailable on Jan 1
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
    """Test request fulfillment tracking."""

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
        schedule = Schedule(
            schedule_id="TEST-001",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 8),
            period_type="week",
            periods=periods,
            workers=workers,
            shift_types=shift_types,
        )

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
