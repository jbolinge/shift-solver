"""Tests for FeasibilityChecker pre-solve validation."""

from datetime import date, time

import pytest

from shift_solver.constraints.base import ConstraintConfig
from shift_solver.models import Availability, SchedulingRequest, ShiftType, Worker
from shift_solver.validation.feasibility import FeasibilityChecker, FeasibilityResult


@pytest.fixture
def workers() -> list[Worker]:
    """Sample workers for testing."""
    return [
        Worker(id="W1", name="Alice"),
        Worker(id="W2", name="Bob"),
        Worker(id="W3", name="Charlie"),
    ]


@pytest.fixture
def shift_types() -> list[ShiftType]:
    """Sample shift types for testing."""
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
        ),
    ]


@pytest.fixture
def period_dates() -> list[tuple[date, date]]:
    """Sample period dates."""
    return [
        (date(2026, 1, 1), date(2026, 1, 7)),
        (date(2026, 1, 8), date(2026, 1, 14)),
    ]


class TestFeasibilityResult:
    """Test FeasibilityResult data class."""

    def test_feasible_result(self) -> None:
        """Feasible result has no issues."""
        result = FeasibilityResult(is_feasible=True, issues=[])
        assert result.is_feasible
        assert len(result.issues) == 0

    def test_infeasible_result_with_issues(self) -> None:
        """Infeasible result contains issues."""
        issues = [
            {"type": "coverage", "message": "Not enough workers", "severity": "error"}
        ]
        result = FeasibilityResult(is_feasible=False, issues=issues)
        assert not result.is_feasible
        assert len(result.issues) == 1

    def test_result_with_warnings(self) -> None:
        """Result can contain warnings even if feasible."""
        warnings = [
            {"type": "balance", "message": "Uneven distribution", "severity": "warning"}
        ]
        result = FeasibilityResult(is_feasible=True, issues=[], warnings=warnings)
        assert result.is_feasible
        assert len(result.warnings) == 1


class TestFeasibilityChecker:
    """Test FeasibilityChecker class."""

    def test_checker_creation(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Checker should be created with required data."""
        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
        )
        assert checker is not None

    def test_valid_inputs_are_feasible(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Valid inputs should be feasible."""
        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
        )
        result = checker.check()
        assert result.is_feasible


class TestCoverageChecks:
    """Test coverage requirement checks."""

    def test_insufficient_workers_for_coverage(
        self,
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Should detect when there aren't enough workers."""
        # Only 1 worker but day shift requires 2
        workers = [Worker(id="W1", name="Alice")]
        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
        )
        result = checker.check()
        assert not result.is_feasible
        assert any(i["type"] == "coverage" for i in result.issues)

    def test_sufficient_workers_for_coverage(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Should pass when enough workers available."""
        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
        )
        result = checker.check()
        assert result.is_feasible

    def test_empty_workers_list(
        self,
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Empty workers list should be infeasible."""
        checker = FeasibilityChecker(
            workers=[],
            shift_types=shift_types,
            period_dates=period_dates,
        )
        result = checker.check()
        assert not result.is_feasible
        assert any(i["type"] == "coverage" for i in result.issues)


class TestAvailabilityChecks:
    """Test availability conflict checks."""

    def test_all_workers_unavailable_same_period(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Should detect when all workers unavailable for a period."""
        # All workers unavailable for first period
        availabilities = [
            Availability(
                worker_id="W1",
                start_date=date(2026, 1, 1),
                end_date=date(2026, 1, 7),
                availability_type="unavailable",
            ),
            Availability(
                worker_id="W2",
                start_date=date(2026, 1, 1),
                end_date=date(2026, 1, 7),
                availability_type="unavailable",
            ),
            Availability(
                worker_id="W3",
                start_date=date(2026, 1, 1),
                end_date=date(2026, 1, 7),
                availability_type="unavailable",
            ),
        ]
        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            availabilities=availabilities,
        )
        result = checker.check()
        assert not result.is_feasible
        assert any(i["type"] == "availability" for i in result.issues)

    def test_partial_availability_is_feasible(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Should pass when some workers available."""
        # Only one worker unavailable
        availabilities = [
            Availability(
                worker_id="W1",
                start_date=date(2026, 1, 1),
                end_date=date(2026, 1, 7),
                availability_type="unavailable",
            ),
        ]
        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            availabilities=availabilities,
        )
        result = checker.check()
        assert result.is_feasible


class TestRestrictionChecks:
    """Test worker restriction checks."""

    def test_all_workers_restricted_from_shift(
        self,
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Should detect when all workers restricted from a shift type."""
        # All workers restricted from day shift
        workers = [
            Worker(id="W1", name="Alice", restricted_shifts=frozenset(["day"])),
            Worker(id="W2", name="Bob", restricted_shifts=frozenset(["day"])),
        ]
        shift_types = [
            ShiftType(
                id="day",
                name="Day Shift",
                category="day",
                start_time=time(7, 0),
                end_time=time(15, 0),
                duration_hours=8.0,
                workers_required=1,
            ),
        ]
        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
        )
        result = checker.check()
        assert not result.is_feasible
        assert any(i["type"] == "restriction" for i in result.issues)

    def test_some_workers_can_work_shift(
        self,
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Should pass when at least required workers can work shift."""
        workers = [
            Worker(id="W1", name="Alice", restricted_shifts=frozenset(["day"])),
            Worker(id="W2", name="Bob"),  # No restrictions
            Worker(id="W3", name="Charlie"),  # No restrictions
        ]
        shift_types = [
            ShiftType(
                id="day",
                name="Day Shift",
                category="day",
                start_time=time(7, 0),
                end_time=time(15, 0),
                duration_hours=8.0,
                workers_required=1,
            ),
        ]
        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
        )
        result = checker.check()
        assert result.is_feasible


class TestDateRangeChecks:
    """Test date range validation."""

    def test_empty_period_dates(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """Empty period dates should be infeasible."""
        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=[],
        )
        result = checker.check()
        assert not result.is_feasible
        assert any(i["type"] == "period" for i in result.issues)

    def test_valid_period_dates(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Valid period dates should pass."""
        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
        )
        result = checker.check()
        assert result.is_feasible


class TestCombinedChecks:
    """Test combined feasibility scenarios."""

    def test_restriction_plus_availability_makes_infeasible(
        self,
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Combination of restrictions and availability can make infeasible."""
        workers = [
            Worker(id="W1", name="Alice", restricted_shifts=frozenset(["day"])),
            Worker(id="W2", name="Bob"),
            Worker(id="W3", name="Charlie"),
        ]
        shift_types = [
            ShiftType(
                id="day",
                name="Day Shift",
                category="day",
                start_time=time(7, 0),
                end_time=time(15, 0),
                duration_hours=8.0,
                workers_required=2,  # Need 2 workers
            ),
        ]
        # W2 and W3 unavailable, only W1 left but restricted
        availabilities = [
            Availability(
                worker_id="W2",
                start_date=date(2026, 1, 1),
                end_date=date(2026, 1, 14),
                availability_type="unavailable",
            ),
            Availability(
                worker_id="W3",
                start_date=date(2026, 1, 1),
                end_date=date(2026, 1, 14),
                availability_type="unavailable",
            ),
        ]
        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            availabilities=availabilities,
        )
        result = checker.check()
        assert not result.is_feasible


class TestCoverageVsRestrictions:
    """Tests for coverage vs restrictions check (scheduler-53)."""

    def test_all_workers_restricted_from_required_shift(self) -> None:
        """All workers restricted from shift that requires coverage."""
        workers = [
            Worker(id="W1", name="Alice", restricted_shifts=frozenset(["night"])),
            Worker(id="W2", name="Bob", restricted_shifts=frozenset(["night"])),
            Worker(id="W3", name="Charlie", restricted_shifts=frozenset(["night"])),
        ]
        shift_types = [
            ShiftType(
                id="night",
                name="Night Shift",
                category="night",
                start_time=time(23, 0),
                end_time=time(7, 0),
                duration_hours=8.0,
                workers_required=2,
            ),
        ]
        period_dates = [(date(2026, 1, 1), date(2026, 1, 7))]

        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
        )
        result = checker.check()

        assert not result.is_feasible
        assert any(i["type"] == "restriction" for i in result.issues)
        # Check error message is descriptive
        restriction_issue = next(i for i in result.issues if i["type"] == "restriction")
        assert "Night Shift" in restriction_issue["message"]
        assert "0 available" in restriction_issue["message"]
        assert "2 required" in restriction_issue["message"]

    def test_partial_restrictions_sufficient_workers(self) -> None:
        """Some workers restricted but still enough available."""
        workers = [
            Worker(id="W1", name="Alice", restricted_shifts=frozenset(["night"])),
            Worker(id="W2", name="Bob"),
            Worker(id="W3", name="Charlie"),
        ]
        shift_types = [
            ShiftType(
                id="night",
                name="Night Shift",
                category="night",
                start_time=time(23, 0),
                end_time=time(7, 0),
                duration_hours=8.0,
                workers_required=2,
            ),
        ]
        period_dates = [(date(2026, 1, 1), date(2026, 1, 7))]

        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
        )
        result = checker.check()
        assert result.is_feasible

    def test_restrictions_plus_unavailability_combined(self) -> None:
        """Workers restricted and remaining unavailable."""
        workers = [
            Worker(id="W1", name="Alice", restricted_shifts=frozenset(["night"])),
            Worker(id="W2", name="Bob"),
            Worker(id="W3", name="Charlie"),
        ]
        shift_types = [
            ShiftType(
                id="night",
                name="Night Shift",
                category="night",
                start_time=time(23, 0),
                end_time=time(7, 0),
                duration_hours=8.0,
                workers_required=2,
            ),
        ]
        period_dates = [(date(2026, 1, 1), date(2026, 1, 7))]
        # Bob and Charlie unavailable
        availabilities = [
            Availability(
                worker_id="W2",
                start_date=date(2026, 1, 1),
                end_date=date(2026, 1, 7),
                availability_type="unavailable",
            ),
            Availability(
                worker_id="W3",
                start_date=date(2026, 1, 1),
                end_date=date(2026, 1, 7),
                availability_type="unavailable",
            ),
        ]

        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            availabilities=availabilities,
        )
        result = checker.check()

        assert not result.is_feasible
        # Should get combined issue
        assert any(i["type"] == "combined" for i in result.issues)


