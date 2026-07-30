"""Consecutive shift type constraint - bounds runs of the same shift group.

Implements the family of "N nights in a row, then M periods off" rules
common in nurse/physician rostering standards (INRC-II, ANROM): a minimum
and/or maximum number of consecutive periods a worker may spend on the same
shift group (a set of shift type ids and/or categories), plus a mandatory
rest period immediately after a completed run of that group ends.
"""

from typing import TYPE_CHECKING, Any

from ortools.sat.python import cp_model

from shift_solver.constraints._windows import iter_windows
from shift_solver.constraints.base import BaseConstraint, ConstraintConfig
from shift_solver.models import ShiftType, Worker
from shift_solver.utils import get_logger

if TYPE_CHECKING:
    from shift_solver.solver.types import SolverVariables

logger = get_logger("constraints.consecutive_shift_type")


class ConsecutiveShiftTypeConstraint(BaseConstraint):
    """
    Bounds/requires consecutive-period runs of a "shift group" per worker.

    A shift group is defined per rule by a filter of shift_types and/or
    categories (union of both if both given). For each worker, ``in_group``
    is an indicator per period that is true iff the worker is assigned any
    shift in the group that period.

    Each rule may independently configure:
    - ``max_consecutive``: no more than N consecutive periods in the group
      (sliding window of size N+1, bounded above by N).
    - ``min_consecutive``: once a run of the group starts, it must continue
      for at least N periods. Lenient at the horizon boundary: a run that
      starts too close to the end of the schedule to reach N periods is not
      penalized for the periods that don't exist.
    - ``rest_after_run``: after a completed run of the group ends (the
      worker worked the group in period p but not in period p+1), the
      worker must not work ANY shift type (not just the group) for the
      following ``rest_after_run`` periods. Lenient at the horizon
      boundary: rest periods that fall beyond the schedule are exempt, and
      a run that is still active in the very last period of the horizon has
      no defined "end" (whether it continues past the horizon is unknown)
      so no rest is required for it.

    In HARD mode (``config.is_hard=True``), each of the above is enforced
    directly with ``model.add(...)`` and no violation variables are
    created (matching :class:`WorkerShiftLimitConstraint`'s pattern for a
    single-severity constraint -- there is no per-rule hard/soft override,
    so ``handles_hard_mode`` stays False and this constraint simply never
    creates violation vars for a hard config, rather than relying on the
    solver's generic pin-to-zero mechanism).

    In SOFT mode, one violation variable is created per (rule, worker,
    window/period) triple:
    - max_consecutive: an IntVar bounded ``[0, window_size - max_consecutive]``
      that is FORCED >= the window's excess over max_consecutive (a lower
      bound; minimization pushes it down to the exact excess).
    - min_consecutive: a BoolVar FORCED >= "a run started here AND the
      required follow-on period was not worked".
    - rest_after_run: a BoolVar FORCED >= "a run ended here AND the worker
      worked some shift in the required rest period".

    All violation vars are registered directly (not marked "auxiliary")
    since none of them are derived sums of other violation vars.

    Required context:
        - workers: list[Worker] - available workers
        - shift_types: list[ShiftType] - shift types (with .category)
        - num_periods: int - number of scheduling periods

    Config parameters:
        - rules: list[dict] - each dict:
            - rule_id: str - unique label for this rule (used in variable
              names and warnings)
            - shift_types: list[str] | None - shift type ids in the group
            - categories: list[str] | None - shift categories in the group
              (at least one of shift_types/categories must be set; the
              group is the union of both filters)
            - min_consecutive: int | None - minimum run length once started
              (values <= 1 are a no-op: a run of length 1 is always valid)
            - max_consecutive: int | None - maximum allowed run length
            - rest_after_run: int - periods of total rest required
              immediately after a completed run (default: 0, meaning no
              rest requirement)
    """

    constraint_id = "consecutive_shift_type"

    def __init__(
        self,
        model: cp_model.CpModel,
        variables: "SolverVariables",
        config: ConstraintConfig | None = None,
    ) -> None:
        """Initialize consecutive shift type constraint."""
        super().__init__(model, variables, config)
        # Shared across rules within one apply() call: "works any shift"
        # depends on ALL shift types, not a per-rule group, so it is
        # identical for every rule and only needs to be built once per
        # (worker, period).
        self._works_any_cache: dict[tuple[str, int], cp_model.IntVar] = {}

    def apply(self, **context: Any) -> None:
        """
        Apply consecutive shift type rules to the model.

        Args:
            **context: Must include workers, shift_types, num_periods
        """
        if not self.is_enabled:
            return

        workers: list[Worker] = context["workers"]
        shift_types: list[ShiftType] = context["shift_types"]
        num_periods: int = context["num_periods"]

        rules: list[dict[str, Any]] | None = self.config.get_param("rules")

        if not rules:
            logger.warning(
                "consecutive_shift_type constraint is enabled but no 'rules' "
                "parameter was configured; constraint has no effect"
            )
            return

        if num_periods < 1:
            logger.warning(
                "consecutive_shift_type constraint: num_periods=%d; nothing "
                "to constrain",
                num_periods,
            )
            return

        self._works_any_cache = {}

        for rule_idx, rule in enumerate(rules):
            self._apply_rule(rule, rule_idx, workers, shift_types, num_periods)

    def _apply_rule(
        self,
        rule: dict[str, Any],
        rule_idx: int,
        workers: list[Worker],
        shift_types: list[ShiftType],
        num_periods: int,
    ) -> None:
        """Validate and apply a single rule across all workers."""
        rule_id = rule.get("rule_id") or f"rule{rule_idx}"

        shift_type_filter: list[str] | None = rule.get("shift_types")
        category_filter: list[str] | None = rule.get("categories")

        if not shift_type_filter and not category_filter:
            logger.warning(
                "consecutive_shift_type rule '%s': neither shift_types nor "
                "categories filter is set; skipping rule (at least one "
                "filter is required)",
                rule_id,
            )
            return

        group_ids = {
            st.id
            for st in shift_types
            if (shift_type_filter and st.id in shift_type_filter)
            or (category_filter and st.category in category_filter)
        }

        if not group_ids:
            logger.warning(
                "consecutive_shift_type rule '%s': shift_types/categories "
                "filters matched no known shift types; skipping rule",
                rule_id,
            )
            return

        min_consecutive: int | None = rule.get("min_consecutive")
        max_consecutive: int | None = rule.get("max_consecutive")
        rest_after_run: int = rule.get("rest_after_run") or 0

        if max_consecutive is not None and max_consecutive < 0:
            logger.warning(
                "consecutive_shift_type rule '%s': max_consecutive=%d is "
                "negative; ignoring",
                rule_id,
                max_consecutive,
            )
            max_consecutive = None

        if min_consecutive is not None and min_consecutive < 1:
            logger.warning(
                "consecutive_shift_type rule '%s': min_consecutive=%d is "
                "less than 1; ignoring (a run of length 1 is always valid)",
                rule_id,
                min_consecutive,
            )
            min_consecutive = None

        if (
            max_consecutive is None
            and (min_consecutive is None or min_consecutive <= 1)
            and rest_after_run <= 0
        ):
            logger.warning(
                "consecutive_shift_type rule '%s': no effective "
                "min_consecutive, max_consecutive, or rest_after_run; rule "
                "has no effect",
                rule_id,
            )
            return

        for worker in workers:
            in_group = self._build_in_group_indicators(
                rule_id, worker, group_ids, num_periods
            )

            if max_consecutive is not None:
                self._apply_max_consecutive(
                    rule_id, worker, in_group, max_consecutive, num_periods
                )

            if min_consecutive is not None and min_consecutive > 1:
                self._apply_min_consecutive(
                    rule_id, worker, in_group, min_consecutive, num_periods
                )

            if rest_after_run > 0:
                self._apply_rest_after_run(
                    rule_id,
                    worker,
                    in_group,
                    rest_after_run,
                    shift_types,
                    num_periods,
                )

    # -- Indicator construction -------------------------------------------

    def _build_in_group_indicators(
        self,
        rule_id: str,
        worker: Worker,
        group_ids: set[str],
        num_periods: int,
    ) -> list[cp_model.IntVar]:
        """
        Build one "worker is in this rule's shift group" indicator per
        period. A period where no candidate assignment variable exists
        (e.g. the group is entirely restricted for this worker) gets a
        constant-0 indicator rather than being omitted, so downstream
        window/run logic never has to special-case missing periods.
        """
        indicators: list[cp_model.IntVar] = []
        for period in range(num_periods):
            candidate_vars: list[cp_model.IntVar] = []
            for shift_type_id in group_ids:
                try:
                    candidate_vars.append(
                        self.variables.get_assignment_var(
                            worker.id, period, shift_type_id
                        )
                    )
                except KeyError:
                    continue

            indicators.append(
                self._sum_indicator(
                    candidate_vars, f"cst_grp_{rule_id}_{worker.id}_p{period}"
                )
            )

        return indicators

    def _get_works_any(
        self, worker: Worker, period: int, shift_types: list[ShiftType]
    ) -> cp_model.IntVar:
        """Get (and cache) the "worker works some shift" indicator for a
        (worker, period), across ALL shift types -- used by rest_after_run,
        which forbids ANY shift during the rest window, not just the
        rule's group."""
        key = (worker.id, period)
        cached = self._works_any_cache.get(key)
        if cached is not None:
            return cached

        candidate_vars: list[cp_model.IntVar] = []
        for st in shift_types:
            try:
                candidate_vars.append(
                    self.variables.get_assignment_var(worker.id, period, st.id)
                )
            except KeyError:
                continue

        indicator = self._sum_indicator(
            candidate_vars, f"cst_any_{worker.id}_p{period}"
        )
        self._works_any_cache[key] = indicator
        return indicator

    def _sum_indicator(
        self, candidate_vars: list[cp_model.IntVar], name: str
    ) -> cp_model.IntVar:
        """
        Build a BoolVar equal to "sum(candidate_vars) >= 1", or a constant
        0 if there are no candidates. Reuses the single variable directly
        when there is exactly one candidate.
        """
        if not candidate_vars:
            return self.model.new_constant(0)

        if len(candidate_vars) == 1:
            return candidate_vars[0]

        indicator = self.model.new_bool_var(name)
        self.model.add(sum(candidate_vars) >= 1).only_enforce_if(indicator)
        self.model.add(sum(candidate_vars) == 0).only_enforce_if(indicator.negated())
        self._constraint_count += 2
        return indicator

    def _build_run_start(
        self,
        rule_id: str,
        worker: Worker,
        in_group: list[cp_model.IntVar],
        period: int,
    ) -> cp_model.IntVar:
        """run_start[p] = in_group[p] AND (p==0 OR NOT in_group[p-1])."""
        current = in_group[period]
        if period == 0:
            return current

        previous = in_group[period - 1]
        run_start = self.model.new_bool_var(f"cst_rs_{rule_id}_{worker.id}_p{period}")
        self.model.add_bool_and([current, previous.negated()]).only_enforce_if(
            run_start
        )
        self.model.add_bool_or([current.negated(), previous]).only_enforce_if(
            run_start.negated()
        )
        self._constraint_count += 2
        return run_start

    def _build_run_end(
        self,
        rule_id: str,
        worker: Worker,
        in_group: list[cp_model.IntVar],
        period: int,
    ) -> cp_model.IntVar:
        """run_end[p] = in_group[p] AND NOT in_group[p+1]."""
        current = in_group[period]
        nxt = in_group[period + 1]
        run_end = self.model.new_bool_var(f"cst_re_{rule_id}_{worker.id}_p{period}")
        self.model.add_bool_and([current, nxt.negated()]).only_enforce_if(run_end)
        self.model.add_bool_or([current.negated(), nxt]).only_enforce_if(
            run_end.negated()
        )
        self._constraint_count += 2
        return run_end

    # -- Rule application ----------------------------------------------

    def _apply_max_consecutive(
        self,
        rule_id: str,
        worker: Worker,
        in_group: list[cp_model.IntVar],
        max_consecutive: int,
        num_periods: int,
    ) -> None:
        """No more than max_consecutive consecutive periods in the group,
        via a sliding window of size max_consecutive+1 bounded above by
        max_consecutive."""
        window_size = max_consecutive + 1
        context_str = f"consecutive_shift_type[{rule_id}].max_consecutive"

        for window_start, window_end in iter_windows(
            num_periods, window_size, logger=logger, context=context_str
        ):
            window_vars = in_group[window_start:window_end]

            if self.is_hard:
                self.model.add(sum(window_vars) <= max_consecutive)
                self._constraint_count += 1
                continue

            excess_ub = max(0, len(window_vars) - max_consecutive)
            violation_name = f"cst_max_viol_{rule_id}_{worker.id}_w{window_start}"
            violation_var = self.model.new_int_var(0, excess_ub, violation_name)
            self.model.add(violation_var >= sum(window_vars) - max_consecutive)

            self._violation_variables[violation_name] = violation_var
            self._constraint_count += 1

    def _apply_min_consecutive(
        self,
        rule_id: str,
        worker: Worker,
        in_group: list[cp_model.IntVar],
        min_consecutive: int,
        num_periods: int,
    ) -> None:
        """Once a run of the group starts, it must continue for at least
        min_consecutive periods. Lenient at the horizon end: follow-on
        periods that don't exist are exempt rather than making the run
        infeasible/always-violated."""
        for period in range(num_periods):
            run_start = self._build_run_start(rule_id, worker, in_group, period)

            for k in range(1, min_consecutive):
                target = period + k
                if target >= num_periods:
                    break  # lenient: horizon ends before the run could complete

                if self.is_hard:
                    self.model.add(in_group[target] == 1).only_enforce_if(run_start)
                    self._constraint_count += 1
                    continue

                violation_name = f"cst_min_viol_{rule_id}_{worker.id}_p{period}_k{k}"
                violation_var = self.model.new_bool_var(violation_name)
                self.model.add(violation_var >= run_start - in_group[target])

                self._violation_variables[violation_name] = violation_var
                self._constraint_count += 1

    def _apply_rest_after_run(
        self,
        rule_id: str,
        worker: Worker,
        in_group: list[cp_model.IntVar],
        rest_after_run: int,
        shift_types: list[ShiftType],
        num_periods: int,
    ) -> None:
        """After a completed run of the group ends at period p (worked at p,
        not worked at p+1), the worker must not work ANY shift type for the
        following rest_after_run periods. Lenient at the horizon end: rest
        periods beyond the schedule are exempt, and a run still active in
        the last period has no defined end (unknown whether it continues
        past the horizon) so no rest is required."""
        for period in range(num_periods - 1):
            run_end = self._build_run_end(rule_id, worker, in_group, period)

            for k in range(1, rest_after_run + 1):
                target = period + k
                if target >= num_periods:
                    break  # lenient: horizon ends before this rest period exists

                works_any = self._get_works_any(worker, target, shift_types)

                if self.is_hard:
                    self.model.add(works_any == 0).only_enforce_if(run_end)
                    self._constraint_count += 1
                    continue

                violation_name = f"cst_rest_viol_{rule_id}_{worker.id}_p{period}_k{k}"
                violation_var = self.model.new_bool_var(violation_name)
                self.model.add(violation_var >= run_end + works_any - 1)

                self._violation_variables[violation_name] = violation_var
                self._constraint_count += 1
