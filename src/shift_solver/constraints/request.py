"""Request constraint - honors worker scheduling preferences."""

from datetime import date
from typing import TYPE_CHECKING, Any

from ortools.sat.python import cp_model

from shift_solver.constraints.base import BaseConstraint, ConstraintConfig
from shift_solver.models import SchedulingRequest, ShiftType, Worker
from shift_solver.utils import get_logger

if TYPE_CHECKING:
    from shift_solver.solver.types import SolverVariables

logger = get_logger("constraints.request")


class RequestConstraint(BaseConstraint):
    """
    Soft constraint honoring worker scheduling requests.

    Handles both positive requests (worker wants to work a shift) and
    negative requests (worker wants to avoid a shift). Violations are
    weighted by priority level.

    Positive requests use "at least once in range" semantics: a request
    spanning multiple periods is satisfied if the worker is assigned the
    shift in ANY one of the overlapping periods (hard -> sum of assignment
    vars over the range >= 1; soft -> a single violation var true iff zero
    assignments across the whole range). Negative requests keep per-period
    semantics: the worker must (or should) avoid the shift in EVERY
    overlapping period.

    Required context:
        - workers: list[Worker] - available workers
        - shift_types: list[ShiftType] - shift types
        - num_periods: int - number of scheduling periods
        - requests: list[SchedulingRequest] - worker requests
        - period_dates: list[tuple[date, date]] - (start, end) for each period

    Config parameters:
        - None currently
    """

    constraint_id = "request"

    # RequestConstraint implements its own per-record hard/soft semantics
    # (each request's is_hard can override the constraint-level config), so
    # the solver's generic soft->hard enforcement must not also force every
    # violation variable to 0 on top of that.
    handles_hard_mode = True

    def __init__(
        self,
        model: cp_model.CpModel,
        variables: "SolverVariables",
        config: ConstraintConfig | None = None,
    ) -> None:
        """Initialize request constraint."""
        # Default config handled by BaseConstraint
        # Registry provides config when instantiated via solver
        super().__init__(model, variables, config)

    def apply(self, **context: Any) -> None:
        """
        Apply request constraint to the model.

        Creates violation variables for each unfulfilled request.
        For positive requests, violation occurs when worker is NOT assigned.
        For negative requests, violation occurs when worker IS assigned.

        Args:
            **context: Must include workers, shift_types, num_periods,
                      requests, period_dates
        """
        if not self.is_enabled:
            return

        workers: list[Worker] = context["workers"]
        shift_types: list[ShiftType] = context["shift_types"]
        num_periods: int = context["num_periods"]
        requests: list[SchedulingRequest] = context.get("requests", [])
        period_dates: list[tuple[date, date]] = context["period_dates"]

        if not requests:
            return

        # Build lookups
        valid_worker_ids = {w.id for w in workers}
        valid_shift_ids = {st.id for st in shift_types}

        for idx, request in enumerate(requests):
            # Skip invalid requests
            if request.worker_id not in valid_worker_ids:
                logger.warning(
                    "Skipping request %d: unknown worker_id '%s'",
                    idx,
                    request.worker_id,
                )
                continue
            if request.shift_type_id not in valid_shift_ids:
                logger.warning(
                    "Skipping request %d: unknown shift_type_id '%s'",
                    idx,
                    request.shift_type_id,
                )
                continue

            # Find which periods this request applies to
            applicable_periods = self._find_applicable_periods(
                request, period_dates, num_periods
            )

            if not applicable_periods:
                continue

            # Create violation variable for this request
            self._add_request_constraint(
                request=request,
                periods=applicable_periods,
                request_idx=idx,
            )

    def _find_applicable_periods(
        self,
        request: SchedulingRequest,
        period_dates: list[tuple[date, date]],
        num_periods: int,
    ) -> list[int]:
        """Find which periods overlap with the request dates."""
        applicable = []
        for period_idx in range(num_periods):
            if period_idx < len(period_dates):
                period_start, period_end = period_dates[period_idx]
                # Check overlap
                if (
                    request.start_date <= period_end
                    and request.end_date >= period_start
                ):
                    applicable.append(period_idx)
        return applicable

    def _add_request_constraint(
        self,
        request: SchedulingRequest,
        periods: list[int],
        request_idx: int,
    ) -> None:
        """
        Add constraint for a single request.

        Positive requests use "at least once in range" semantics: the
        request is satisfied if the worker is assigned in ANY overlapping
        period (hard -> sum of assignment vars over the range >= 1;
        soft -> one violation var true iff zero assignments across the
        whole range). Negative requests keep per-period semantics: the
        worker must (or should) avoid the shift in EVERY overlapping period.

        When is_hard=True, enforces the request as a hard constraint.
        When is_hard=False, creates violation variable(s) for soft penalties.
        """
        assignment_vars = []
        valid_periods = []
        for period in periods:
            try:
                assignment_var = self.variables.get_assignment_var(
                    request.worker_id, period, request.shift_type_id
                )
            except KeyError:
                logger.warning(
                    "Request %d for worker '%s' shift '%s': no assignment "
                    "variable for period %d (shift may not apply that period)",
                    request_idx,
                    request.worker_id,
                    request.shift_type_id,
                    period,
                )
                continue
            assignment_vars.append(assignment_var)
            valid_periods.append(period)

        if not assignment_vars:
            return

        request_is_hard = request.is_hard if request.is_hard is not None else self.is_hard

        if request.is_positive:
            self._add_positive_request_constraint(
                request, assignment_vars, request_idx, request_is_hard
            )
        else:
            self._add_negative_request_constraint(
                request, valid_periods, assignment_vars, request_idx, request_is_hard
            )

    def _add_positive_request_constraint(
        self,
        request: SchedulingRequest,
        assignment_vars: list[cp_model.IntVar],
        request_idx: int,
        request_is_hard: bool,
    ) -> None:
        """
        Add "at least once in range" constraint for a positive request.

        Hard: sum(assignment_vars) >= 1 (the worker must be assigned in at
        least one of the overlapping periods).
        Soft: a single violation variable is true iff the sum is 0 (the
        worker was never assigned across the whole range).
        """
        total = sum(assignment_vars)

        if request_is_hard:
            self.model.add(total >= 1)
            self._constraint_count += 1
            return

        violation_name = (
            f"req_viol_{request.worker_id}_{request.shift_type_id}_r{request_idx}"
        )
        violation_var = self.model.new_bool_var(violation_name)
        self.model.add(total == 0).only_enforce_if(violation_var)
        self.model.add(total >= 1).only_enforce_if(violation_var.negated())

        self._violation_variables[violation_name] = violation_var
        self._violation_priorities[violation_name] = request.priority
        self._constraint_count += 2

    def _add_negative_request_constraint(
        self,
        request: SchedulingRequest,
        periods: list[int],
        assignment_vars: list[cp_model.IntVar],
        request_idx: int,
        request_is_hard: bool,
    ) -> None:
        """
        Add per-period constraints for a negative request.

        The worker must (hard) or should (soft) avoid the shift in EVERY
        overlapping period - unchanged from prior behavior.
        """
        for period, assignment_var in zip(periods, assignment_vars, strict=True):
            if request_is_hard:
                # Must NOT be assigned
                self.model.add(assignment_var == 0)
                self._constraint_count += 1
                continue

            # Soft constraint: violation when assigned
            violation_name = (
                f"req_viol_{request.worker_id}_{request.shift_type_id}"
                f"_p{period}_r{request_idx}"
            )
            violation_var = self.model.new_bool_var(violation_name)
            self.model.add(assignment_var >= 1).only_enforce_if(violation_var)
            self.model.add(assignment_var == 0).only_enforce_if(
                violation_var.negated()
            )

            self._violation_variables[violation_name] = violation_var
            self._violation_priorities[violation_name] = request.priority
            self._constraint_count += 2
