"""FeasibilityChecker for pre-solve validation."""

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from shift_solver.models import Availability, ShiftType, Worker
from shift_solver.utils import get_logger

logger = get_logger("validation.feasibility")


@dataclass
class FeasibilityResult:
    """Result of feasibility check."""

    is_feasible: bool
    issues: list[dict[str, Any]]
    warnings: list[dict[str, Any]] = field(default_factory=list)

    def add_issue(
        self, issue_type: str, message: str, severity: str = "error", **details: Any
    ) -> None:
        """Add an issue to the result."""
        self.issues.append(
            {"type": issue_type, "message": message, "severity": severity, **details}
        )
        if severity == "error":
            self.is_feasible = False

    def add_warning(self, issue_type: str, message: str, **details: Any) -> None:
        """Add a warning to the result."""
        self.warnings.append(
            {"type": issue_type, "message": message, "severity": "warning", **details}
        )


class FeasibilityChecker:
    """
    Validates input data before attempting to solve.

    Performs checks to detect obviously infeasible problems:
    - Sufficient workers for coverage requirements
    - No periods where all workers are unavailable
    - Worker restrictions don't make shifts unfillable
    - Valid date ranges and periods
    """

    def __init__(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
        availabilities: list[Availability] | None = None,
    ) -> None:
        """
        Initialize the feasibility checker.

        Args:
            workers: List of workers to schedule
            shift_types: List of shift types with requirements
            period_dates: List of (start_date, end_date) for each period
            availabilities: Optional list of availability records
        """
        self.workers = workers
        self.shift_types = shift_types
        self.period_dates = period_dates
        self.availabilities = availabilities or []

    def check(self) -> FeasibilityResult:
        """
        Run all feasibility checks.

        Returns:
            FeasibilityResult with is_feasible flag and list of issues
        """
        result = FeasibilityResult(is_feasible=True, issues=[])

        # Run all checks
        self._check_period_dates(result)
        self._check_basic_coverage(result)
        self._check_restrictions(result)
        self._check_availability_conflicts(result)
        self._check_combined_feasibility(result)

        if result.is_feasible:
            logger.info("Feasibility check passed")
        else:
            logger.warning(f"Feasibility check failed with {len(result.issues)} issues")
            for issue in result.issues:
                logger.warning(f"  - {issue['type']}: {issue['message']}")

        return result

    def _check_period_dates(self, result: FeasibilityResult) -> None:
        """Check that period dates are valid."""
        if not self.period_dates:
            result.add_issue(
                "period",
                "No scheduling periods defined",
            )
            return

        for i, (start, end) in enumerate(self.period_dates):
            if end < start:
                result.add_issue(
                    "period",
                    f"Period {i} has end date before start date",
                    period_index=i,
                )

    def _check_basic_coverage(self, result: FeasibilityResult) -> None:
        """Check that there are enough workers for basic coverage."""
        if not self.workers:
            result.add_issue(
                "coverage",
                "No workers defined",
            )
            return

        # Find maximum workers required for any single shift type
        max_required = max(st.workers_required for st in self.shift_types)

        if len(self.workers) < max_required:
            result.add_issue(
                "coverage",
                f"Not enough workers ({len(self.workers)}) for shift "
                f"requiring {max_required} workers",
                workers_available=len(self.workers),
                workers_required=max_required,
            )

    def _check_restrictions(self, result: FeasibilityResult) -> None:
        """Check that worker restrictions don't make shifts unfillable."""
        for shift_type in self.shift_types:
            # Count workers who can work this shift type
            available_workers = [
                w for w in self.workers if w.can_work_shift(shift_type.id)
            ]

            if len(available_workers) < shift_type.workers_required:
                result.add_issue(
                    "restriction",
                    f"Not enough workers can work shift '{shift_type.name}': "
                    f"{len(available_workers)} available, {shift_type.workers_required} required",
                    shift_type_id=shift_type.id,
                    workers_available=len(available_workers),
                    workers_required=shift_type.workers_required,
                )

    def _check_availability_conflicts(self, result: FeasibilityResult) -> None:
        """Check for periods where all workers are unavailable."""
        if not self.availabilities:
            return

        for period_idx, (period_start, period_end) in enumerate(self.period_dates):
            # Find workers unavailable for this entire period
            unavailable_workers = set()

            for avail in self.availabilities:
                if avail.availability_type != "unavailable":
                    continue
                # Check if availability overlaps with period
                if avail.start_date <= period_end and avail.end_date >= period_start:
                    unavailable_workers.add(avail.worker_id)

            # Check if all workers are unavailable
            all_worker_ids = {w.id for w in self.workers}
            available_worker_ids = all_worker_ids - unavailable_workers

            if not available_worker_ids:
                result.add_issue(
                    "availability",
                    f"All workers unavailable for period {period_idx} "
                    f"({period_start} to {period_end})",
                    period_index=period_idx,
                    period_start=str(period_start),
                    period_end=str(period_end),
                )

    def _check_combined_feasibility(self, result: FeasibilityResult) -> None:
        """Check combined restrictions and availability for each period/shift."""
        if result.issues:
            # Already have fundamental issues, skip detailed check
            return

        for period_idx, (period_start, period_end) in enumerate(self.period_dates):
            # Find workers unavailable for this period
            unavailable_workers = set()
            for avail in self.availabilities:
                if avail.availability_type != "unavailable":
                    continue
                if avail.start_date <= period_end and avail.end_date >= period_start:
                    unavailable_workers.add(avail.worker_id)

            # For each shift type, count truly available workers
            for shift_type in self.shift_types:
                available_count = 0
                for worker in self.workers:
                    # Worker must not be unavailable
                    if worker.id in unavailable_workers:
                        continue
                    # Worker must not be restricted from this shift
                    if not worker.can_work_shift(shift_type.id):
                        continue
                    available_count += 1

                if available_count < shift_type.workers_required:
                    result.add_issue(
                        "combined",
                        f"Period {period_idx}: Not enough workers for "
                        f"shift '{shift_type.name}' after restrictions and availability: "
                        f"{available_count} available, {shift_type.workers_required} required",
                        period_index=period_idx,
                        shift_type_id=shift_type.id,
                        workers_available=available_count,
                        workers_required=shift_type.workers_required,
                    )