class TestShiftFrequencyFeasibility:
    """Tests for shift frequency requirement feasibility checks (scheduler-96)."""

    def test_worker_restricted_from_all_required_shift_types(
        self,
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Infeasible when worker is restricted from ALL required shift types."""
        from shift_solver.models import ShiftFrequencyRequirement

        workers = [
            # W1 restricted from both mvsc_day and mvsc_night
            Worker(
                id="W1",
                name="Alice",
                restricted_shifts=frozenset(["mvsc_day", "mvsc_night"]),
            ),
            Worker(id="W2", name="Bob"),
        ]
        shift_types = [
            ShiftType(
                id="mvsc_day",
                name="MVSC Day",
                category="day",
                start_time=time(7, 0),
                end_time=time(15, 0),
                duration_hours=8.0,
                workers_required=1,
            ),
            ShiftType(
                id="mvsc_night",
                name="MVSC Night",
                category="night",
                start_time=time(23, 0),
                end_time=time(7, 0),
                duration_hours=8.0,
                workers_required=1,
            ),
        ]
        requirements = [
            ShiftFrequencyRequirement(
                worker_id="W1",
                shift_types=frozenset(["mvsc_day", "mvsc_night"]),
                max_periods_between=4,
            )
        ]

        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            shift_frequency_requirements=requirements,
        )
        result = checker.check()

        assert not result.is_feasible
        assert any(i["type"] == "shift_frequency" for i in result.issues)
        issue = next(i for i in result.issues if i["type"] == "shift_frequency")
        assert "W1" in issue["message"] or "Alice" in issue["message"]
        assert "restricted" in issue["message"].lower()

    def test_worker_restricted_from_some_shift_types_feasible(
        self,
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Feasible when worker can work at least one of the required shift types."""
        from shift_solver.models import ShiftFrequencyRequirement

        workers = [
            # W1 restricted from only mvsc_day, can still do mvsc_night
            Worker(id="W1", name="Alice", restricted_shifts=frozenset(["mvsc_day"])),
            Worker(id="W2", name="Bob"),
        ]
        shift_types = [
            ShiftType(
                id="mvsc_day",
                name="MVSC Day",
                category="day",
                start_time=time(7, 0),
                end_time=time(15, 0),
                duration_hours=8.0,
                workers_required=1,
            ),
            ShiftType(
                id="mvsc_night",
                name="MVSC Night",
                category="night",
                start_time=time(23, 0),
                end_time=time(7, 0),
                duration_hours=8.0,
                workers_required=1,
            ),
        ]
        requirements = [
            ShiftFrequencyRequirement(
                worker_id="W1",
                shift_types=frozenset(["mvsc_day", "mvsc_night"]),
                max_periods_between=4,
            )
        ]

        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            shift_frequency_requirements=requirements,
        )
        result = checker.check()

        assert result.is_feasible

    def test_unknown_shift_type_in_requirement(
        self,
        workers: list[Worker],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Infeasible when requirement references unknown shift type."""
        from shift_solver.models import ShiftFrequencyRequirement

        shift_types = [
            ShiftType(
                id="day",
                name="Day Shift",
                category="day",
                start_time=time(7, 0),
                end_time=time(15, 0),
                duration_hours=8.0,
                workers_required=1,
            ),
        ]
        requirements = [
            ShiftFrequencyRequirement(
                worker_id="W1",
                shift_types=frozenset(["unknown_shift"]),
                max_periods_between=4,
            )
        ]

        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            shift_frequency_requirements=requirements,
        )
        result = checker.check()

        assert not result.is_feasible
        assert any(i["type"] == "shift_frequency" for i in result.issues)
        issue = next(i for i in result.issues if i["type"] == "shift_frequency")
        assert "unknown_shift" in issue["message"]

    def test_max_periods_between_exceeds_num_periods(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """Warning when max_periods_between > num_periods."""
        from shift_solver.models import ShiftFrequencyRequirement

        # Only 2 periods
        period_dates = [
            (date(2026, 1, 1), date(2026, 1, 7)),
            (date(2026, 1, 8), date(2026, 1, 14)),
        ]
        requirements = [
            ShiftFrequencyRequirement(
                worker_id="W1",
                shift_types=frozenset(["day"]),
                max_periods_between=10,  # Much larger than 2 periods
            )
        ]

        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            shift_frequency_requirements=requirements,
        )
        result = checker.check()

        # This is a warning, not an error (still feasible)
        assert result.is_feasible
        assert any(w["type"] == "shift_frequency" for w in result.warnings)

    def test_unknown_worker_in_requirement(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Warning when requirement references unknown worker."""
        from shift_solver.models import ShiftFrequencyRequirement

        requirements = [
            ShiftFrequencyRequirement(
                worker_id="UNKNOWN_WORKER",
                shift_types=frozenset(["day"]),
                max_periods_between=4,
            )
        ]

        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            shift_frequency_requirements=requirements,
        )
        result = checker.check()

        # This is a warning, not an error
        assert result.is_feasible
        assert any(w["type"] == "shift_frequency" for w in result.warnings)
        warning = next(w for w in result.warnings if w["type"] == "shift_frequency")
        assert "UNKNOWN_WORKER" in warning["message"]

    def test_no_requirements_is_feasible(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """No shift_frequency_requirements should be feasible."""
        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            shift_frequency_requirements=[],
        )
        result = checker.check()
        assert result.is_feasible


