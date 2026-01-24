"""ScheduleValidator for post-solve validation."""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from shift_solver.models import Availability, Schedule, SchedulingRequest
from shift_solver.utils import get_logger

logger = get_logger("validation.schedule")


@dataclass
class ValidationResult:
    """Result of schedule validation."""

    is_valid: bool
    violations: list[dict[str, Any]]
    warnings: list[dict[str, Any]] = field(default_factory=list)
    statistics: dict[str, Any] = field(default_factory=dict)

    def add_violation(
        self, violation_type: str, message: str, severity: str = "error", **details: Any
    ) -> None:
        """Add a violation to the result."""
        self.violations.append(
            {"type": violation_type, "message": message, "severity": severity, **details}
        )
        if severity == "error":
            self.is_valid = False

    def add_warning(self, violation_type: str, message: str, **details: Any) -> None:
        """Add a warning to the result."""
        self.warnings.append(
            {"type": violation_type, "message": message, "severity": "warning", **details}
        )


class ScheduleValidator:
    """
    Validates generated schedules against all constraints.

    Performs post-solve validation to verify:
    - All hard constraints are satisfied
    - Coverage requirements are met
    - No restricted assignments
    - Availability is honored
    - Computes statistics on soft constraint fulfillment
    """

    def __init__(
        self,
        schedule: Schedule,
        availabilities: list[Availability] | None = None,
        requests: list[SchedulingRequest] | None = None,
    ) -> None:
        """
        Initialize the schedule validator.

        Args:
            schedule: The schedule to validate
            availabilities: Optional list of availability records
            requests: Optional list of scheduling requests
        """
        self.schedule = schedule
        self.availabilities = availabilities or []
        self.requests = requests or []

        # Build lookup maps
        self._worker_map = {w.id: w for w in schedule.workers}
        self._shift_type_map = {st.id: st for st in schedule.shift_types}

    def validate(self) -> ValidationResult:
        """
        Run all validation checks.

        Returns:
            ValidationResult with is_valid flag, violations, and statistics
        """
        result = ValidationResult(is_valid=True, violations=[])

        # Run all validation checks
        self._validate_coverage(result)
        self._validate_restrictions(result)
        self._validate_availability(result)

        # Compute statistics
        self._compute_statistics(result)
        self._compute_request_fulfillment(result)

        if result.is_valid:
            logger.info("Schedule validation passed")
        else:
            logger.warning(
                f"Schedule validation failed with {len(result.violations)} violations"
            )
            for violation in result.violations:
                logger.warning(f"  - {violation['type']}: {violation['message']}")

        return result

    def _validate_coverage(self, result: ValidationResult) -> None:
        """Validate that coverage requirements are met."""
        for period in self.schedule.periods:
            # Count assignments per shift type for this period
            shift_type_counts: dict[str, int] = defaultdict(int)

            for worker_id, shifts in period.assignments.items():
                for shift in shifts:
                    shift_type_counts[shift.shift_type_id] += 1

            # Check each shift type has required coverage
            for shift_type in self.schedule.shift_types:
                count = shift_type_counts.get(shift_type.id, 0)
                if count < shift_type.workers_required:
                    result.add_violation(
                        "coverage",
                        f"Period {period.period_index}: Shift '{shift_type.name}' "
                        f"has {count} workers, requires {shift_type.workers_required}",
                        period_index=period.period_index,
                        shift_type_id=shift_type.id,
                        assigned=count,
                        required=shift_type.workers_required,
                    )

    def _validate_restrictions(self, result: ValidationResult) -> None:
        """Validate that no worker is assigned to a restricted shift."""
        for period in self.schedule.periods:
            for worker_id, shifts in period.assignments.items():
                worker = self._worker_map.get(worker_id)
                if not worker:
                    result.add_violation(
                        "data",
                        f"Unknown worker '{worker_id}' in assignments",
                        worker_id=worker_id,
                    )
                    continue

                for shift in shifts:
                    if not worker.can_work_shift(shift.shift_type_id):
                        shift_type = self._shift_type_map.get(shift.shift_type_id)
                        shift_name = shift_type.name if shift_type else shift.shift_type_id
                        result.add_violation(
                            "restriction",
                            f"Worker '{worker.name}' assigned to restricted "
                            f"shift '{shift_name}' on {shift.date}",
                            worker_id=worker_id,
                            shift_type_id=shift.shift_type_id,
                            date=str(shift.date),
                        )

    def _validate_availability(self, result: ValidationResult) -> None:
        """Validate that no worker is assigned when unavailable."""
        if not self.availabilities:
            return

        # Build lookup: (worker_id, date) -> is_unavailable
        unavailable_dates: dict[tuple[str, date], bool] = {}
        for avail in self.availabilities:
            if avail.availability_type != "unavailable":
                continue
            # Mark all dates in range as unavailable
            current = avail.start_date
            while current <= avail.end_date:
                key = (avail.worker_id, current)
                # If shift_type_id is specified, only that shift is unavailable
                # For simplicity, we treat general unavailability as blocking all shifts
                if avail.shift_type_id is None:
                    unavailable_dates[key] = True
                current = date.fromordinal(current.toordinal() + 1)

        # Check assignments
        for period in self.schedule.periods:
            for worker_id, shifts in period.assignments.items():
                for shift in shifts:
                    if (worker_id, shift.date) in unavailable_dates:
                        worker = self._worker_map.get(worker_id)
                        worker_name = worker.name if worker else worker_id
                        result.add_violation(
                            "availability",
                            f"Worker '{worker_name}' assigned on {shift.date} "
                            f"but marked unavailable",
                            worker_id=worker_id,
                            date=str(shift.date),
                            shift_type_id=shift.shift_type_id,
                        )

    def _compute_statistics(self, result: ValidationResult) -> None:
        """Compute schedule statistics."""
        total_assignments = 0
        assignments_per_worker: dict[str, int] = defaultdict(int)
        undesirable_per_worker: dict[str, int] = defaultdict(int)

        for period in self.schedule.periods:
            for worker_id, shifts in period.assignments.items():
                for shift in shifts:
                    total_assignments += 1
                    assignments_per_worker[worker_id] += 1

                    # Track undesirable shifts
                    shift_type = self._shift_type_map.get(shift.shift_type_id)
                    if shift_type and shift_type.is_undesirable:
                        undesirable_per_worker[worker_id] += 1

        result.statistics["total_assignments"] = total_assignments
        result.statistics["assignments_per_worker"] = dict(assignments_per_worker)

        # Compute fairness metrics
        if assignments_per_worker:
            counts = list(assignments_per_worker.values())
            avg = sum(counts) / len(counts)
            variance = sum((c - avg) ** 2 for c in counts) / len(counts)
            std_dev = variance ** 0.5

            undesirable_counts = list(undesirable_per_worker.values())
            undesirable_avg = (
                sum(undesirable_counts) / len(undesirable_counts)
                if undesirable_counts
                else 0
            )

            result.statistics["fairness"] = {
                "average_assignments": avg,
                "std_deviation": std_dev,
                "min_assignments": min(counts),
                "max_assignments": max(counts),
                "average_undesirable": undesirable_avg,
            }
        else:
            result.statistics["fairness"] = {
                "average_assignments": 0,
                "std_deviation": 0,
                "min_assignments": 0,
                "max_assignments": 0,
                "average_undesirable": 0,
            }

    def _compute_request_fulfillment(self, result: ValidationResult) -> None:
        """Compute request fulfillment statistics."""
        if not self.requests:
            result.statistics["request_fulfillment"] = {
                "total_requests": 0,
                "fulfilled": 0,
                "violated": 0,
                "rate": 1.0,  # No requests means 100% fulfilled
            }
            return

        # Build assignment lookup: (worker_id, date, shift_type_id) -> assigned
        assignments: set[tuple[str, date, str]] = set()
        for period in self.schedule.periods:
            for worker_id, shifts in period.assignments.items():
                for shift in shifts:
                    assignments.add((worker_id, shift.date, shift.shift_type_id))

        fulfilled = 0
        violated = 0

        for request in self.requests:
            # Check all dates in request range
            current = request.start_date
            while current <= request.end_date:
                key = (request.worker_id, current, request.shift_type_id)
                is_assigned = key in assignments

                if request.is_positive:
                    # Positive request: fulfilled if assigned
                    if is_assigned:
                        fulfilled += 1
                    else:
                        violated += 1
                else:
                    # Negative request: fulfilled if NOT assigned
                    if not is_assigned:
                        fulfilled += 1
                    else:
                        violated += 1

                current = date.fromordinal(current.toordinal() + 1)

        total = fulfilled + violated
        rate = fulfilled / total if total > 0 else 1.0

        result.statistics["request_fulfillment"] = {
            "total_requests": total,
            "fulfilled": fulfilled,
            "violated": violated,
            "rate": rate,
        }
