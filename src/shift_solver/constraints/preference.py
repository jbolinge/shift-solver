"""Preference constraint - honors worker preferred shifts and preferred/required
availability windows."""

from datetime import date
from typing import TYPE_CHECKING, Any

from ortools.sat.python import cp_model

from shift_solver.constraints import _windows
from shift_solver.constraints.base import BaseConstraint, ConstraintConfig
from shift_solver.models import Availability, ShiftType, Worker
from shift_solver.utils import get_logger

if TYPE_CHECKING:
    from shift_solver.solver.types import SolverVariables

logger = get_logger("constraints.preference")


class PreferenceConstraint(BaseConstraint):
    """
    Preference constraint - a soft constraint with one hard sub-rule.

    Resurrects three data channels that would otherwise be inert:

    (a) ``Worker.preferred_shifts`` - for every worker with a non-empty
        ``preferred_shifts`` set, any assignment to a shift type NOT in
        that set is penalized.
    (b) ``Availability`` records with ``availability_type="preferred"`` -
        the worker not being assigned to any of the (optionally
        shift-type-restricted) candidate shifts anywhere in the window is
        penalized once per record.
    (c) ``Availability`` records with ``availability_type="required"`` -
        always enforced as a HARD constraint (independent of
        ``config.is_hard``) when ``honor_required_availability`` is True:
        the worker must be assigned at least one of the candidate shifts
        somewhere in the window. If a "required" window overlaps zero
        scheduling periods, or has zero valid candidate assignment
        variables (e.g. an unmatched ``shift_type_id``), it is logged and
        skipped rather than making the whole model infeasible -- callers
        are responsible for ensuring required windows correspond to real
        capacity, or the schedule may silently under-deliver on that
        requirement.

    Required context:
        - workers: list[Worker] - available workers
        - shift_types: list[ShiftType] - shift types
        - num_periods: int - number of scheduling periods
        - availabilities: list[Availability] - availability records
        - period_dates: list[tuple[date, date]] - (start, end) for each period

    Config parameters:
        - worker_preferred_weight: int = 1 - priority multiplier for
            violation variables from sub-rule (a) (assignments outside a
            worker's non-empty preferred_shifts set).
        - availability_preferred_weight: int = 1 - priority multiplier for
            violation variables from sub-rule (b) ("preferred" availability
            windows in which the worker ends up not working).
        - honor_required_availability: bool = True - whether sub-rule (c)
            ("required" availability windows) is enforced at all. When
            False, "required" records are ignored entirely by this
            constraint.

    Hard mode (``config.is_hard=True``): this constraint sets
    ``handles_hard_mode = True`` because sub-rule (c) is unconditionally
    hard while (a)/(b) are governed by ``config.is_hard``. When
    ``config.is_hard`` is True, the violation variables created for (a)
    and (b) are pinned to 0 directly (``model.add(viol == 0)``), which
    forces the corresponding assignments/coverage the same way the
    solver's generic soft->hard enforcement would -- but done here so that
    generic enforcement does not also try to pin (c)'s hard constraint (a
    plain ``>= 1``, not a violation variable).
    """

    constraint_id = "preference"

    handles_hard_mode = True

    def __init__(
        self,
        model: cp_model.CpModel,
        variables: "SolverVariables",
        config: ConstraintConfig | None = None,
    ) -> None:
        """Initialize preference constraint."""
        super().__init__(model, variables, config)

    def apply(self, **context: Any) -> None:
        """
        Apply preference constraints to the model.

        Args:
            **context: Must include workers, shift_types, num_periods,
                      availabilities, period_dates
        """
        if not self.is_enabled:
            return

        workers: list[Worker] = context["workers"]
        shift_types: list[ShiftType] = context["shift_types"]
        num_periods: int = context["num_periods"]
        availabilities: list[Availability] = context.get("availabilities", [])
        period_dates: list[tuple[date, date]] = context["period_dates"]

        worker_preferred_weight = self._get_int_param("worker_preferred_weight", 1)
        availability_preferred_weight = self._get_int_param(
            "availability_preferred_weight", 1
        )
        honor_required_availability = self._get_bool_param(
            "honor_required_availability", True
        )

        self._apply_worker_preferred_shifts(
            workers, shift_types, num_periods, worker_preferred_weight
        )
        self._apply_availability_records(
            workers,
            shift_types,
            num_periods,
            availabilities,
            period_dates,
            availability_preferred_weight,
            honor_required_availability,
        )

    def _get_int_param(self, key: str, default: int) -> int:
        """Read an int param, treating an explicit None value as absent."""
        value = self.config.get_param(key, default)
        return default if value is None else value

    def _get_bool_param(self, key: str, default: bool) -> bool:
        """Read a bool param, treating an explicit None value as absent."""
        value = self.config.get_param(key, default)
        return default if value is None else value

    # -- Sub-rule (a): Worker.preferred_shifts -----------------------------

    def _apply_worker_preferred_shifts(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        num_periods: int,
        worker_preferred_weight: int,
    ) -> None:
        """
        Penalize assignments outside a worker's non-empty preferred_shifts.

        For every worker with a non-empty ``preferred_shifts`` set, for
        every period and every shift type NOT in that set, registers a
        violation BoolVar tied to the assignment var via
        ``model.add(viol == x)`` -- so pinning ``viol == 0`` (hard mode)
        directly forbids the non-preferred assignment.
        """
        workers_with_preferences = [w for w in workers if w.preferred_shifts]
        if not workers_with_preferences:
            return

        for worker in workers_with_preferences:
            non_preferred_shifts = [
                st for st in shift_types if st.id not in worker.preferred_shifts
            ]
            for shift_type in non_preferred_shifts:
                for period in range(num_periods):
                    try:
                        assignment_var = self.variables.get_assignment_var(
                            worker.id, period, shift_type.id
                        )
                    except KeyError:
                        continue

                    violation_name = (
                        f"pref_worker_viol_{worker.id}_{shift_type.id}_p{period}"
                    )
                    violation_var = self.model.new_bool_var(violation_name)
                    self.model.add(violation_var == assignment_var)
                    self._constraint_count += 1

                    if self.is_hard:
                        self.model.add(violation_var == 0)
                        self._constraint_count += 1
                        continue

                    self._violation_variables[violation_name] = violation_var
                    self._violation_priorities[violation_name] = worker_preferred_weight

    # -- Sub-rules (b) and (c): Availability records ------------------------

    def _apply_availability_records(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        num_periods: int,
        availabilities: list[Availability],
        period_dates: list[tuple[date, date]],
        availability_preferred_weight: int,
        honor_required_availability: bool,
    ) -> None:
        """Process "preferred" and "required" availability records."""
        if not availabilities:
            return

        valid_worker_ids = {w.id for w in workers}
        valid_shift_ids = {st.id for st in shift_types}

        for idx, availability in enumerate(availabilities):
            if availability.availability_type not in ("preferred", "required"):
                continue

            if availability.worker_id not in valid_worker_ids:
                logger.warning(
                    "preference constraint: skipping availability record %d: "
                    "unknown worker_id '%s'",
                    idx,
                    availability.worker_id,
                )
                continue

            if (
                availability.shift_type_id is not None
                and availability.shift_type_id not in valid_shift_ids
            ):
                logger.warning(
                    "preference constraint: skipping availability record %d: "
                    "unknown shift_type_id '%s'",
                    idx,
                    availability.shift_type_id,
                )
                continue

            if availability.availability_type == "required" and (
                not honor_required_availability
            ):
                continue

            applicable_periods = self._find_applicable_periods(
                availability, period_dates, num_periods
            )
            if not applicable_periods:
                logger.warning(
                    "preference constraint: %s availability record %d for "
                    "worker '%s' overlaps zero scheduling periods; skipping",
                    availability.availability_type,
                    idx,
                    availability.worker_id,
                )
                continue

            candidate_shift_types = (
                [st for st in shift_types if st.id == availability.shift_type_id]
                if availability.shift_type_id is not None
                else shift_types
            )

            window_vars = []
            for period in applicable_periods:
                for shift_type in candidate_shift_types:
                    try:
                        window_vars.append(
                            self.variables.get_assignment_var(
                                availability.worker_id, period, shift_type.id
                            )
                        )
                    except KeyError:
                        continue

            if not window_vars:
                logger.warning(
                    "preference constraint: %s availability record %d for "
                    "worker '%s' has no valid candidate assignment "
                    "variables; skipping",
                    availability.availability_type,
                    idx,
                    availability.worker_id,
                )
                continue

            if availability.availability_type == "required":
                self.model.add(sum(window_vars) >= 1)
                self._constraint_count += 1
                continue

            # "preferred"
            violation_name = f"pref_avail_viol_{availability.worker_id}_r{idx}"
            has_assignment_name = f"pref_avail_has_{availability.worker_id}_r{idx}"
            violation_var = _windows.build_absence_violation(
                self.model,
                window_vars,
                violation_name,
                has_assignment_name,
                logger=logger,
                context="preference constraint",
            )
            if violation_var is None:
                continue
            self._constraint_count += 3

            if self.is_hard:
                self.model.add(violation_var == 0)
                self._constraint_count += 1
                continue

            self._violation_variables[violation_name] = violation_var
            self._violation_priorities[violation_name] = availability_preferred_weight

    def _find_applicable_periods(
        self,
        availability: Availability,
        period_dates: list[tuple[date, date]],
        num_periods: int,
    ) -> list[int]:
        """Find which periods overlap with the availability record's dates."""
        applicable = []
        for period_idx in range(num_periods):
            if period_idx < len(period_dates):
                period_start, period_end = period_dates[period_idx]
                if (
                    availability.start_date <= period_end
                    and availability.end_date >= period_start
                ):
                    applicable.append(period_idx)
        return applicable