class TestShiftOrderPreferenceFeasibility:
    """Tests for shift order preference feasibility checks."""

    def test_no_preferences_is_feasible(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """No shift_order_preferences should be feasible."""
        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            shift_order_preferences=[],
        )
        result = checker.check()
        assert result.is_feasible

    def test_unknown_trigger_shift_type(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Warning when trigger references unknown shift type."""
        from shift_solver.models import ShiftOrderPreference

        prefs = [
            ShiftOrderPreference(
                rule_id="test",
                trigger_type="shift_type",
                trigger_value="nonexistent",
                direction="after",
                preferred_type="shift_type",
                preferred_value="day",
            )
        ]
        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            shift_order_preferences=prefs,
        )
        result = checker.check()
        assert result.is_feasible
        assert any(
            w["type"] == "shift_order_preference" and "nonexistent" in w["message"]
            for w in result.warnings
        )

    def test_unknown_trigger_category(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Warning when trigger references unknown category."""
        from shift_solver.models import ShiftOrderPreference

        prefs = [
            ShiftOrderPreference(
                rule_id="test",
                trigger_type="category",
                trigger_value="nonexistent_cat",
                direction="after",
                preferred_type="shift_type",
                preferred_value="day",
            )
        ]
        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            shift_order_preferences=prefs,
        )
        result = checker.check()
        assert result.is_feasible
        assert any(
            w["type"] == "shift_order_preference" and "nonexistent_cat" in w["message"]
            for w in result.warnings
        )

    def test_unknown_preferred_shift_type(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Warning when preferred references unknown shift type."""
        from shift_solver.models import ShiftOrderPreference

        prefs = [
            ShiftOrderPreference(
                rule_id="test",
                trigger_type="shift_type",
                trigger_value="day",
                direction="after",
                preferred_type="shift_type",
                preferred_value="nonexistent",
            )
        ]
        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            shift_order_preferences=prefs,
        )
        result = checker.check()
        assert result.is_feasible
        assert any(
            w["type"] == "shift_order_preference"
            and "preferred" in w["message"]
            and "nonexistent" in w["message"]
            for w in result.warnings
        )

    def test_unknown_worker_ids(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Warning when worker_ids references unknown workers."""
        from shift_solver.models import ShiftOrderPreference

        prefs = [
            ShiftOrderPreference(
                rule_id="test",
                trigger_type="shift_type",
                trigger_value="day",
                direction="after",
                preferred_type="shift_type",
                preferred_value="night",
                worker_ids=frozenset(["UNKNOWN_W"]),
            )
        ]
        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            shift_order_preferences=prefs,
        )
        result = checker.check()
        assert result.is_feasible
        assert any(
            w["type"] == "shift_order_preference" and "UNKNOWN_W" in w["message"]
            for w in result.warnings
        )

    def test_few_periods_warning(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
    ) -> None:
        """Warning when schedule has fewer than 2 periods."""
        from shift_solver.models import ShiftOrderPreference

        prefs = [
            ShiftOrderPreference(
                rule_id="test",
                trigger_type="shift_type",
                trigger_value="day",
                direction="after",
                preferred_type="shift_type",
                preferred_value="night",
            )
        ]
        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=[(date(2026, 1, 1), date(2026, 1, 7))],
            shift_order_preferences=prefs,
        )
        result = checker.check()
        assert result.is_feasible
        assert any(
            w["type"] == "shift_order_preference" and "fewer than 2" in w["message"]
            for w in result.warnings
        )

    def test_all_workers_restricted_from_preferred(
        self,
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Warning when all applicable workers are restricted from preferred shift."""
        from shift_solver.models import ShiftOrderPreference

        workers = [
            Worker(id="W1", name="Alice", restricted_shifts=frozenset(["night"])),
            Worker(id="W2", name="Bob", restricted_shifts=frozenset(["night"])),
            Worker(id="W3", name="Charlie"),  # Can work night (for coverage)
        ]
        shift_types = [
            ShiftType(
                id="day",
                name="Day Shift",
                category="day",
                start_time=time(7, 0),
                end_time=time(15, 0),
                duration_hours=8.0,
                workers_required=1,
            ),
            ShiftType(
                id="night",
                name="Night Shift",
                category="night",
                start_time=time(23, 0),
                end_time=time(7, 0),
                duration_hours=8.0,
                workers_required=1,
            ),
        ]
        prefs = [
            ShiftOrderPreference(
                rule_id="test",
                trigger_type="shift_type",
                trigger_value="day",
                direction="after",
                preferred_type="shift_type",
                preferred_value="night",
                worker_ids=frozenset(["W1", "W2"]),  # Only restricted workers
            )
        ]
        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            shift_order_preferences=prefs,
        )
        result = checker.check()
        assert result.is_feasible
        assert any(
            w["type"] == "shift_order_preference" and "restricted" in w["message"]
            for w in result.warnings
        )


class TestAvailabilityShiftTypeScoping:
    """
    Tests that shift-type-scoped unavailability isn't treated as total
    unavailability (scheduler contract item B.1).
    """

    def test_shift_scoped_unavailability_does_not_trigger_all_unavailable(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """All workers unavailable for ONE shift type only should be feasible."""
        availabilities = [
            Availability(
                worker_id=w.id,
                start_date=period_dates[0][0],
                end_date=period_dates[0][1],
                availability_type="unavailable",
                shift_type_id="night",
            )
            for w in workers
        ]
        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            availabilities=availabilities,
        )
        result = checker.check()

        # Every worker is unavailable for "night" only - they can still
        # cover "day", so this must NOT be flagged as "all unavailable".
        assert not any(i["type"] == "availability" for i in result.issues)

    def test_unscoped_unavailability_still_triggers_all_unavailable(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Total (unscoped) unavailability for everyone is still detected."""
        availabilities = [
            Availability(
                worker_id=w.id,
                start_date=period_dates[0][0],
                end_date=period_dates[0][1],
                availability_type="unavailable",
            )
            for w in workers
        ]
        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            availabilities=availabilities,
        )
        result = checker.check()

        assert not result.is_feasible
        assert any(i["type"] == "availability" for i in result.issues)


