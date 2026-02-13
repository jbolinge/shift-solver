"""Tests for FeasibilityChecker pre-solve validation."""

from datetime import date, time

import pytest

from shift_solver.models import Availability, ShiftType, Worker
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
