"""FeasibilityChecker for pre-solve validation."""

from collections import Counter
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from shift_solver.constraints.base import ConstraintConfig
from shift_solver.models import (
    Availability,
    SchedulingRequest,
    ShiftFrequencyRequirement,
    ShiftOrderPreference,
    ShiftType,
    Worker,
    is_eligible,
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
    - No duplicate worker or shift type IDs
    - Hard requests don't conflict with restrictions/availability or with
      each other
    """

    def __init__(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        period_dates: list[tuple[date, date]],
        availabilities: list[Availability] | None = None,
        shift_frequency_requirements: list[ShiftFrequencyRequirement] | None = None,
        shift_order_preferences: list[ShiftOrderPreference] | None = None,
        requests: list[SchedulingRequest] | None = None,
        constraint_configs: dict[str, ConstraintConfig] | None = None,
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
            requests: Optional list of scheduling requests
            constraint_configs: Optional dict mapping constraint_id to the
                resolved solver ConstraintConfig, as passed to ShiftSolver.
                Used to resolve constraints (e.g. worker_shift_limit) whose
                parameters affect what "feasible" means. Constraints not
                present here fall back to their ConstraintRegistry default.
        """
        self.workers = workers
        self.shift_types = shift_types
        self.period_dates = period_dates
        self.availabilities = availabilities or []
        self.shift_frequency_requirements = shift_frequency_requirements or []
        self.shift_order_preferences = shift_order_preferences or []
        self.requests = requests or []
        self.constraint_configs = constraint_configs or {}

    def check(self) -> FeasibilityResult:
        """
        Run all feasibility checks.

        Returns:
            FeasibilityResult with is_feasible flag and list of issues
        """
        result = FeasibilityResult(is_feasible=True, issues=[])

        # Run all checks
        self._check_period_dates(result)
        self._check_duplicate_ids(result)
        self._check_basic_coverage(result)
        self._check_restrictions(result)
        self._check_availability_conflicts(result)
        self._check_combined_feasibility(result)
        self._check_skills(result)
        self._check_worker_shift_limit_capacity(result)
        self._check_unknown_availability_references(result)
        self._check_shift_frequency_requirements(result)
        self._check_shift_order_preferences(result)
        self._check_requests(result)

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

    def _check_duplicate_ids(self, result: FeasibilityResult) -> None:
        """Check for duplicate worker IDs and duplicate shift type IDs.

        Duplicate IDs silently corrupt lookups throughout the solver (later
        entries shadow earlier ones), so they're treated as hard issues
        rather than warnings.
        """
        worker_id_counts = Counter(w.id for w in self.workers)
        duplicate_worker_ids = sorted(
            wid for wid, count in worker_id_counts.items() if count > 1
        )
        if duplicate_worker_ids:
            result.add_issue(
                "duplicate_id",
                f"Duplicate worker IDs found: {duplicate_worker_ids}",
                duplicate_worker_ids=duplicate_worker_ids,
            )

        shift_type_id_counts = Counter(st.id for st in self.shift_types)
        duplicate_shift_type_ids = sorted(
            sid for sid, count in shift_type_id_counts.items() if count > 1
        )
        if duplicate_shift_type_ids:
            result.add_issue(
                "duplicate_id",
                f"Duplicate shift type IDs found: {duplicate_shift_type_ids}",
                duplicate_shift_type_ids=duplicate_shift_type_ids,
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
        if not self._is_constraint_active("restriction"):
            # The restriction constraint is disabled (or configured soft), so
            # Worker.can_work_shift restrictions are never enforced by the
            # solver - flagging them here would be a false INFEASIBLE.
            return

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
        """Check for periods where all workers are unavailable for every shift.

        Only unavailability records with shift_type_id=None (i.e. total
        unavailability) count here - a record scoped to a specific shift
        type doesn't stop a worker from covering other shifts that period.
        """
        if not self.availabilities:
            return
        if not self._is_constraint_active("availability"):
            # The availability constraint is disabled (or configured soft),
            # so 'unavailable' records are never enforced by the solver -
            # flagging them here would be a false INFEASIBLE.
            return

        for period_idx, (period_start, period_end) in enumerate(self.period_dates):
            # Find workers unavailable for this entire period (all shifts)
            unavailable_workers = set()

            for avail in self.availabilities:
                if avail.availability_type != "unavailable":
                    continue
                if avail.shift_type_id is not None:
                    # Scoped to a specific shift type - doesn't make the
                    # worker unavailable for everything.
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

    def _unavailable_workers_for_shift(
        self,
        shift_type_id: str,
        period_start: date,
        period_end: date,
    ) -> set[str]:
        """Find workers unavailable for a specific shift type during a period.

        Respects shift-type scoping: an unavailability record with
        shift_type_id=None applies to every shift, while one with a
        shift_type_id set only applies to that shift type.
        """
        unavailable_workers = set()
        for avail in self.availabilities:
            if avail.availability_type != "unavailable":
                continue
            if avail.shift_type_id is not None and avail.shift_type_id != shift_type_id:
                continue
            if avail.start_date <= period_end and avail.end_date >= period_start:
                unavailable_workers.add(avail.worker_id)
        return unavailable_workers

    def _check_combined_feasibility(self, result: FeasibilityResult) -> None:
        """Check combined restrictions and availability for each period/shift."""
        if result.issues:
            # Already have fundamental issues, skip detailed check
            return

        restriction_active = self._is_constraint_active("restriction")
        availability_active = self._is_constraint_active("availability")
        if not restriction_active and not availability_active:
            # Neither constraint is enforced by the solver, so there's no
            # restriction/availability combination to flag here.
            return

        for period_idx, (period_start, period_end) in enumerate(self.period_dates):
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

                # Unavailability scoped to this shift type (or unscoped) -
                # only consulted if the availability constraint is active.
                unavailable_workers = (
                    self._unavailable_workers_for_shift(
                        shift_type.id, period_start, period_end
                    )
                    if availability_active
                    else set()
                )

                available_count = 0
                for worker in self.workers:
                    # Worker must not be unavailable for this shift
                    if availability_active and worker.id in unavailable_workers:
                        continue
                    # Worker must not be restricted from this shift
                    if restriction_active and not worker.can_work_shift(shift_type.id):
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

    def _worker_qualifies_for_skills(
        self, worker: Worker, shift_type: ShiftType
    ) -> bool:
        """
        Check whether a worker's attributes satisfy a shift's requirements.

        Mirrors SkillsConstraint._worker_qualifies exactly (including using
        dict.get rather than a membership check, so a missing attribute key
        is treated the same as one whose value doesn't match).
        """
        return all(
            worker.attributes.get(key) == value
            for key, value in shift_type.required_attributes.items()
        )

    def _check_skills(self, result: FeasibilityResult) -> None:
        """
        Check that shift types with required_attributes have enough
        qualifying workers.

        A shift type with non-empty required_attributes is only fillable by
        workers whose attributes satisfy every required key/value pair
        (SkillsConstraint forces every other worker's assignment variable to
        0 for that shift type). If fewer workers qualify than
        workers_required, the solver can never fill the shift - without this
        check that surfaces as a bare INFEASIBLE with no indication that
        skills/attributes are the cause.
        """
        if not self._is_constraint_active("skills"):
            # skills is disabled (or configured soft), so required_attributes
            # is never enforced by the solver - flagging a shortage here
            # would be a false INFEASIBLE.
            return

        for shift_type in self.shift_types:
            if not shift_type.required_attributes:
                # Unconstrained - any worker may work this shift type.
                continue

            qualifying_workers = [
                w
                for w in self.workers
                if self._worker_qualifies_for_skills(w, shift_type)
            ]

            if len(qualifying_workers) < shift_type.workers_required:
                required_attrs = ", ".join(
                    f"{key}={value}"
                    for key, value in shift_type.required_attributes.items()
                )
                result.add_issue(
                    "skills",
                    f"Not enough workers qualify for shift '{shift_type.name}' "
                    f"(requires attributes: {required_attrs}): "
                    f"{len(qualifying_workers)} qualify, "
                    f"{shift_type.workers_required} required",
                    shift_type_id=shift_type.id,
                    required_attributes=dict(shift_type.required_attributes),
                    workers_qualified=len(qualifying_workers),
                    workers_required=shift_type.workers_required,
                )

    def _resolve_constraint_config(self, constraint_id: str) -> ConstraintConfig:
        """Resolve a constraint's config, falling back to the registry default.

        Mirrors ShiftSolver._get_constraint_config: a caller-supplied
        constraint_configs entry wins, otherwise the ConstraintRegistry
        registration (the single source of truth for defaults, per the
        worker_shift_limit/skills/workload design) is used.
        """
        configured = self.constraint_configs.get(constraint_id)
        if configured is not None:
            return configured

        from shift_solver.solver.constraint_registry import (
            ConstraintRegistry,
            register_builtin_constraints,
        )

        register_builtin_constraints()
        registration = ConstraintRegistry.get_all_constraints().get(constraint_id)
        if registration is not None:
            return registration.default_config
        return ConstraintConfig()

    def _resolve_worker_shift_limit_config(self) -> ConstraintConfig:
        """Resolve the worker_shift_limit config, falling back to the registry default."""
        return self._resolve_constraint_config("worker_shift_limit")

    def _is_constraint_active(self, constraint_id: str) -> bool:
        """
        Whether the solver actually enforces this constraint as hard.

        ShiftSolver._apply_hard_constraints applies a hard-registered
        constraint (coverage, restriction, availability, worker_shift_limit,
        skills) whenever it is enabled - those constraints have no soft mode
        and never read is_hard, so enabled alone decides. Soft-registered
        constraints are only enforced (violations pinned to zero) when both
        enabled and is_hard. A check gated on the wrong condition would
        report false INFEASIBLE results, or skip a diagnostic the solver is
        about to fail on.
        """
        from shift_solver.solver.constraint_registry import (
            ConstraintRegistry,
            register_builtin_constraints,
        )

        register_builtin_constraints()
        config = self._resolve_constraint_config(constraint_id)
        if constraint_id in ConstraintRegistry.get_hard_constraints():
            return bool(config.enabled)
        return bool(config.enabled) and bool(config.is_hard)

    def _check_worker_shift_limit_capacity(self, result: FeasibilityResult) -> None:
        """Check aggregate per-period demand against worker_shift_limit capacity.

        worker_shift_limit caps each worker to at most max_shifts_per_period
        assignments per period (across all shift types combined). Unlike
        _check_basic_coverage/_check_combined_feasibility, which examine each
        shift type in isolation, total per-period demand can exceed total
        worker capacity even when every individual shift type is fillable on
        its own - and no combination of assignments can satisfy coverage in
        that case, regardless of skills or availability. Report the shortfall
        explicitly instead of leaving the solver to return a bare INFEASIBLE.
        """
        if not self.workers or result.issues:
            # Already have fundamental issues, skip detailed check.
            return

        if not self._is_constraint_active("worker_shift_limit"):
            # Not enforced - doesn't bound feasibility.
            return

        config = self._resolve_worker_shift_limit_config()

        max_shifts_per_period = config.get_param("max_shifts_per_period", 1)
        capacity = len(self.workers) * max_shifts_per_period

        for period_idx, (period_start, period_end) in enumerate(self.period_dates):
            total_required = 0
            for shift_type in self.shift_types:
                if shift_type.applicable_days is not None:
                    applicable_count = self._count_applicable_days(
                        shift_type, period_start, period_end
                    )
                    if applicable_count == 0:
                        # No applicable days - no coverage required this period.
                        continue
                total_required += shift_type.workers_required

            if total_required > capacity:
                result.add_issue(
                    "worker_shift_limit",
                    f"Period {period_idx}: total shift demand ({total_required}) "
                    f"exceeds worker capacity ({len(self.workers)} workers x "
                    f"{max_shifts_per_period} shift(s) per period = {capacity}); "
                    f"short by {total_required - capacity}",
                    period_index=period_idx,
                    total_required=total_required,
                    capacity=capacity,
                    max_shifts_per_period=max_shifts_per_period,
                    shortfall=total_required - capacity,
                )

    def _check_unknown_availability_references(self, result: FeasibilityResult) -> None:
        """Warn about availability records referencing unknown workers/shift types."""
        if not self.availabilities:
            return

        worker_ids = {w.id for w in self.workers}
        shift_type_ids = {st.id for st in self.shift_types}

        for avail in self.availabilities:
            if avail.worker_id not in worker_ids:
                result.add_warning(
                    "availability",
                    f"Availability record references unknown worker "
                    f"'{avail.worker_id}'",
                    worker_id=avail.worker_id,
                )
            if (
                avail.shift_type_id is not None
                and avail.shift_type_id not in shift_type_ids
            ):
                result.add_warning(
                    "availability",
                    f"Availability record references unknown shift type "
                    f"'{avail.shift_type_id}'",
                    shift_type_id=avail.shift_type_id,
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
            workable_shifts = {st for st in valid_shifts if worker.can_work_shift(st)}

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
        shift_type_map = {st.id: st for st in self.shift_types}
        shift_type_ids = set(shift_type_map)
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
                pref.trigger_type == "category" and pref.trigger_value not in categories
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

            # Check if applicable workers are ineligible for all preferred
            # shifts, whether restricted (can_work_shift) or simply missing
            # a required skill/attribute (SkillsConstraint) -- either way
            # the constraint's preference indicator can never be satisfied.
            applicable_workers = (
                [worker_map[wid] for wid in pref.worker_ids if wid in worker_map]
                if pref.worker_ids
                else list(self.workers)
            )
            if (
                pref.preferred_type == "shift_type"
                and pref.preferred_value in shift_type_ids
            ):
                preferred_shift_type = shift_type_map[pref.preferred_value]
                all_ineligible = all(
                    not is_eligible(w, preferred_shift_type) for w in applicable_workers
                )
                if applicable_workers and all_ineligible:
                    result.add_warning(
                        "shift_order_preference",
                        f"Rule '{pref.rule_id}': all applicable workers are "
                        f"ineligible (restricted or missing required "
                        f"attributes) for preferred shift "
                        f"'{pref.preferred_value}'",
                        rule_id=pref.rule_id,
                    )

    def _applicable_periods_for_request(self, request: SchedulingRequest) -> list[int]:
        """Find which period indices overlap with a request's date range."""
        applicable = []
        for period_idx, (period_start, period_end) in enumerate(self.period_dates):
            if request.start_date <= period_end and request.end_date >= period_start:
                applicable.append(period_idx)
        return applicable

    def _worker_available_for_shift_in_period(
        self,
        worker_id: str,
        shift_type_id: str,
        period_start: date,
        period_end: date,
    ) -> bool:
        """Check whether a worker is not marked unavailable for a shift/period."""
        for avail in self.availabilities:
            if avail.worker_id != worker_id or avail.availability_type != "unavailable":
                continue
            if avail.shift_type_id is not None and avail.shift_type_id != shift_type_id:
                continue
            if avail.start_date <= period_end and avail.end_date >= period_start:
                return False
        return True

    def _check_requests(self, result: FeasibilityResult) -> None:
        """
        Check that scheduling requests are internally consistent and satisfiable.

        Flags (as hard issues):
        - A hard positive request for a shift the worker is restricted from.
        - A hard positive request for a shift the worker is unavailable for
          during EVERY period the request overlaps (so the solver's
          "at least once in range" constraint can never be satisfied).
        - Two contradictory hard requests (a positive and a negative for the
          same worker/shift whose applicable periods make both impossible to
          satisfy simultaneously) - including when a positive request's
          periods are only fully covered by the UNION of several hard
          negatives rather than any single one of them.

        The restriction- and unavailability-based checks are only applied
        when the corresponding 'restriction'/'availability' constraint is
        enabled and hard (see _is_constraint_active) - a disabled or soft
        constraint is never enforced by the solver, so requests conflicting
        with it are not actually infeasible.

        Flags (as warnings):
        - A request referencing an unknown worker or shift type.
        """
        if not self.requests:
            return

        request_config = self._resolve_constraint_config("request")
        if not request_config.enabled:
            # RequestConstraint is never built when disabled, so requests
            # cannot make the model infeasible - contradictions included.
            return

        worker_map = {w.id: w for w in self.workers}
        shift_type_ids = {st.id for st in self.shift_types}
        restriction_active = self._is_constraint_active("restriction")
        availability_active = self._is_constraint_active("availability")

        # Hard requests, keyed by (worker_id, shift_type_id), tracked with
        # their applicable periods for contradiction detection.
        hard_positive: list[tuple[SchedulingRequest, set[int]]] = []
        hard_negative: list[tuple[SchedulingRequest, set[int]]] = []

        for request in self.requests:
            unknown_worker = request.worker_id not in worker_map
            unknown_shift = request.shift_type_id not in shift_type_ids

            if unknown_worker or unknown_shift:
                missing = []
                if unknown_worker:
                    missing.append(f"worker '{request.worker_id}'")
                if unknown_shift:
                    missing.append(f"shift type '{request.shift_type_id}'")
                result.add_warning(
                    "request",
                    f"Request references unknown {' and '.join(missing)}",
                    worker_id=request.worker_id,
                    shift_type_id=request.shift_type_id,
                )
                continue

            request_is_hard = (
                request.is_hard
                if request.is_hard is not None
                else bool(request_config.is_hard)
            )
            if not request_is_hard:
                # Only hard requests (per-record flag, falling back to the
                # request constraint's configured is_hard, mirroring
                # RequestConstraint) are checked here; soft requests can't
                # make the schedule infeasible.
                continue

            applicable_periods = self._applicable_periods_for_request(request)
            if not applicable_periods:
                continue

            worker = worker_map[request.worker_id]

            if request.is_positive:
                hard_positive.append((request, set(applicable_periods)))

                if restriction_active and not worker.can_work_shift(
                    request.shift_type_id
                ):
                    result.add_issue(
                        "request",
                        f"Hard positive request for worker '{request.worker_id}' "
                        f"on shift '{request.shift_type_id}' conflicts with a "
                        f"restriction: worker cannot work this shift type",
                        worker_id=request.worker_id,
                        shift_type_id=request.shift_type_id,
                    )
                    continue

                if availability_active:
                    all_unavailable = all(
                        not self._worker_available_for_shift_in_period(
                            request.worker_id,
                            request.shift_type_id,
                            *self.period_dates[period_idx],
                        )
                        for period_idx in applicable_periods
                    )
                    if all_unavailable:
                        result.add_issue(
                            "request",
                            f"Hard positive request for worker '{request.worker_id}' "
                            f"on shift '{request.shift_type_id}' conflicts with "
                            f"unavailability: worker is unavailable for every "
                            f"period the request covers",
                            worker_id=request.worker_id,
                            shift_type_id=request.shift_type_id,
                        )
            else:
                hard_negative.append((request, set(applicable_periods)))

        # Contradictory hard requests: a positive request whose applicable
        # periods are entirely covered by the UNION of ALL hard-negative
        # requests for the same worker/shift can never be satisfied - even
        # when no single negative individually covers every period, two (or
        # more) negatives can jointly cover it.
        negative_periods_by_key: dict[tuple[str, str], set[int]] = {}
        for neg_request, neg_periods in hard_negative:
            key = (neg_request.worker_id, neg_request.shift_type_id)
            negative_periods_by_key.setdefault(key, set()).update(neg_periods)

        for pos_request, pos_periods in hard_positive:
            key = (pos_request.worker_id, pos_request.shift_type_id)
            negative_union = negative_periods_by_key.get(key)
            if negative_union and pos_periods and pos_periods <= negative_union:
                result.add_issue(
                    "request",
                    f"Contradictory hard requests for worker "
                    f"'{pos_request.worker_id}' on shift "
                    f"'{pos_request.shift_type_id}': one request requires "
                    f"it, another forbids it for the same period(s)",
                    worker_id=pos_request.worker_id,
                    shift_type_id=pos_request.shift_type_id,
                )