class TestCombinedFeasibilityShiftTypeScoping:
    """
    Tests that the combined restriction+availability check respects
    shift-type scoping (scheduler contract item B.1).
    """

    def test_shift_scoped_unavailability_only_blocks_that_shift(self) -> None:
        """Workers unavailable for night only shouldn't block day coverage."""
        workers = [
            Worker(id="W1", name="Alice"),
            Worker(id="W2", name="Bob"),
        ]
        shift_types = [
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
            ),
        ]
        period_dates = [(date(2026, 1, 1), date(2026, 1, 7))]
        # Both workers unavailable for NIGHT only - day coverage (needs 2)
        # should be unaffected.
        availabilities = [
            Availability(
                worker_id="W1",
                start_date=date(2026, 1, 1),
                end_date=date(2026, 1, 7),
                availability_type="unavailable",
                shift_type_id="night",
            ),
            Availability(
                worker_id="W2",
                start_date=date(2026, 1, 1),
                end_date=date(2026, 1, 7),
                availability_type="unavailable",
                shift_type_id="night",
            ),
        ]

        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            availabilities=availabilities,
        )
        result = checker.check()

        # Day coverage still satisfiable (2 workers available for day);
        # night coverage is genuinely unfillable (0 available) - should be
        # a "combined" issue for night only.
        assert not result.is_feasible
        combined_issues = [i for i in result.issues if i["type"] == "combined"]
        assert any(i["shift_type_id"] == "night" for i in combined_issues)
        assert not any(i["shift_type_id"] == "day" for i in combined_issues)

    def test_shift_scoped_unavailability_does_not_falsely_block_own_shift_workers(
        self,
    ) -> None:
        """Unavailability scoped to a DIFFERENT shift doesn't block this one."""
        workers = [
            Worker(id="W1", name="Alice"),
            Worker(id="W2", name="Bob"),
        ]
        shift_types = [
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
            ),
        ]
        period_dates = [(date(2026, 1, 1), date(2026, 1, 7))]
        # W1 unavailable for day only; W2 alone can't fill day (needs 2),
        # so "combined" will still flag day - the point of this test is
        # that "night" must NOT be falsely flagged too.
        availabilities = [
            Availability(
                worker_id="W1",
                start_date=date(2026, 1, 1),
                end_date=date(2026, 1, 7),
                availability_type="unavailable",
                shift_type_id="day",
            ),
        ]

        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            availabilities=availabilities,
        )
        result = checker.check()

        # W1 can still work night (unavailability is day-scoped only)
        combined_issues = [i for i in result.issues if i["type"] == "combined"]
        assert not any(i["shift_type_id"] == "night" for i in combined_issues)


class TestDuplicateIdChecks:
    """Tests for duplicate worker/shift-type ID detection (scheduler contract item F)."""

    def test_duplicate_worker_ids_is_hard_issue(
        self,
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Duplicate worker IDs should be a hard (infeasible) issue."""
        workers = [
            Worker(id="W1", name="Alice"),
            Worker(id="W1", name="Alice Duplicate"),
            Worker(id="W2", name="Bob"),
        ]
        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
        )
        result = checker.check()

        assert not result.is_feasible
        assert any(i["type"] == "duplicate_id" for i in result.issues)
        issue = next(i for i in result.issues if i["type"] == "duplicate_id")
        assert "W1" in issue["message"]

    def test_duplicate_shift_type_ids_is_hard_issue(
        self,
        workers: list[Worker],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Duplicate shift type IDs should be a hard (infeasible) issue."""
        shift_types = [
            ShiftType(
                id="day",
                name="Day Shift",
                category="day",
                start_time=time(7, 0),
                end_time=time(15, 0),
                duration_hours=8.0,
                workers_required=1,
            ),
            ShiftType(
                id="day",
                name="Day Shift Duplicate",
                category="day",
                start_time=time(7, 0),
                end_time=time(15, 0),
                duration_hours=8.0,
                workers_required=1,
            ),
        ]
        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
        )
        result = checker.check()

        assert not result.is_feasible
        assert any(i["type"] == "duplicate_id" for i in result.issues)
        issue = next(i for i in result.issues if i["type"] == "duplicate_id")
        assert "day" in issue["message"]

    def test_no_duplicates_is_feasible(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Unique IDs should not trigger the duplicate_id check."""
        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
        )
        result = checker.check()

        assert not any(i["type"] == "duplicate_id" for i in result.issues)


class TestUnknownAvailabilityReferences:
    """
    Tests for warnings on availability records referencing unknown
    workers/shift types (scheduler contract item F).
    """

    def test_unknown_worker_in_availability_warns(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Availability referencing an unknown worker should warn."""
        availabilities = [
            Availability(
                worker_id="UNKNOWN_WORKER",
                start_date=period_dates[0][0],
                end_date=period_dates[0][1],
                availability_type="unavailable",
            ),
        ]
        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            availabilities=availabilities,
        )
        result = checker.check()

        assert result.is_feasible
        assert any(
            w["type"] == "availability" and "UNKNOWN_WORKER" in w["message"]
            for w in result.warnings
        )

    def test_unknown_shift_type_in_availability_warns(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Availability referencing an unknown shift type should warn."""
        availabilities = [
            Availability(
                worker_id=workers[0].id,
                start_date=period_dates[0][0],
                end_date=period_dates[0][1],
                availability_type="unavailable",
                shift_type_id="unknown_shift",
            ),
        ]
        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            availabilities=availabilities,
        )
        result = checker.check()

        assert result.is_feasible
        assert any(
            w["type"] == "availability" and "unknown_shift" in w["message"]
            for w in result.warnings
        )

    def test_known_references_do_not_warn(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Availability referencing known workers/shifts should not warn."""
        availabilities = [
            Availability(
                worker_id=workers[0].id,
                start_date=period_dates[0][0],
                end_date=period_dates[0][1],
                availability_type="unavailable",
                shift_type_id=shift_types[0].id,
            ),
        ]
        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            availabilities=availabilities,
        )
        result = checker.check()

        assert not any(w["type"] == "availability" for w in result.warnings)


