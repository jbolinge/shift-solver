"""FeasibilityChecker for pre-solve validation."""

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from shift_solver.models import (
    Availability,
    ShiftFrequencyRequirement,
    ShiftOrderPreference,
    ShiftType,
    Worker,
)
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
        shift_frequency_requirements: list[ShiftFrequencyRequirement] | None = None,
        shift_order_preferences: list[ShiftOrderPreference] | None = None,
    ) -> None:
        """
        Initialize the feasibility checker.

        Args:
            workers: List of workers to schedule
            shift_types: List of shift types with requirements
            period_dates: List of (start_date, end_date) for each period
            availabilities: Optional list of availability records
            shift_frequency_requirements: Optional list of shift frequency requirements
            shift_order_preferences: Optional list of shift order preferences
        """
        self.workers = workers
        self.shift_types = shift_types
        self.period_dates = period_dates
        self.availabilities = availabilities or []
        self.shift_frequency_requirements = shift_frequency_requirements or []
        self.shift_order_preferences = shift_order_preferences or []

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
        self._check_shift_frequency_requirements(result)
        self._check_shift_order_preferences(result)

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

    def _count_applicable_days(
        self,
        shift_type: ShiftType,
        period_start: date,
        period_end: date,
    ) -> int:
        """
        Count how many days in the period the shift type applies to.

        Args:
            shift_type: Shift type with applicable_days
            period_start: Start date of the period
            period_end: End date of the period

        Returns:
            Number of days in the period where the shift applies
        """
        if shift_type.applicable_days is None:
            # None means all days - count all days in period
            return (period_end - period_start).days + 1

        count = 0
        current = period_start
        while current <= period_end:
            if current.weekday() in shift_type.applicable_days:
                count += 1
            current += timedelta(days=1)
        return count

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
                # Skip coverage check if shift has no applicable days in this period
                if shift_type.applicable_days is not None:
                    applicable_count = self._count_applicable_days(
                        shift_type, period_start, period_end
                    )
                    if applicable_count == 0:
                        # No applicable days - no coverage required
                        continue

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

    def _check_shift_frequency_requirements(self, result: FeasibilityResult) -> None:
        """Check that shift frequency requirements are satisfiable."""
        if not self.shift_frequency_requirements:
            return

        worker_map = {w.id: w for w in self.workers}
        shift_type_ids = {st.id for st in self.shift_types}
        num_periods = len(self.period_dates)

        for req in self.shift_frequency_requirements:
            # Check if worker exists
            if req.worker_id not in worker_map:
                result.add_warning(
                    "shift_frequency",
                    f"Shift frequency requirement references unknown worker "
                    f"'{req.worker_id}'",
                    worker_id=req.worker_id,
                )
                continue

            worker = worker_map[req.worker_id]

            # Check if all shift types exist
            unknown_shifts = req.shift_types - shift_type_ids
            if unknown_shifts:
                # If ALL shift types are unknown, it's an error
                valid_shifts = req.shift_types & shift_type_ids
                if not valid_shifts:
                    result.add_issue(
                        "shift_frequency",
                        f"Shift frequency requirement for worker '{req.worker_id}' "
                        f"references unknown shift types: {sorted(unknown_shifts)}",
                        worker_id=req.worker_id,
                        unknown_shift_types=sorted(unknown_shifts),
                    )
                    continue

            # Check if worker can work any of the required shift types
            valid_shifts = req.shift_types & shift_type_ids
            workable_shifts = {
                st for st in valid_shifts if worker.can_work_shift(st)
            }

            if not workable_shifts:
                result.add_issue(
                    "shift_frequency",
                    f"Worker '{req.worker_id}' has shift frequency requirement "
                    f"for shift types {sorted(req.shift_types)} but is restricted "
                    f"from all of them",
                    worker_id=req.worker_id,
                    required_shift_types=sorted(req.shift_types),
                )

            # Warn if max_periods_between > num_periods
            if req.max_periods_between > num_periods:
                result.add_warning(
                    "shift_frequency",
                    f"Worker '{req.worker_id}' has max_periods_between="
                    f"{req.max_periods_between} but schedule only has "
                    f"{num_periods} periods. Constraint will use single window.",
                    worker_id=req.worker_id,
                    max_periods_between=req.max_periods_between,
                    num_periods=num_periods,
                )

    def _check_shift_order_preferences(self, result: FeasibilityResult) -> None:
        """Check that shift order preference rules reference valid entities."""
        if not self.shift_order_preferences:
            return

        worker_map = {w.id: w for w in self.workers}
        shift_type_ids = {st.id for st in self.shift_types}
        categories = {st.category for st in self.shift_types}
        num_periods = len(self.period_dates)

        if num_periods < 2:
            for pref in self.shift_order_preferences:
                result.add_warning(
                    "shift_order_preference",
                    f"Rule '{pref.rule_id}': schedule has fewer than 2 periods, "
                    f"constraint will have no effect",
                    rule_id=pref.rule_id,
                )
            return

        for pref in self.shift_order_preferences:
            # Check trigger references
            if (
                pref.trigger_type == "shift_type"
                and pref.trigger_value not in shift_type_ids
            ):
                result.add_warning(
                    "shift_order_preference",
                    f"Rule '{pref.rule_id}': unknown trigger shift type "
                    f"'{pref.trigger_value}'",
                    rule_id=pref.rule_id,
                )
            elif (
                pref.trigger_type == "category"
                and pref.trigger_value not in categories
            ):
                result.add_warning(
                    "shift_order_preference",
                    f"Rule '{pref.rule_id}': unknown trigger category "
                    f"'{pref.trigger_value}'",
                    rule_id=pref.rule_id,
                )

            # Check preferred references
            if (
                pref.preferred_type == "shift_type"
                and pref.preferred_value not in shift_type_ids
            ):
                result.add_warning(
                    "shift_order_preference",
                    f"Rule '{pref.rule_id}': unknown preferred shift type "
                    f"'{pref.preferred_value}'",
                    rule_id=pref.rule_id,
                )
            elif (
                pref.preferred_type == "category"
                and pref.preferred_value not in categories
            ):
                result.add_warning(
                    "shift_order_preference",
                    f"Rule '{pref.rule_id}': unknown preferred category "
                    f"'{pref.preferred_value}'",
                    rule_id=pref.rule_id,
                )

            # Check worker_ids
            if pref.worker_ids:
                unknown_workers = pref.worker_ids - set(worker_map.keys())
                if unknown_workers:
                    result.add_warning(
                        "shift_order_preference",
                        f"Rule '{pref.rule_id}': unknown worker IDs: "
                        f"{sorted(unknown_workers)}",
                        rule_id=pref.rule_id,
                    )

            # Check if applicable workers are restricted from all preferred shifts
            applicable_workers = (
                [worker_map[wid] for wid in pref.worker_ids if wid in worker_map]
                if pref.worker_ids
                else list(self.workers)
            )
            if pref.preferred_type == "shift_type" and pref.preferred_value in shift_type_ids:
                all_restricted = all(
                    not w.can_work_shift(pref.preferred_value)
                    for w in applicable_workers
                )
                if applicable_workers and all_restricted:
                    result.add_warning(
                        "shift_order_preference",
                        f"Rule '{pref.rule_id}': all applicable workers are "
                        f"restricted from preferred shift '{pref.preferred_value}'",
                        rule_id=pref.rule_id,
                    )
