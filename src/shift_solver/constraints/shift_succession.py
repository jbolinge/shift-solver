"""Shift succession constraint - forbids/penalizes shift-type transitions."""

from typing import TYPE_CHECKING, Any

from ortools.sat.python import cp_model

from shift_solver.constraints.base import BaseConstraint, ConstraintConfig
from shift_solver.models import ShiftType, Worker
from shift_solver.utils import get_logger

if TYPE_CHECKING:
    from shift_solver.solver.types import SolverVariables

logger = get_logger("constraints.shift_succession")

_FILTER_TYPES = ("shift_type", "category")


class ShiftSuccessionConstraint(BaseConstraint):
    """
    Forbids or penalizes specific shift-type transitions between periods.

    Each rule defines a "from" filter (a shift type or a whole category) and
    a "to" filter, plus a ``gap_periods`` offset. For every worker and every
    period ``p`` where ``p + gap_periods < num_periods``, the rule fires if
    the worker is assigned to a shift matching the "from" filter at period
    ``p`` AND a shift matching the "to" filter at period ``p + gap_periods``.
    This generalizes the common "no early shift after a night shift" rule to
    arbitrary shift-type/category pairs and arbitrary gaps.

    Each rule has its own hard/soft override (``is_hard``); when a rule's
    ``is_hard`` is ``None`` it inherits the constraint-level
    ``config.is_hard``. Because hard/soft is decided per rule, this
    constraint enforces hard rules itself (``handles_hard_mode = True``)
    rather than relying on the solver's generic soft-violation pinning.

    This constraint supersedes :class:`~shift_solver.constraints.sequence.SequenceConstraint`
    for the "no two consecutive same-category shifts" special case (a
    same-category rule with ``from_type=to_type="category"``,
    ``from_value=to_value=<category>``, ``gap_periods=1`` reproduces it with
    per-rule hard/soft control). ``SequenceConstraint`` itself is untouched;
    callers who want the richer per-rule semantics should configure a
    ``shift_succession`` rule instead of (or in addition to) ``sequence``.

    Required context:
        - workers: list[Worker] - available workers
        - shift_types: list[ShiftType] - shift types with categories
        - num_periods: int - number of scheduling periods

    Config parameters:
        - rules: list[dict] - succession rules. Each dict has:
            - rule_id: str - unique identifier for the rule (required; used
              to build unique CP-SAT variable names, so rules missing it
              are skipped)
            - from_type: "shift_type" | "category" - filter kind for the
              "from" (earlier) side
            - from_value: str - shift type id or category name to match on
              the "from" side
            - to_type: "shift_type" | "category" - filter kind for the "to"
              (later) side
            - to_value: str - shift type id or category name to match on
              the "to" side
            - is_hard: bool | None - per-rule hard/soft override; ``None``
              (default) inherits ``config.is_hard``
            - priority: int - penalty multiplier for soft violations
              (default 1)
            - gap_periods: int - number of periods between the "from" and
              "to" side (default 1; must be ``>= 1`` and ``< num_periods``)

    Rules are skipped (with a warning) when: the rule is not a dict, when
    ``rule_id`` is missing/empty, when ``from_type``/``to_type`` is not one
    of "shift_type"/"category", when ``from_value``/``to_value`` references
    an unknown shift type id or category, or when ``gap_periods`` is
    ``< 1`` or ``>= num_periods``.
    """

    constraint_id = "shift_succession"

    # Hard/soft is decided per rule (rule.is_hard overrides config.is_hard),
    # so the solver's generic soft->hard enforcement (forcing every
    # violation var to 0 when config.is_hard is True) must not also run on
    # top of the per-rule enforcement done in apply().
    handles_hard_mode = True

    def __init__(
        self,
        model: cp_model.CpModel,
        variables: "SolverVariables",
        config: ConstraintConfig | None = None,
    ) -> None:
        """Initialize shift succession constraint."""
        super().__init__(model, variables, config)

    def apply(self, **context: Any) -> None:
        """
        Apply shift succession constraint to the model.

        Args:
            **context: Must include workers, shift_types, num_periods
        """
        if not self.is_enabled:
            return

        workers: list[Worker] = context["workers"]
        shift_types: list[ShiftType] = context["shift_types"]
        num_periods: int = context["num_periods"]

        rules: list[Any] | None = self.config.get_param("rules")
        if not rules:
            logger.warning(
                "shift_succession constraint enabled but no rules configured; "
                "constraint has no effect"
            )
            return

        if num_periods < 2:
            logger.warning(
                "shift_succession constraint: num_periods=%d is too small for "
                "any from/to transition (need at least 2); constraint has no "
                "effect",
                num_periods,
            )
            return

        shift_type_map: dict[str, ShiftType] = {st.id: st for st in shift_types}
        shifts_by_category: dict[str, list[ShiftType]] = {}
        for st in shift_types:
            shifts_by_category.setdefault(st.category, []).append(st)

        for rule_idx, rule in enumerate(rules):
            self._apply_rule(
                rule=rule,
                rule_idx=rule_idx,
                workers=workers,
                shift_type_map=shift_type_map,
                shifts_by_category=shifts_by_category,
                num_periods=num_periods,
            )

    def _resolve_filter_ids(
        self,
        filter_type: str,
        filter_value: str,
        shift_type_map: dict[str, ShiftType],
        shifts_by_category: dict[str, list[ShiftType]],
    ) -> list[str] | None:
        """
        Resolve a from/to filter to a list of candidate shift type ids.

        Returns None if the filter references an unknown shift type or
        category.
        """
        if filter_type == "shift_type":
            if filter_value not in shift_type_map:
                return None
            return [filter_value]

        # filter_type == "category"
        category_shifts = shifts_by_category.get(filter_value)
        if not category_shifts:
            return None
        return [st.id for st in category_shifts]

    def _apply_rule(
        self,
        rule: Any,
        rule_idx: int,
        workers: list[Worker],
        shift_type_map: dict[str, ShiftType],
        shifts_by_category: dict[str, list[ShiftType]],
        num_periods: int,
    ) -> None:
        """Validate and apply a single succession rule across all workers."""
        if not isinstance(rule, dict):
            logger.warning(
                "shift_succession: skipping rule at index %d: expected a dict, got %s",
                rule_idx,
                type(rule).__name__,
            )
            return

        rule_id = rule.get("rule_id")
        if not rule_id:
            logger.warning(
                "shift_succession: skipping rule at index %d: missing/empty rule_id",
                rule_idx,
            )
            return

        from_type = rule.get("from_type")
        to_type = rule.get("to_type")
        if from_type not in _FILTER_TYPES or to_type not in _FILTER_TYPES:
            logger.warning(
                "shift_succession rule '%s': from_type/to_type must be one of "
                "%s, got from_type=%r, to_type=%r; skipping rule",
                rule_id,
                _FILTER_TYPES,
                from_type,
                to_type,
            )
            return

        from_value = rule.get("from_value")
        to_value = rule.get("to_value")
        if not isinstance(from_value, str) or not isinstance(to_value, str):
            logger.warning(
                "shift_succession rule '%s': from_value/to_value must be "
                "strings, got from_value=%r, to_value=%r; skipping rule",
                rule_id,
                from_value,
                to_value,
            )
            return

        from_shift_ids = self._resolve_filter_ids(
            from_type, from_value, shift_type_map, shifts_by_category
        )
        if from_shift_ids is None:
            logger.warning(
                "shift_succession rule '%s': from_value %r is not a known "
                "%s; skipping rule",
                rule_id,
                from_value,
                from_type,
            )
            return

        to_shift_ids = self._resolve_filter_ids(
            to_type, to_value, shift_type_map, shifts_by_category
        )
        if to_shift_ids is None:
            logger.warning(
                "shift_succession rule '%s': to_value %r is not a known %s; "
                "skipping rule",
                rule_id,
                to_value,
                to_type,
            )
            return

        gap_periods = rule.get("gap_periods", 1)
        if not isinstance(gap_periods, int) or gap_periods < 1:
            logger.warning(
                "shift_succession rule '%s': gap_periods must be an integer "
                ">= 1, got %r; skipping rule",
                rule_id,
                gap_periods,
            )
            return
        if gap_periods >= num_periods:
            logger.warning(
                "shift_succession rule '%s': gap_periods=%d exceeds/equals "
                "horizon of num_periods=%d; skipping rule",
                rule_id,
                gap_periods,
                num_periods,
            )
            return

        rule_is_hard_raw = rule.get("is_hard")
        rule_is_hard = (
            rule_is_hard_raw if rule_is_hard_raw is not None else self.is_hard
        )
        priority = rule.get("priority", 1)

        for worker in workers:
            for period in range(num_periods - gap_periods):
                next_period = period + gap_periods
                self._apply_rule_for_worker_period(
                    rule_id=rule_id,
                    worker=worker,
                    period=period,
                    next_period=next_period,
                    from_shift_ids=from_shift_ids,
                    to_shift_ids=to_shift_ids,
                    rule_is_hard=rule_is_hard,
                    priority=priority,
                )

    def _apply_rule_for_worker_period(
        self,
        rule_id: str,
        worker: Worker,
        period: int,
        next_period: int,
        from_shift_ids: list[str],
        to_shift_ids: list[str],
        rule_is_hard: bool,
        priority: int,
    ) -> None:
        """Build the from/to indicators and the hard/soft record for one pair."""
        from_vars: list[cp_model.IntVar] = []
        for sid in from_shift_ids:
            try:
                from_vars.append(
                    self.variables.get_assignment_var(worker.id, period, sid)
                )
            except KeyError:
                continue

        to_vars: list[cp_model.IntVar] = []
        for sid in to_shift_ids:
            try:
                to_vars.append(
                    self.variables.get_assignment_var(worker.id, next_period, sid)
                )
            except KeyError:
                continue

        if not from_vars or not to_vars:
            # No assignment variables exist for this worker/period/filter
            # combination (e.g. none of the candidate shift types apply that
            # day) -- a soft, expected no-op, not worth warning per pair.
            return

        from_ind = self.model.new_bool_var(f"succ_from_{worker.id}_{rule_id}_p{period}")
        self.model.add(sum(from_vars) >= 1).only_enforce_if(from_ind)
        self.model.add(sum(from_vars) == 0).only_enforce_if(from_ind.negated())

        to_ind = self.model.new_bool_var(
            f"succ_to_{worker.id}_{rule_id}_p{next_period}"
        )
        self.model.add(sum(to_vars) >= 1).only_enforce_if(to_ind)
        self.model.add(sum(to_vars) == 0).only_enforce_if(to_ind.negated())

        self._constraint_count += 4

        if rule_is_hard:
            self.model.add(from_ind + to_ind <= 1)
            self._constraint_count += 1
            return

        violation_name = f"succ_viol_{worker.id}_{rule_id}_p{period}"
        violation_var = self.model.new_bool_var(violation_name)
        self.model.add(violation_var >= from_ind + to_ind - 1)
        self._constraint_count += 1

        self._violation_variables[violation_name] = violation_var
        self._violation_priorities[violation_name] = priority