class TestRequestFeasibilityChecks:
    """
    Tests for scheduling-request feasibility diagnostics (scheduler
    contract item B.2): hard requests conflicting with restrictions,
    availability, or each other should surface issues; unknown
    worker/shift references should surface warnings.
    """

    def test_hard_positive_request_conflicts_with_restriction(
        self,
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Hard positive request for a shift the worker is restricted from."""
        workers = [
            Worker(id="W1", name="Alice", restricted_shifts=frozenset(["night"])),
            Worker(id="W2", name="Bob"),
        ]
        shift_types = [
            ShiftType(
                id="night",
                name="Night Shift",
                category="night",
                start_time=time(23, 0),
                end_time=time(7, 0),
                duration_hours=8.0,
                workers_required=1,
            ),
        ]
        requests = [
            SchedulingRequest(
                worker_id="W1",
                start_date=period_dates[0][0],
                end_date=period_dates[0][1],
                request_type="positive",
                shift_type_id="night",
                priority=1,
                is_hard=True,
            )
        ]
        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            requests=requests,
        )
        result = checker.check()

        assert not result.is_feasible
        assert any(i["type"] == "request" for i in result.issues)
        issue = next(i for i in result.issues if i["type"] == "request")
        assert "W1" in issue["message"]
        assert "restrict" in issue["message"].lower()

    def test_hard_positive_request_conflicts_with_unavailability(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Hard positive request during full unavailability for that shift."""
        availabilities = [
            Availability(
                worker_id="W1",
                start_date=period_dates[0][0],
                end_date=period_dates[0][1],
                availability_type="unavailable",
                shift_type_id="day",
            ),
        ]
        requests = [
            SchedulingRequest(
                worker_id="W1",
                start_date=period_dates[0][0],
                end_date=period_dates[0][1],
                request_type="positive",
                shift_type_id="day",
                priority=1,
                is_hard=True,
            )
        ]
        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            availabilities=availabilities,
            requests=requests,
        )
        result = checker.check()

        assert not result.is_feasible
        assert any(i["type"] == "request" for i in result.issues)
        issue = next(i for i in result.issues if i["type"] == "request")
        assert "W1" in issue["message"]
        assert "unavailab" in issue["message"].lower()

    def test_hard_positive_request_partial_unavailability_is_feasible(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Request spanning 2 periods, unavailable in only one, is feasible
        under at-least-once-in-range semantics."""
        availabilities = [
            Availability(
                worker_id="W1",
                start_date=period_dates[1][0],
                end_date=period_dates[1][1],
                availability_type="unavailable",
                shift_type_id="day",
            ),
        ]
        requests = [
            SchedulingRequest(
                worker_id="W1",
                start_date=period_dates[0][0],
                end_date=period_dates[1][1],
                request_type="positive",
                shift_type_id="day",
                priority=1,
                is_hard=True,
            )
        ]
        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            availabilities=availabilities,
            requests=requests,
        )
        result = checker.check()

        # W1 is still available in period 0, so the "at least once" request
        # is satisfiable - no request issue should be raised.
        assert not any(i["type"] == "request" for i in result.issues)

    def test_contradictory_hard_requests(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """A hard positive and hard negative request for the same worker/shift/
        period are mutually contradictory."""
        requests = [
            SchedulingRequest(
                worker_id="W1",
                start_date=period_dates[0][0],
                end_date=period_dates[0][1],
                request_type="positive",
                shift_type_id="day",
                priority=1,
                is_hard=True,
            ),
            SchedulingRequest(
                worker_id="W1",
                start_date=period_dates[0][0],
                end_date=period_dates[0][1],
                request_type="negative",
                shift_type_id="day",
                priority=1,
                is_hard=True,
            ),
        ]
        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            requests=requests,
        )
        result = checker.check()

        assert not result.is_feasible
        assert any(i["type"] == "request" for i in result.issues)
        issue = next(i for i in result.issues if i["type"] == "request")
        assert "W1" in issue["message"]

    def test_soft_requests_do_not_trigger_hard_request_checks(
        self,
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Soft (or default) requests never make the schedule infeasible here."""
        workers = [
            Worker(id="W1", name="Alice", restricted_shifts=frozenset(["night"])),
        ]
        shift_types = [
            ShiftType(
                id="night",
                name="Night Shift",
                category="night",
                start_time=time(23, 0),
                end_time=time(7, 0),
                duration_hours=8.0,
                workers_required=1,
            ),
        ]
        requests = [
            SchedulingRequest(
                worker_id="W1",
                start_date=period_dates[0][0],
                end_date=period_dates[0][1],
                request_type="positive",
                shift_type_id="night",
                priority=1,
                # is_hard left as default (None) - not explicitly hard
            )
        ]
        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            requests=requests,
        )
        result = checker.check()

        assert not any(i["type"] == "request" for i in result.issues)

    def test_unknown_worker_in_request_warns(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Request referencing an unknown worker should warn."""
        requests = [
            SchedulingRequest(
                worker_id="UNKNOWN_WORKER",
                start_date=period_dates[0][0],
                end_date=period_dates[0][1],
                request_type="positive",
                shift_type_id=shift_types[0].id,
                priority=1,
            )
        ]
        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            requests=requests,
        )
        result = checker.check()

        assert result.is_feasible
        assert any(
            w["type"] == "request" and "UNKNOWN_WORKER" in w["message"]
            for w in result.warnings
        )

    def test_unknown_shift_type_in_request_warns(
        self,
        workers: list[Worker],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Request referencing an unknown shift type should warn."""
        shift_types = [
            ShiftType(
                id="day",
                name="Day Shift",
                category="day",
                start_time=time(7, 0),
                end_time=time(15, 0),
                duration_hours=8.0,
                workers_required=1,
            ),
        ]
        requests = [
            SchedulingRequest(
                worker_id=workers[0].id,
                start_date=period_dates[0][0],
                end_date=period_dates[0][1],
                request_type="positive",
                shift_type_id="unknown_shift",
                priority=1,
            )
        ]
        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            requests=requests,
        )
        result = checker.check()

        assert result.is_feasible
        assert any(
            w["type"] == "request" and "unknown_shift" in w["message"]
            for w in result.warnings
        )

    def test_no_requests_is_feasible(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """No requests should not affect feasibility."""
        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
        )
        result = checker.check()
        assert result.is_feasible


