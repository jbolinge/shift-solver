"""Test data factories for shift_solver tests.

Provides builder patterns for creating test data without repetition.
"""

from datetime import date, time, timedelta
from typing import Any

from shift_solver.constraints.base import ConstraintConfig
from shift_solver.models import (
    Availability,
    SchedulingRequest,
    ShiftType,
    Worker,
)


class WorkerFactory:
    """Factory for creating test Worker instances."""

    _counter = 0

    def __init__(self) -> None:
        self._counter = 0

    def create(
        self,
        id: str | None = None,
        name: str | None = None,
        worker_type: str | None = None,
        restricted_shifts: frozenset[str] | None = None,
        preferred_shifts: frozenset[str] | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> Worker:
        """Create a single worker with auto-incrementing ID if not provided."""
        self._counter += 1
        return Worker(
            id=id or f"W{self._counter:03d}",
            name=name or f"Worker {self._counter}",
            worker_type=worker_type,
            restricted_shifts=restricted_shifts or frozenset(),
            preferred_shifts=preferred_shifts or frozenset(),
            attributes=attributes or {},
        )

    def create_batch(
        self,
        count: int,
        worker_type: str | None = None,
        restricted_shifts: frozenset[str] | None = None,
    ) -> list[Worker]:
        """Create multiple workers with the same configuration."""
        return [
            self.create(worker_type=worker_type, restricted_shifts=restricted_shifts)
            for _ in range(count)
        ]

    def reset(self) -> None:
        """Reset the counter for fresh ID generation."""
        self._counter = 0


class ShiftTypeFactory:
    """Factory for creating test ShiftType instances."""

    _counter = 0

    # Common presets
    PRESETS = {
        "day_8": {
            "name": "Day Shift",
            "category": "day",
            "start_time": time(7, 0),
            "end_time": time(15, 0),
            "duration_hours": 8.0,
        },
        "night_8": {
            "name": "Night Shift",
            "category": "night",
            "start_time": time(23, 0),
            "end_time": time(7, 0),
            "duration_hours": 8.0,
            "is_undesirable": True,
        },
        "day_12": {
            "name": "Day Shift (12h)",
            "category": "day",
            "start_time": time(7, 0),
            "end_time": time(19, 0),
            "duration_hours": 12.0,
        },
        "night_12": {
            "name": "Night Shift (12h)",
            "category": "night",
            "start_time": time(19, 0),
            "end_time": time(7, 0),
            "duration_hours": 12.0,
            "is_undesirable": True,
        },
        "weekend": {
            "name": "Weekend Shift",
            "category": "weekend",
            "start_time": time(8, 0),
            "end_time": time(16, 0),
            "duration_hours": 8.0,
            "is_undesirable": True,
        },
    }

    def __init__(self) -> None:
        self._counter = 0

    def create(
        self,
        id: str | None = None,
        name: str | None = None,
        category: str = "day",
        start_time: time = time(9, 0),
        end_time: time = time(17, 0),
        duration_hours: float = 8.0,
        is_undesirable: bool = False,
        workers_required: int = 1,
        required_attributes: dict[str, Any] | None = None,
    ) -> ShiftType:
        """Create a single shift type."""
        self._counter += 1
        return ShiftType(
            id=id or f"shift_{self._counter}",
            name=name or f"Shift {self._counter}",
            category=category,
            start_time=start_time,
            end_time=end_time,
            duration_hours=duration_hours,
            is_undesirable=is_undesirable,
            workers_required=workers_required,
            required_attributes=required_attributes or {},
        )

    def create_from_preset(
        self,
        preset: str,
        id: str | None = None,
        workers_required: int = 1,
    ) -> ShiftType:
        """Create a shift type from a named preset."""
        if preset not in self.PRESETS:
            raise ValueError(f"Unknown preset: {preset}. Available: {list(self.PRESETS)}")

        config = self.PRESETS[preset].copy()
        self._counter += 1
        return ShiftType(
            id=id or preset,
            workers_required=workers_required,
            **config,
        )

    def create_standard_set(self, workers_per_shift: int = 1) -> list[ShiftType]:
        """Create a standard set of day, night, and weekend shifts."""
        return [
            self.create_from_preset("day_8", id="day", workers_required=workers_per_shift),
            self.create_from_preset("night_8", id="night", workers_required=workers_per_shift),
            self.create_from_preset("weekend", id="weekend", workers_required=workers_per_shift),
        ]

    def create_healthcare_set(self, workers_per_shift: int = 2) -> list[ShiftType]:
        """Create healthcare-style 12-hour shifts."""
        return [
            self.create_from_preset("day_12", id="day", workers_required=workers_per_shift),
            self.create_from_preset("night_12", id="night", workers_required=workers_per_shift),
        ]

    def create_warehouse_set(self) -> list[ShiftType]:
        """Create warehouse 3-shift rotation."""
        return [
            ShiftType(
                id="first",
                name="First Shift",
                category="day",
                start_time=time(6, 0),
                end_time=time(14, 0),
                duration_hours=8.0,
                workers_required=3,
            ),
            ShiftType(
                id="second",
                name="Second Shift",
                category="evening",
                start_time=time(14, 0),
                end_time=time(22, 0),
                duration_hours=8.0,
                workers_required=3,
            ),
            ShiftType(
                id="third",
                name="Third Shift",
                category="night",
                start_time=time(22, 0),
                end_time=time(6, 0),
                duration_hours=8.0,
                workers_required=2,
                is_undesirable=True,
            ),
        ]

    def reset(self) -> None:
        """Reset the counter."""
        self._counter = 0


def create_period_dates(
    start_date: date = date(2026, 2, 2),
    num_periods: int = 4,
    period_length_days: int = 7,
) -> list[tuple[date, date]]:
    """Create a list of period date ranges.

    Args:
        start_date: Start date for the first period
        num_periods: Number of periods to create
        period_length_days: Length of each period in days

    Returns:
        List of (start, end) date tuples
    """
    periods = []
    current = start_date
    for _ in range(num_periods):
        period_end = current + timedelta(days=period_length_days - 1)
        periods.append((current, period_end))
        current = period_end + timedelta(days=1)
    return periods


class ScenarioBuilder:
    """Fluent builder for creating complete test scenarios.

    Usage:
        scenario = (
            ScenarioBuilder()
            .with_workers(10)
            .with_shift_types("standard")
            .with_periods(4)
            .with_unavailability("W001", period=0)
            .build()
        )

        solver = ShiftSolver(
            workers=scenario["workers"],
            shift_types=scenario["shift_types"],
            period_dates=scenario["period_dates"],
            ...
        )
    """

    def __init__(self) -> None:
        self._worker_factory = WorkerFactory()
        self._shift_factory = ShiftTypeFactory()
        self._workers: list[Worker] = []
        self._shift_types: list[ShiftType] = []
        self._period_dates: list[tuple[date, date]] = []
        self._availabilities: list[Availability] = []
        self._requests: list[SchedulingRequest] = []
        self._constraints: dict[str, ConstraintConfig] = {}
        self._schedule_id: str = "TEST-001"
        self._start_date: date = date(2026, 2, 2)

    def with_workers(
        self,
        count: int | list[Worker],
        worker_type: str | None = None,
    ) -> "ScenarioBuilder":
        """Add workers to the scenario."""
        if isinstance(count, list):
            self._workers = count
        else:
            self._workers = self._worker_factory.create_batch(count, worker_type=worker_type)
        return self

    def with_worker(
        self,
        id: str,
        name: str,
        worker_type: str | None = None,
        restricted_shifts: frozenset[str] | None = None,
    ) -> "ScenarioBuilder":
        """Add a single custom worker."""
        self._workers.append(
            Worker(
                id=id,
                name=name,
                worker_type=worker_type,
                restricted_shifts=restricted_shifts or frozenset(),
            )
        )
        return self

    def with_shift_types(
        self,
        shift_types: str | list[ShiftType],
        workers_per_shift: int = 1,
    ) -> "ScenarioBuilder":
        """Add shift types to the scenario.

        Args:
            shift_types: Either a preset name ("standard", "healthcare", "warehouse")
                        or a list of ShiftType objects
            workers_per_shift: Number of workers required per shift (for presets)
        """
        if isinstance(shift_types, list):
            self._shift_types = shift_types
        elif shift_types == "standard":
            self._shift_types = self._shift_factory.create_standard_set(workers_per_shift)
        elif shift_types == "healthcare":
            self._shift_types = self._shift_factory.create_healthcare_set(workers_per_shift)
        elif shift_types == "warehouse":
            self._shift_types = self._shift_factory.create_warehouse_set()
        else:
            raise ValueError(f"Unknown shift type preset: {shift_types}")
        return self

    def with_periods(
        self,
        num_periods: int,
        period_length_days: int = 7,
        start_date: date | None = None,
    ) -> "ScenarioBuilder":
        """Add scheduling periods."""
        if start_date:
            self._start_date = start_date
        self._period_dates = create_period_dates(
            start_date=self._start_date,
            num_periods=num_periods,
            period_length_days=period_length_days,
        )
        return self

    def with_unavailability(
        self,
        worker_id: str,
        period: int | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        shift_type_id: str | None = None,
    ) -> "ScenarioBuilder":
        """Add unavailability for a worker.

        Can specify either a period index or explicit date range.
        """
        if period is not None:
            if not self._period_dates:
                raise ValueError("Call with_periods() before with_unavailability(period=...)")
            start = self._period_dates[period][0]
            end = self._period_dates[period][1]
        elif start_date and end_date:
            start = start_date
            end = end_date
        else:
            raise ValueError("Must specify either period or (start_date, end_date)")

        self._availabilities.append(
            Availability(
                worker_id=worker_id,
                start_date=start,
                end_date=end,
                availability_type="unavailable",
                shift_type_id=shift_type_id,
            )
        )
        return self

    def with_request(
        self,
        worker_id: str,
        shift_type_id: str,
        request_type: str = "positive",
        period: int | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        priority: int = 1,
    ) -> "ScenarioBuilder":
        """Add a scheduling request."""
        if period is not None:
            if not self._period_dates:
                raise ValueError("Call with_periods() before with_request(period=...)")
            start = self._period_dates[period][0]
            end = self._period_dates[period][1]
        elif start_date and end_date:
            start = start_date
            end = end_date
        else:
            raise ValueError("Must specify either period or (start_date, end_date)")

        self._requests.append(
            SchedulingRequest(
                worker_id=worker_id,
                start_date=start,
                end_date=end,
                request_type=request_type,  # type: ignore
                shift_type_id=shift_type_id,
                priority=priority,
            )
        )
        return self

    def with_constraints(
        self,
        preset: str = "all",
        **overrides: ConstraintConfig,
    ) -> "ScenarioBuilder":
        """Configure constraints.

        Args:
            preset: "all", "hard_only", or "minimal"
            **overrides: Individual constraint overrides
        """
        if preset == "all":
            self._constraints = {
                "coverage": ConstraintConfig(enabled=True, is_hard=True),
                "restriction": ConstraintConfig(enabled=True, is_hard=True),
                "availability": ConstraintConfig(enabled=True, is_hard=True),
                "fairness": ConstraintConfig(enabled=True, is_hard=False, weight=100),
                "frequency": ConstraintConfig(enabled=True, is_hard=False, weight=50),
                "request": ConstraintConfig(enabled=True, is_hard=False, weight=75),
            }
        elif preset == "hard_only":
            self._constraints = {
                "coverage": ConstraintConfig(enabled=True, is_hard=True),
                "restriction": ConstraintConfig(enabled=True, is_hard=True),
                "availability": ConstraintConfig(enabled=True, is_hard=True),
            }
        elif preset == "minimal":
            self._constraints = {
                "coverage": ConstraintConfig(enabled=True, is_hard=True),
            }
        else:
            raise ValueError(f"Unknown constraint preset: {preset}")

        self._constraints.update(overrides)
        return self

    def with_schedule_id(self, schedule_id: str) -> "ScenarioBuilder":
        """Set the schedule ID."""
        self._schedule_id = schedule_id
        return self

    def build(self) -> dict[str, Any]:
        """Build and return the complete scenario."""
        return {
            "workers": self._workers,
            "shift_types": self._shift_types,
            "period_dates": self._period_dates,
            "availabilities": self._availabilities,
            "requests": self._requests,
            "constraint_configs": self._constraints or None,
            "schedule_id": self._schedule_id,
        }


# Convenience factory instances for quick access
worker_factory = WorkerFactory()
shift_factory = ShiftTypeFactory()
