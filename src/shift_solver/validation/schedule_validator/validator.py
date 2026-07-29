"""ScheduleValidator - orchestrator for post-solve validation."""

from collections import defaultdict

from shift_solver.models import (
    Availability,
    Schedule,
    SchedulingRequest,
    ShiftType,
    Worker,
)
from shift_solver.utils import get_logger
from shift_solver.validation.schedule_validator.result import ValidationResult
from shift_solver.validation.schedule_validator.strategies import (
    AvailabilityValidationStrategy,
    BaseValidationStrategy,
    CoverageValidationStrategy,
    RestrictionValidationStrategy,
    SkillsValidationStrategy,
    WorkerShiftLimitValidationStrategy,
)

logger = get_logger("validation.schedule")

DEFAULT_MAX_SHIFTS_PER_PERIOD = 1


class ScheduleValidator:
    """
    Validates generated schedules against all constraints.

    Performs post-solve validation to verify:
    - All hard constraints are satisfied
    - Coverage requirements are met exactly (honoring applicable_days)
    - No restricted assignments, and no unknown workers/shift types
    - Availability is honored (period-granular, including scoped records)
    - No worker exceeds the per-period shift limit
    - Assigned workers satisfy each shift type's required attributes
    - Computes statistics on soft constraint fulfillment
    """

    def __init__(
        self,
        schedule: Schedule,
        availabilities: list[Availability] | None = None,
        requests: list[SchedulingRequest] | None = None,
        shift_types: list[ShiftType] | None = None,
        workers: list[Worker] | None = None,
        max_shifts_per_period: int = DEFAULT_MAX_SHIFTS_PER_PERIOD,
    ) -> None:
        """
        Initialize the schedule validator.

        Args:
            schedule: The schedule to validate
            availabilities: Optional list of availability records
            requests: Optional list of scheduling requests
            shift_types: Optional shift type metadata (e.g. required_attributes,
                applicable_days) to use in addition to schedule.shift_types.
                Entries here take precedence over same-id entries embedded in
                the schedule. Callers that don't have this richer metadata can
                omit it; checks that need it simply find nothing to flag.
            workers: Optional worker metadata (e.g. attributes) used the same
                way as shift_types, in addition to schedule.workers.
            max_shifts_per_period: Maximum shift assignments allowed for a
                single worker within a single period (default 1), matching
                the "worker_shift_limit" constraint.
        """
        self.schedule = schedule
        self.availabilities = availabilities or []
        self.requests = requests or []
        self.max_shifts_per_period = max_shifts_per_period

        # Build lookup maps. Explicitly supplied metadata overrides/extends
        # what is embedded in the schedule, so callers that only have a bare
        # schedule (e.g. reconstructed from JSON) keep working unchanged.
        self._worker_map = {w.id: w for w in schedule.workers}
        if workers:
            self._worker_map.update({w.id: w for w in workers})

        self._shift_type_map = {st.id: st for st in schedule.shift_types}
        if shift_types:
            self._shift_type_map.update({st.id: st for st in shift_types})

        # Initialize validation strategies
        self._strategies: list[BaseValidationStrategy] = [
            CoverageValidationStrategy(),
            RestrictionValidationStrategy(),
            AvailabilityValidationStrategy(),
            WorkerShiftLimitValidationStrategy(
                max_shifts_per_period=self.max_shifts_per_period
            ),
            SkillsValidationStrategy(),
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
        """
        Compute request fulfillment statistics.

        The engine is period-granular (one assignment covers the whole
        period), so fulfillment is evaluated per request over the periods
        it overlaps rather than per calendar day: a positive request is
        fulfilled if the worker has the shift type in at least one
        overlapping period; a negative request is fulfilled if the worker
        avoids the shift type in every overlapping period. This mirrors the
        at-least-once request semantics enforced by RequestConstraint.
        """
        if not self.requests:
            result.statistics["request_fulfillment"] = {
                "total_requests": 0,
                "fulfilled": 0,
                "violated": 0,
                "rate": 1.0,  # No requests means 100% fulfilled
            }
            return

        # Build assignment lookup: (worker_id, period_index, shift_type_id)
        assignments: set[tuple[str, int, str]] = set()
        for period in self.schedule.periods:
            for worker_id, shifts in period.assignments.items():
                for shift in shifts:
                    assignments.add(
                        (worker_id, period.period_index, shift.shift_type_id)
                    )

        fulfilled = 0
        violated = 0

        for request in self.requests:
            overlapping_periods = [
                period
                for period in self.schedule.periods
                if request.start_date <= period.period_end
                and request.end_date >= period.period_start
            ]
            if not overlapping_periods:
                continue

            assigned_in_any_period = any(
                (request.worker_id, period.period_index, request.shift_type_id)
                in assignments
                for period in overlapping_periods
            )

            if request.is_positive:
                # Positive request: fulfilled if assigned in at least one
                # overlapping period.
                if assigned_in_any_period:
                    fulfilled += 1
                else:
                    violated += 1
            else:
                # Negative request: fulfilled if NOT assigned in ANY
                # overlapping period (i.e. avoided in every one).
                if not assigned_in_any_period:
                    fulfilled += 1
                else:
                    violated += 1

        total = fulfilled + violated
        rate = fulfilled / total if total > 0 else 1.0

        result.statistics["request_fulfillment"] = {
            "total_requests": total,
            "fulfilled": fulfilled,
            "violated": violated,
            "rate": rate,
        }