class TestWorkerShiftLimitCapacity:
    """
    Tests for aggregate per-period demand vs worker_shift_limit capacity.

    worker_shift_limit is registered HARD + enabled by default with
    max_shifts_per_period=1, capping each worker to one assignment per
    period across all shift types combined. Individual per-shift-type
    checks (_check_basic_coverage/_check_combined_feasibility) can't catch
    the case where total demand exceeds total capacity even though each
    shift type is individually fillable, so this must be caught separately.
    """

    def test_aggregate_demand_exceeds_capacity_is_infeasible(
        self,
        period_dates: list[tuple[date, date]],
    ) -> None:
        """3 workers, day(req=2) + night(req=2) = 4 > 3 * 1 capacity."""
        workers = [
            Worker(id="W1", name="Alice"),
            Worker(id="W2", name="Bob"),
            Worker(id="W3", name="Charlie"),
        ]
        shift_types = [
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
                workers_required=2,
            ),
        ]
        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
        )
        result = checker.check()

        assert not result.is_feasible
        issues = [i for i in result.issues if i["type"] == "worker_shift_limit"]
        assert len(issues) == len(period_dates)
        assert issues[0]["total_required"] == 4
        assert issues[0]["capacity"] == 3
        assert issues[0]["shortfall"] == 1
        assert "4" in issues[0]["message"]
        assert "3" in issues[0]["message"]

    def test_demand_at_capacity_is_feasible(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """3 workers, day(req=2) + night(req=1) = 3 == 3 * 1 capacity."""
        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
        )
        result = checker.check()

        assert not any(i["type"] == "worker_shift_limit" for i in result.issues)

    def test_disabled_worker_shift_limit_does_not_bound_feasibility(
        self,
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Aggregate demand over worker count is fine when the constraint
        that would enforce one-shift-per-worker-per-period is disabled."""
        workers = [Worker(id="W1", name="Alice"), Worker(id="W2", name="Bob")]
        shift_types = [
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
                workers_required=2,
            ),
        ]
        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            constraint_configs={
                "worker_shift_limit": ConstraintConfig(
                    enabled=False, is_hard=True, parameters={"max_shifts_per_period": 1}
                ),
            },
        )
        result = checker.check()

        assert not any(i["type"] == "worker_shift_limit" for i in result.issues)

    def test_worker_shift_limit_enforced_regardless_of_is_hard_flag(
        self,
        period_dates: list[tuple[date, date]],
    ) -> None:
        """worker_shift_limit is hard-registered: the solver enforces it
        whenever enabled, ignoring is_hard, so the checker must flag the
        capacity shortfall even with is_hard=False (a shape the programmatic
        API can still produce even though YAML loading rejects it)."""
        workers = [Worker(id="W1", name="Alice"), Worker(id="W2", name="Bob")]
        shift_types = [
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
                workers_required=2,
            ),
        ]
        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            constraint_configs={
                "worker_shift_limit": ConstraintConfig(
                    enabled=True, is_hard=False, parameters={"max_shifts_per_period": 1}
                ),
            },
        )
        result = checker.check()

        assert any(i["type"] == "worker_shift_limit" for i in result.issues)

    def test_higher_max_shifts_per_period_raises_capacity(
        self,
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Configuring a higher max_shifts_per_period raises the capacity
        bound, making previously-over-capacity demand feasible."""
        workers = [Worker(id="W1", name="Alice"), Worker(id="W2", name="Bob")]
        shift_types = [
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
                workers_required=2,
            ),
        ]
        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            constraint_configs={
                "worker_shift_limit": ConstraintConfig(
                    enabled=True, is_hard=True, parameters={"max_shifts_per_period": 2}
                ),
            },
        )
        result = checker.check()

        # 2 workers * 2 shifts/period capacity = 4 == demand (2 + 2)
        assert not any(i["type"] == "worker_shift_limit" for i in result.issues)

    def test_applicable_days_excludes_shift_with_no_days_in_period(self) -> None:
        """A shift type with zero applicable days in a period contributes no
        demand for that period, even though it would otherwise push total
        demand over capacity."""
        workers = [
            Worker(id="W1", name="Alice"),
            Worker(id="W2", name="Bob"),
        ]
        shift_types = [
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
                id="weekend_only",
                name="Weekend Only Shift",
                category="weekend",
                start_time=time(7, 0),
                end_time=time(15, 0),
                duration_hours=8.0,
                workers_required=2,
                # Saturday=5, Sunday=6 - only applies on weekends.
                applicable_days=frozenset({5, 6}),
            ),
        ]
        # A period covering only weekdays (Mon-Fri) has zero Sat/Sun days,
        # so "weekend_only" contributes no demand.
        weekday_period_dates = [(date(2026, 1, 5), date(2026, 1, 9))]

        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=weekday_period_dates,
        )
        result = checker.check()

        # Only "day" (req=2) applies; capacity is 2 workers * 1 = 2.
        assert not any(i["type"] == "worker_shift_limit" for i in result.issues)


