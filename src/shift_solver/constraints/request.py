"""Request constraint - honors worker scheduling preferences."""

from datetime import date
from typing import TYPE_CHECKING, Any

from ortools.sat.python import cp_model

from shift_solver.constraints.base import BaseConstraint, ConstraintConfig
from shift_solver.models import SchedulingRequest, ShiftType, Worker

if TYPE_CHECKING:
    from shift_solver.solver.types import SolverVariables


class RequestConstraint(BaseConstraint):
    """
    Soft constraint honoring worker scheduling requests.

    Handles both positive requests (worker wants to work a shift) and
    negative requests (worker wants to avoid a shift). Violations are
    weighted by priority level.

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

    def __init__(
        self,
        model: cp_model.CpModel,
        variables: "SolverVariables",
        config: ConstraintConfig | None = None,
    ) -> None:
        """Initialize request constraint with soft default."""
        if config is None:
            config = ConstraintConfig(enabled=True, is_hard=False, weight=100)
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
                continue
            if request.shift_type_id not in valid_shift_ids:
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

        For positive requests: violation if NOT assigned
        For negative requests: violation if assigned

        When is_hard=True, enforces the request as a hard constraint.
        When is_hard=False, creates violation variables for soft penalties.
        """
        for period in periods:
            try:
                assignment_var = self.variables.get_assignment_var(
                    request.worker_id, period, request.shift_type_id
                )
            except KeyError:
                continue

            if self.is_hard:
                # Hard constraint: enforce directly
                if request.is_positive:
                    # Must be assigned
                    self.model.add(assignment_var >= 1)
                else:
                    # Must NOT be assigned
                    self.model.add(assignment_var == 0)
                self._constraint_count += 1
            else:
                # Soft constraint: create violation variable
                violation_name = (
                    f"req_viol_{request.worker_id}_{request.shift_type_id}"
                    f"_p{period}_r{request_idx}"
                )

                if request.is_positive:
                    # Positive request: violation when NOT assigned
                    # violation = (assignment == 0)
                    violation_var = self.model.new_bool_var(violation_name)
                    self.model.add(assignment_var == 0).only_enforce_if(violation_var)
                    self.model.add(assignment_var >= 1).only_enforce_if(
                        violation_var.negated()
                    )
                else:
                    # Negative request: violation when assigned
                    # violation = (assignment == 1)
                    violation_var = self.model.new_bool_var(violation_name)
                    self.model.add(assignment_var >= 1).only_enforce_if(violation_var)
                    self.model.add(assignment_var == 0).only_enforce_if(
                        violation_var.negated()
                    )

                # Store violation variable and priority separately
                # Priority is stored in _violation_priorities dict for ObjectiveBuilder
                self._violation_variables[violation_name] = violation_var
                self._violation_priorities[violation_name] = request.priority
                self._constraint_count += 2
