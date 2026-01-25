"""ScheduleValidator - orchestrator for post-solve validation."""

from collections import defaultdict
from datetime import date

from shift_solver.models import Availability, Schedule, SchedulingRequest
from shift_solver.utils import get_logger
from shift_solver.validation.schedule_validator.result import ValidationResult
from shift_solver.validation.schedule_validator.strategies import (
    AvailabilityValidationStrategy,
    CoverageValidationStrategy,
    RestrictionValidationStrategy,
)

logger = get_logger("validation.schedule")


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

        # Initialize validation strategies
        self._strategies = [
            CoverageValidationStrategy(),
            RestrictionValidationStrategy(),
            AvailabilityValidationStrategy(),
        ]

    def validate(self) -> ValidationResult:
        """
        Run all validation checks.

        Returns:
            ValidationResult with is_valid flag, violations, and statistics
        """
        result = ValidationResult(is_valid=True, violations=[])

        # Run all validation strategies
        for strategy in self._strategies:
            strategy.validate(
                schedule=self.schedule,
                result=result,
                worker_map=self._worker_map,
                shift_type_map=self._shift_type_map,
                availabilities=self.availabilities,
                requests=self.requests,
            )

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
            std_dev = variance**0.5

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