class TestRestrictionAvailabilityGating:
    """
    Tests that restriction/availability-based checks only fire when the
    corresponding constraint is actually enabled and hard - mirroring
    ShiftSolver._apply_hard_constraints, which skips a hard-registered
    constraint entirely when it's disabled. Before this fix, a config with
    e.g. `restriction: {enabled: false}` (a documented, legitimate setup)
    produced a false INFEASIBLE_PRE_SOLVE even though the solver itself
    would happily generate a schedule.
    """

    def test_disabled_restriction_does_not_block_check_restrictions(
        self,
        period_dates: list[tuple[date, date]],
    ) -> None:
        """All workers restricted from a shift is fine if restriction is disabled."""
        workers = [
            Worker(id="W1", name="Alice", restricted_shifts=frozenset(["day"])),
            Worker(id="W2", name="Bob", restricted_shifts=frozenset(["day"])),
        ]
        shift_types = [
            ShiftType(
                id="day",
                name="Day Shift",
                category="day",
                start_time=time(7, 0),
                end_time=time(15, 0),
                duration_hours=8.0,
                workers_required=1,
            ),
        ]
        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            constraint_configs={
                "restriction": ConstraintConfig(enabled=False, is_hard=True),
            },
        )
        result = checker.check()

        assert not any(i["type"] == "restriction" for i in result.issues)
        assert result.is_feasible

    def test_restriction_enforced_regardless_of_is_hard_flag(
        self,
        period_dates: list[tuple[date, date]],
    ) -> None:
        """restriction is hard-registered: the solver enforces it whenever
        enabled, ignoring is_hard, so the checker must still flag the
        shortfall with is_hard=False (a shape the programmatic API can
        produce even though YAML loading rejects it)."""
        workers = [
            Worker(id="W1", name="Alice", restricted_shifts=frozenset(["day"])),
        ]
        shift_types = [
            ShiftType(
                id="day",
                name="Day Shift",
                category="day",
                start_time=time(7, 0),
                end_time=time(15, 0),
                duration_hours=8.0,
                workers_required=1,
            ),
        ]
        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            constraint_configs={
                "restriction": ConstraintConfig(enabled=True, is_hard=False),
            },
        )
        result = checker.check()

        assert any(i["type"] == "restriction" for i in result.issues)
        assert not result.is_feasible

    def test_disabled_availability_does_not_block_check_availability_conflicts(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """All workers unavailable for a period is fine if availability is disabled."""
        availabilities = [
            Availability(
                worker_id=w.id,
                start_date=period_dates[0][0],
                end_date=period_dates[0][1],
                availability_type="unavailable",
            )
            for w in workers
        ]
        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            availabilities=availabilities,
            constraint_configs={
                "availability": ConstraintConfig(enabled=False, is_hard=True),
            },
        )
        result = checker.check()

        assert not any(i["type"] == "availability" for i in result.issues)
        assert result.is_feasible

    def test_disabled_restriction_does_not_block_combined_check(self) -> None:
        """Restriction disabled: combined check should ignore restrictions
        entirely, so only genuine availability shortfalls are flagged."""
        workers = [
            Worker(id="W1", name="Alice", restricted_shifts=frozenset(["day"])),
            Worker(id="W2", name="Bob"),
            Worker(id="W3", name="Charlie"),
        ]
        shift_types = [
            ShiftType(
                id="day",
                name="Day Shift",
                category="day",
                start_time=time(7, 0),
                end_time=time(15, 0),
                duration_hours=8.0,
                workers_required=2,
            ),
        ]
        period_dates = [(date(2026, 1, 1), date(2026, 1, 7))]

        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            constraint_configs={
                "restriction": ConstraintConfig(enabled=False, is_hard=True),
            },
        )
        result = checker.check()

        # With restriction disabled, all 3 workers can work "day" - only the
        # 2 required, so nothing should be flagged.
        assert not any(i["type"] == "combined" for i in result.issues)
        assert result.is_feasible

    def test_disabled_availability_does_not_block_combined_check(self) -> None:
        """Availability disabled: combined check should ignore unavailability
        records entirely."""
        workers = [
            Worker(id="W1", name="Alice"),
            Worker(id="W2", name="Bob"),
        ]
        shift_types = [
            ShiftType(
                id="day",
                name="Day Shift",
                category="day",
                start_time=time(7, 0),
                end_time=time(15, 0),
                duration_hours=8.0,
                workers_required=2,
            ),
        ]
        period_dates = [(date(2026, 1, 1), date(2026, 1, 7))]
        availabilities = [
            Availability(
                worker_id="W1",
                start_date=date(2026, 1, 1),
                end_date=date(2026, 1, 7),
                availability_type="unavailable",
            ),
            Availability(
                worker_id="W2",
                start_date=date(2026, 1, 1),
                end_date=date(2026, 1, 7),
                availability_type="unavailable",
            ),
        ]

        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            availabilities=availabilities,
            constraint_configs={
                "availability": ConstraintConfig(enabled=False, is_hard=True),
            },
        )
        result = checker.check()

        # With availability disabled, both workers still count as available.
        assert not any(i["type"] == "combined" for i in result.issues)
        assert result.is_feasible

    def test_disabled_restriction_does_not_block_hard_request_check(
        self,
        period_dates: list[tuple[date, date]],
    ) -> None:
        """A hard positive request for a restricted shift is fine once
        restriction is disabled - the solver won't enforce the restriction."""
        workers = [
            Worker(id="W1", name="Alice", restricted_shifts=frozenset(["night"])),
            Worker(id="W2", name="Bob"),
        ]
        shift_types = [
            ShiftType(
                id="night",
                name="Night Shift",
                category="night",
                start_time=time(23, 0),
                end_time=time(7, 0),
                duration_hours=8.0,
                workers_required=1,
            ),
        ]
        requests = [
            SchedulingRequest(
                worker_id="W1",
                start_date=period_dates[0][0],
                end_date=period_dates[0][1],
                request_type="positive",
                shift_type_id="night",
                priority=1,
                is_hard=True,
            )
        ]
        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            requests=requests,
            constraint_configs={
                "restriction": ConstraintConfig(enabled=False, is_hard=True),
            },
        )
        result = checker.check()

        assert not any(i["type"] == "request" for i in result.issues)

    def test_disabled_availability_does_not_block_hard_request_check(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """A hard positive request during full unavailability is fine once
        availability is disabled - the solver won't enforce unavailability."""
        availabilities = [
            Availability(
                worker_id="W1",
                start_date=period_dates[0][0],
                end_date=period_dates[0][1],
                availability_type="unavailable",
                shift_type_id="day",
            ),
        ]
        requests = [
            SchedulingRequest(
                worker_id="W1",
                start_date=period_dates[0][0],
                end_date=period_dates[0][1],
                request_type="positive",
                shift_type_id="day",
                priority=1,
                is_hard=True,
            )
        ]
        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            availabilities=availabilities,
            requests=requests,
            constraint_configs={
                "availability": ConstraintConfig(enabled=False, is_hard=True),
            },
        )
        result = checker.check()

        assert not any(i["type"] == "request" for i in result.issues)


