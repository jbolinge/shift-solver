"""Shift order preference constraint - encourages specific shift transitions."""

from datetime import date
from typing import TYPE_CHECKING, Any

from ortools.sat.python import cp_model

from shift_solver.constraints.base import BaseConstraint, ConstraintConfig
from shift_solver.models import Availability, ShiftOrderPreference, ShiftType, Worker

if TYPE_CHECKING:
    from shift_solver.solver.types import SolverVariables


class ShiftOrderPreferenceConstraint(BaseConstraint):
    """
    Soft constraint encouraging preferred shift transitions between adjacent periods.

    Supports three trigger types:
    - shift_type: triggered when worker works a specific shift type
    - category: triggered when worker works any shift in a category
    - unavailability: triggered when worker is unavailable in a period

    And two directions:
    - after: prefer a shift/category at N+1 when trigger fires at N
    - before: prefer a shift/category at N when trigger fires at N+1

    Required context:
        - workers: list[Worker]
        - shift_types: list[ShiftType]
        - num_periods: int
        - period_dates: list[tuple[date, date]]
        - availabilities: list[Availability]
        - shift_order_preferences: list[ShiftOrderPreference]
    """

    constraint_id = "shift_order_preference"

    def __init__(
        self,
        model: cp_model.CpModel,
        variables: "SolverVariables",
        config: ConstraintConfig | None = None,
    ) -> None:
        """Initialize shift order preference constraint."""
        super().__init__(model, variables, config)

    def apply(self, **context: Any) -> None:
        """
        Apply shift order preference constraint to the model.

        Args:
            **context: Must include workers, shift_types, num_periods,
                       period_dates, availabilities, shift_order_preferences
        """
        if not self.is_enabled:
            return

        workers: list[Worker] = context["workers"]
        shift_types: list[ShiftType] = context["shift_types"]
        num_periods: int = context["num_periods"]
        period_dates: list[tuple[date, date]] = context["period_dates"]
        availabilities: list[Availability] = context.get("availabilities", [])
        preferences: list[ShiftOrderPreference] = context.get(
            "shift_order_preferences", []
        )

        if not preferences or num_periods < 2:
            return

        # Build lookups
        shift_type_map = {st.id: st for st in shift_types}
        shifts_by_category: dict[str, list[ShiftType]] = {}
        for st in shift_types:
            if st.category not in shifts_by_category:
                shifts_by_category[st.category] = []
            shifts_by_category[st.category].append(st)

        # Build unavailability index: worker_id -> set of period indices
        unavail_index: dict[str, set[int]] = {}
        for avail in availabilities:
            if avail.availability_type != "unavailable":
                continue
            if avail.worker_id not in unavail_index:
                unavail_index[avail.worker_id] = set()
            for period_idx in range(num_periods):
                p_start, p_end = period_dates[period_idx]
                if avail.start_date <= p_end and avail.end_date >= p_start:
                    unavail_index[avail.worker_id].add(period_idx)

        for rule in preferences:
            self._apply_rule(
                rule=rule,
                workers=workers,
                shift_type_map=shift_type_map,
                shifts_by_category=shifts_by_category,
                unavail_index=unavail_index,
                num_periods=num_periods,
            )

    def _apply_rule(
        self,
        rule: ShiftOrderPreference,
        workers: list[Worker],
        shift_type_map: dict[str, ShiftType],
        shifts_by_category: dict[str, list[ShiftType]],
        unavail_index: dict[str, set[int]],
        num_periods: int,
    ) -> None:
        """Apply a single shift order preference rule."""
        # Validate trigger exists
        if (
            rule.trigger_type == "shift_type" and rule.trigger_value not in shift_type_map
        ) or (
            rule.trigger_type == "category"
            and rule.trigger_value not in shifts_by_category
        ):
            return

        # Validate preferred exists
        if (
            rule.preferred_type == "shift_type"
            and rule.preferred_value not in shift_type_map
        ) or (
            rule.preferred_type == "category"
            and rule.preferred_value not in shifts_by_category
        ):
            return

        for worker in workers:
            # Apply worker_ids filter
            if rule.worker_ids is not None and worker.id not in rule.worker_ids:
                continue

            self._apply_rule_for_worker(
                rule=rule,
                worker=worker,
                shifts_by_category=shifts_by_category,
                unavail_index=unavail_index,
                num_periods=num_periods,
            )

    def _apply_rule_for_worker(
        self,
        rule: ShiftOrderPreference,
        worker: Worker,
        shifts_by_category: dict[str, list[ShiftType]],
        unavail_index: dict[str, set[int]],
        num_periods: int,
    ) -> None:
        """Apply rule for a single worker across adjacent period pairs."""
        for period in range(num_periods - 1):
            if rule.direction == "after":
                trigger_period = period
                preferred_period = period + 1
            else:  # before
                preferred_period = period
                trigger_period = period + 1

            self._create_violation_for_pair(
                rule=rule,
                worker=worker,
                trigger_period=trigger_period,
                preferred_period=preferred_period,
                shifts_by_category=shifts_by_category,
                unavail_index=unavail_index,
            )

    def _create_violation_for_pair(
        self,
        rule: ShiftOrderPreference,
        worker: Worker,
        trigger_period: int,
        preferred_period: int,
        shifts_by_category: dict[str, list[ShiftType]],
        unavail_index: dict[str, set[int]],
    ) -> None:
        """Create a violation variable for a single (trigger, preferred) pair."""
        # Build trigger indicator
        trigger_met = self._get_trigger_indicator(
            rule=rule,
            worker=worker,
            period=trigger_period,
            shifts_by_category=shifts_by_category,
            unavail_index=unavail_index,
        )

        if trigger_met is None:
            return  # Skip - trigger not applicable

        # Build preferred indicator
        preferred_met = self._get_preferred_indicator(
            rule=rule,
            worker=worker,
            period=preferred_period,
            shifts_by_category=shifts_by_category,
        )

        if preferred_met is None:
            return  # Skip - worker can't work preferred shift

        violation_name = (
            f"sop_viol_{worker.id}_{rule.rule_id}_p{trigger_period}"
        )

        if isinstance(trigger_met, bool):
            # Constant trigger (unavailability) - trigger is always true for this pair
            # violation = NOT preferred_met
            violation_var = self.model.new_bool_var(violation_name)
            self.model.add(violation_var == preferred_met.negated())
            self._constraint_count += 1
        else:
            # Variable trigger - violation = trigger AND NOT preferred
            violation_var = self.model.new_bool_var(violation_name)
            self.model.add_bool_and(
                [trigger_met, preferred_met.negated()]
            ).only_enforce_if(violation_var)
            self.model.add_bool_or(
                [trigger_met.negated(), preferred_met]
            ).only_enforce_if(violation_var.negated())
            self._constraint_count += 2

        self._violation_variables[violation_name] = violation_var
        self._violation_priorities[violation_name] = rule.priority

    def _get_trigger_indicator(
        self,
        rule: ShiftOrderPreference,
        worker: Worker,
        period: int,
        shifts_by_category: dict[str, list[ShiftType]],
        unavail_index: dict[str, set[int]],
    ) -> cp_model.IntVar | bool | None:
        """
        Get the trigger indicator for a rule/worker/period.

        Returns:
            - IntVar: a boolean variable for shift_type/category triggers
            - True: constant for unavailability triggers when worker is unavailable
            - None: skip this pair (trigger doesn't apply)
        """
        if rule.trigger_type == "shift_type":
            assert rule.trigger_value is not None
            try:
                return self.variables.get_assignment_var(
                    worker.id, period, rule.trigger_value
                )
            except KeyError:
                return None

        elif rule.trigger_type == "category":
            assert rule.trigger_value is not None
            category_shifts = shifts_by_category.get(rule.trigger_value, [])
            if not category_shifts:
                return None

            cat_vars: list[cp_model.IntVar] = []
            for st in category_shifts:
                try:
                    var = self.variables.get_assignment_var(worker.id, period, st.id)
                    cat_vars.append(var)
                except KeyError:
                    continue

            if not cat_vars:
                return None

            indicator = self.model.new_bool_var(
                f"sop_trig_{worker.id}_{rule.rule_id}_p{period}"
            )
            self.model.add(sum(cat_vars) >= 1).only_enforce_if(indicator)
            self.model.add(sum(cat_vars) == 0).only_enforce_if(indicator.negated())
            self._constraint_count += 2
            return indicator

        else:  # unavailability
            worker_unavail = unavail_index.get(worker.id, set())
            if period in worker_unavail:
                return True  # Constant: trigger is always met
            return None  # Not unavailable -> skip

    def _get_preferred_indicator(
        self,
        rule: ShiftOrderPreference,
        worker: Worker,
        period: int,
        shifts_by_category: dict[str, list[ShiftType]],
    ) -> cp_model.IntVar | None:
        """
        Get the preferred indicator for a rule/worker/period.

        Returns:
            - IntVar: a boolean variable indicating preferred shift is assigned
            - None: worker can't work any preferred shifts (skip this pair)
        """
        if rule.preferred_type == "shift_type":
            if not worker.can_work_shift(rule.preferred_value):
                return None
            try:
                return self.variables.get_assignment_var(
                    worker.id, period, rule.preferred_value
                )
            except KeyError:
                return None

        else:  # category
            category_shifts = shifts_by_category.get(rule.preferred_value, [])
            if not category_shifts:
                return None

            cat_vars: list[cp_model.IntVar] = []
            for st in category_shifts:
                if not worker.can_work_shift(st.id):
                    continue
                try:
                    var = self.variables.get_assignment_var(worker.id, period, st.id)
                    cat_vars.append(var)
                except KeyError:
                    continue

            if not cat_vars:
                return None

            indicator = self.model.new_bool_var(
                f"sop_pref_{worker.id}_{rule.rule_id}_p{period}"
            )
            self.model.add(sum(cat_vars) >= 1).only_enforce_if(indicator)
            self.model.add(sum(cat_vars) == 0).only_enforce_if(indicator.negated())
            self._constraint_count += 2
            return indicator