class TestSkillsFeasibility:
    """
    Tests for the skills feasibility check: a shift type with
    required_attributes that no (or too few) workers satisfy should be
    diagnosed with actionable text, mirroring SkillsConstraint._worker_qualifies
    exactly (a worker qualifies only if every required key/value pair
    matches worker.attributes).
    """

    def test_no_worker_qualifies_is_infeasible_with_actionable_message(
        self,
        period_dates: list[tuple[date, date]],
    ) -> None:
        """No worker has the required attribute -> hard issue naming the
        shift type, the required attributes, and the qualifying count."""
        workers = [
            Worker(id="W1", name="Alice", attributes={"certification": "basic"}),
            Worker(id="W2", name="Bob", attributes={"certification": "basic"}),
        ]
        shift_types = [
            ShiftType(
                id="icu",
                name="ICU Shift",
                category="day",
                start_time=time(7, 0),
                end_time=time(15, 0),
                duration_hours=8.0,
                workers_required=1,
                required_attributes={"certification": "icu"},
            ),
        ]
        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
        )
        result = checker.check()

        assert not result.is_feasible
        assert any(i["type"] == "skills" for i in result.issues)
        issue = next(i for i in result.issues if i["type"] == "skills")
        assert "ICU Shift" in issue["message"]
        assert "certification" in issue["message"]
        assert "icu" in issue["message"]
        assert "0" in issue["message"]
        assert "1" in issue["message"]
        assert issue["workers_qualified"] == 0
        assert issue["workers_required"] == 1
        assert issue["required_attributes"] == {"certification": "icu"}

    def test_too_few_qualifying_workers_is_infeasible(
        self,
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Only 1 worker qualifies but 2 are required."""
        workers = [
            Worker(id="W1", name="Alice", attributes={"certification": "icu"}),
            Worker(id="W2", name="Bob", attributes={"certification": "basic"}),
            Worker(id="W3", name="Charlie", attributes={"certification": "basic"}),
        ]
        shift_types = [
            ShiftType(
                id="icu",
                name="ICU Shift",
                category="day",
                start_time=time(7, 0),
                end_time=time(15, 0),
                duration_hours=8.0,
                workers_required=2,
                required_attributes={"certification": "icu"},
            ),
        ]
        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
        )
        result = checker.check()

        assert not result.is_feasible
        issue = next(i for i in result.issues if i["type"] == "skills")
        assert issue["workers_qualified"] == 1
        assert issue["workers_required"] == 2

    def test_multi_attribute_requirement_requires_all_pairs(
        self,
        period_dates: list[tuple[date, date]],
    ) -> None:
        """A worker must satisfy EVERY required key/value pair to qualify."""
        workers = [
            # Has the right certification but wrong site - doesn't qualify.
            Worker(
                id="W1",
                name="Alice",
                attributes={"certification": "icu", "site": "east"},
            ),
            Worker(
                id="W2",
                name="Bob",
                attributes={"certification": "icu", "site": "west"},
            ),
        ]
        shift_types = [
            ShiftType(
                id="icu_west",
                name="ICU West Shift",
                category="day",
                start_time=time(7, 0),
                end_time=time(15, 0),
                duration_hours=8.0,
                workers_required=1,
                required_attributes={"certification": "icu", "site": "west"},
            ),
        ]
        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
        )
        result = checker.check()

        # W2 satisfies both pairs, so this is feasible.
        assert not any(i["type"] == "skills" for i in result.issues)

    def test_enough_qualifying_workers_is_feasible(
        self,
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Enough workers qualify -> no skills issue."""
        workers = [
            Worker(id="W1", name="Alice", attributes={"certification": "icu"}),
        ]
        shift_types = [
            ShiftType(
                id="icu",
                name="ICU Shift",
                category="day",
                start_time=time(7, 0),
                end_time=time(15, 0),
                duration_hours=8.0,
                workers_required=1,
                required_attributes={"certification": "icu"},
            ),
        ]
        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
        )
        result = checker.check()

        assert result.is_feasible
        assert not any(i["type"] == "skills" for i in result.issues)

    def test_empty_required_attributes_is_unconstrained(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Shift types with no required_attributes are never flagged."""
        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
        )
        result = checker.check()

        assert not any(i["type"] == "skills" for i in result.issues)

    def test_disabled_skills_constraint_does_not_bound_feasibility(
        self,
        period_dates: list[tuple[date, date]],
    ) -> None:
        """No qualifying worker is fine if the skills constraint is disabled -
        the solver never enforces required_attributes in that case."""
        workers = [
            Worker(id="W1", name="Alice", attributes={"certification": "basic"}),
        ]
        shift_types = [
            ShiftType(
                id="icu",
                name="ICU Shift",
                category="day",
                start_time=time(7, 0),
                end_time=time(15, 0),
                duration_hours=8.0,
                workers_required=1,
                required_attributes={"certification": "icu"},
            ),
        ]
        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            constraint_configs={
                "skills": ConstraintConfig(enabled=False, is_hard=True),
            },
        )
        result = checker.check()

        assert not any(i["type"] == "skills" for i in result.issues)
        assert result.is_feasible

    def test_skills_enforced_regardless_of_is_hard_flag(
        self,
        period_dates: list[tuple[date, date]],
    ) -> None:
        """skills is hard-registered: the solver enforces it whenever
        enabled, ignoring is_hard, so the checker must still flag the
        qualification shortfall with is_hard=False (a shape the programmatic
        API can produce even though YAML loading rejects it)."""
        workers = [
            Worker(id="W1", name="Alice", attributes={"certification": "basic"}),
        ]
        shift_types = [
            ShiftType(
                id="icu",
                name="ICU Shift",
                category="day",
                start_time=time(7, 0),
                end_time=time(15, 0),
                duration_hours=8.0,
                workers_required=1,
                required_attributes={"certification": "icu"},
            ),
        ]
        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            constraint_configs={
                "skills": ConstraintConfig(enabled=True, is_hard=False),
            },
        )
        result = checker.check()

        assert any(i["type"] == "skills" for i in result.issues)
        assert not result.is_feasible


class TestRequestContradictionUnionOfNegatives:
    """
    Tests for the union-of-negatives fix (contradictory hard-request
    detection): two hard negatives that individually cover only PART of a
    hard positive's applicable periods, but jointly cover all of them,
    must still be flagged as contradictory.
    """

    def test_two_negatives_jointly_covering_positive_are_contradictory(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Positive spans both periods; negative #1 covers only period 0,
        negative #2 covers only period 1 - neither alone covers the
        positive's periods, but together they do."""
        requests = [
            SchedulingRequest(
                worker_id="W1",
                start_date=period_dates[0][0],
                end_date=period_dates[1][1],
                request_type="positive",
                shift_type_id="day",
                priority=1,
                is_hard=True,
            ),
            SchedulingRequest(
                worker_id="W1",
                start_date=period_dates[0][0],
                end_date=period_dates[0][1],
                request_type="negative",
                shift_type_id="day",
                priority=1,
                is_hard=True,
            ),
            SchedulingRequest(
                worker_id="W1",
                start_date=period_dates[1][0],
                end_date=period_dates[1][1],
                request_type="negative",
                shift_type_id="day",
                priority=1,
                is_hard=True,
            ),
        ]
        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            requests=requests,
        )
        result = checker.check()

        assert not result.is_feasible
        assert any(i["type"] == "request" for i in result.issues)
        issue = next(i for i in result.issues if i["type"] == "request")
        assert "W1" in issue["message"]

    def test_negatives_not_jointly_covering_positive_are_feasible(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """A single negative covering only ONE of the two periods the
        positive spans is not contradictory - the request is still
        satisfiable in the other period."""
        requests = [
            SchedulingRequest(
                worker_id="W1",
                start_date=period_dates[0][0],
                end_date=period_dates[1][1],
                request_type="positive",
                shift_type_id="day",
                priority=1,
                is_hard=True,
            ),
            SchedulingRequest(
                worker_id="W1",
                start_date=period_dates[0][0],
                end_date=period_dates[0][1],
                request_type="negative",
                shift_type_id="day",
                priority=1,
                is_hard=True,
            ),
        ]
        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            requests=requests,
        )
        result = checker.check()

        assert not any(i["type"] == "request" for i in result.issues)


class TestRequestCheckGating:
    """
    The request checks must mirror what the solver actually enforces:
    a disabled request constraint is never built, and per-record hardness
    falls back to the request constraint's configured is_hard.
    """

    def _contradictory_requests(
        self, period_dates: list[tuple[date, date]], is_hard: bool | None
    ) -> list[SchedulingRequest]:
        """A positive spanning both periods plus negatives covering each."""
        return [
            SchedulingRequest(
                worker_id="W1",
                start_date=period_dates[0][0],
                end_date=period_dates[1][1],
                request_type="positive",
                shift_type_id="day",
                priority=1,
                is_hard=is_hard,
            ),
            SchedulingRequest(
                worker_id="W1",
                start_date=period_dates[0][0],
                end_date=period_dates[0][1],
                request_type="negative",
                shift_type_id="day",
                priority=1,
                is_hard=is_hard,
            ),
            SchedulingRequest(
                worker_id="W1",
                start_date=period_dates[1][0],
                end_date=period_dates[1][1],
                request_type="negative",
                shift_type_id="day",
                priority=1,
                is_hard=is_hard,
            ),
        ]

    def test_disabled_request_constraint_skips_contradiction_checks(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """With request: {enabled: false} the RequestConstraint is never
        built, so contradictory hard requests cannot make the model
        infeasible and must not be flagged."""
        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            requests=self._contradictory_requests(period_dates, is_hard=True),
            constraint_configs={
                "request": ConstraintConfig(enabled=False, is_hard=False),
            },
        )
        result = checker.check()

        assert not any(i["type"] == "request" for i in result.issues)
        assert result.is_feasible

    def test_config_level_is_hard_makes_blank_requests_hard(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
    ) -> None:
        """Requests with is_hard=None inherit the request constraint's
        configured is_hard (mirroring RequestConstraint), so a contradiction
        among such requests is caught when the config says is_hard=True."""
        checker = FeasibilityChecker(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            requests=self._contradictory_requests(period_dates, is_hard=None),
            constraint_configs={
                "request": ConstraintConfig(enabled=True, is_hard=True),
            },
        )
        result = checker.check()

        assert not result.is_feasible
        assert any(i["type"] == "request" for i in result.issues)
