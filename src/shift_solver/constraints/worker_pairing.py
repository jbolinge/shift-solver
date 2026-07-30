"""Worker pairing constraint - keeps two workers apart or together."""

from typing import TYPE_CHECKING, Any

from ortools.sat.python import cp_model

from shift_solver.constraints.base import BaseConstraint, ConstraintConfig
from shift_solver.models import ShiftType, Worker
from shift_solver.utils import get_logger

if TYPE_CHECKING:
    from shift_solver.solver.types import SolverVariables

logger = get_logger("constraints.worker_pairing")

_RULE_TYPES = ("together", "apart")


class WorkerPairingConstraint(BaseConstraint):
    """
    Keeps two named workers apart (never on the same shift) or together
    (one is a "tutor"/backup who must be present whenever the other works).

    Each rule names an ordered pair ``worker_a``/``worker_b`` and a
    ``type``:

    - ``"apart"``: for every period and every shift type in the rule's
      scope, worker_a and worker_b must not (hard) / should not (soft)
      both be assigned that shift in that period.
      Hard: ``x[a,p,s] + x[b,p,s] <= 1``.
      Soft: a violation variable with ``viol >= x[a,p,s] + x[b,p,s] - 1``.

    - ``"together"`` (tutorship): for every period, worker_b must (hard) /
      should (soft) be assigned *some* shift in the rule's scope whenever
      worker_a is assigned *some* shift in that scope. Presence is tracked
      per worker per period via a bidirectional boolean indicator
      (``works_x[p]`` true iff the worker has >=1 assignment among the
      scope's shift types that period).
      Hard: ``works_b[p] >= works_a[p]``.
      Soft: a violation variable with ``viol >= works_a[p] - works_b[p]``.

    Hard/soft is decided per rule (``rule["is_hard"]`` overrides
    ``config.is_hard`` when not ``None``), so this constraint enforces hard
    rules itself (``handles_hard_mode = True``) rather than relying on the
    solver's generic soft-violation pinning.

    Required context:
        - workers: list[Worker] - available workers
        - shift_types: list[ShiftType] - shift types
        - num_periods: int - number of scheduling periods

    Config parameters:
        - rules: list[dict] - pairing rules. Each dict has:
            - rule_id: str - unique identifier (required; used to build
              unique CP-SAT variable names, so rules missing it are
              skipped)
            - type: "together" | "apart"
            - worker_a: str - must reference a known worker
            - worker_b: str - must reference a known worker
            - shift_types: list[str] | None - candidate shift types for
              this rule's scope. ``None`` (default) = all shift types.
              For "apart" this is the same-shift conflict scope (checked
              shift-by-shift); for "together" it is the set of shifts that
              count as "worker_a/worker_b is working" that period.
            - is_hard: bool | None - per-rule hard/soft override; ``None``
              (default) inherits ``config.is_hard``
            - priority: int - penalty multiplier for soft violations
              (default 1)

    Rules are skipped (with a warning) when: the rule is not a dict, when
    ``rule_id`` is missing/empty, when ``type`` is not "together"/"apart",
    when ``worker_a``/``worker_b`` references an unknown worker id or the
    pair is degenerate (``worker_a == worker_b``), or when the ``shift_types``
    scope (after dropping unknown ids) is empty.
    """

    constraint_id = "worker_pairing"

    # Hard/soft is decided per rule (rule["is_hard"] overrides
    # config.is_hard), so the solver's generic soft->hard enforcement
    # (forcing every violation var to 0 when config.is_hard is True) must
    # not also run on top of the per-rule enforcement done in apply().
    handles_hard_mode = True

    def __init__(
        self,
        model: cp_model.CpModel,
        variables: "SolverVariables",
        config: ConstraintConfig | None = None,
    ) -> None:
        """Initialize worker pairing constraint."""
        super().__init__(model, variables, config)

    def apply(self, **context: Any) -> None:
        """
        Apply worker pairing constraints to the model.

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
                "worker_pairing constraint enabled but no rules configured; "
                "constraint has no effect"
            )
            return

        valid_worker_ids = {w.id for w in workers}
        all_shift_ids = [st.id for st in shift_types]

        for rule_idx, rule in enumerate(rules):
            self._apply_rule(
                rule=rule,
                rule_idx=rule_idx,
                valid_worker_ids=valid_worker_ids,
                all_shift_ids=all_shift_ids,
                num_periods=num_periods,
            )

    def _resolve_scope(
        self, rule_id: str, shift_types_param: Any, all_shift_ids: list[str]
    ) -> list[str] | None:
        """
        Resolve a rule's ``shift_types`` scope parameter to a concrete list
        of shift type ids.

        ``None`` means "all shift types". A provided list has unknown ids
        dropped (with a warning). Returns ``None`` (signaling "skip the
        rule") only if the resulting scope is empty.
        """
        if shift_types_param is None:
            scope = list(all_shift_ids)
        else:
            valid_shift_ids = set(all_shift_ids)
            scope = [s for s in shift_types_param if s in valid_shift_ids]
            unknown = [s for s in shift_types_param if s not in valid_shift_ids]
            if unknown:
                logger.warning(
                    "worker_pairing rule '%s': dropping unknown shift_types "
                    "%r from scope",
                    rule_id,
                    unknown,
                )

        if not scope:
            logger.warning(
                "worker_pairing rule '%s': shift_types scope is empty after "
                "validation; skipping rule",
                rule_id,
            )
            return None

        return scope

    def _apply_rule(
        self,
        rule: Any,
        rule_idx: int,
        valid_worker_ids: set[str],
        all_shift_ids: list[str],
        num_periods: int,
    ) -> None:
        """Validate and apply a single pairing rule across all periods."""
        if not isinstance(rule, dict):
            logger.warning(
                "worker_pairing: skipping rule at index %d: expected a dict, got %s",
                rule_idx,
                type(rule).__name__,
            )
            return

        rule_id = rule.get("rule_id")
        if not rule_id:
            logger.warning(
                "worker_pairing: skipping rule at index %d: missing/empty rule_id",
                rule_idx,
            )
            return

        rule_type = rule.get("type")
        if rule_type not in _RULE_TYPES:
            logger.warning(
                "worker_pairing rule '%s': type must be one of %s, got %r; "
                "skipping rule",
                rule_id,
                _RULE_TYPES,
                rule_type,
            )
            return

        worker_a = rule.get("worker_a")
        worker_b = rule.get("worker_b")
        if worker_a not in valid_worker_ids:
            logger.warning(
                "worker_pairing rule '%s': unknown worker_a %r; skipping rule",
                rule_id,
                worker_a,
            )
            return
        if worker_b not in valid_worker_ids:
            logger.warning(
                "worker_pairing rule '%s': unknown worker_b %r; skipping rule",
                rule_id,
                worker_b,
            )
            return
        if worker_a == worker_b:
            logger.warning(
                "worker_pairing rule '%s': worker_a and worker_b are both "
                "%r; skipping rule",
                rule_id,
                worker_a,
            )
            return

        scope = self._resolve_scope(rule_id, rule.get("shift_types"), all_shift_ids)
        if scope is None:
            return

        rule_is_hard_raw = rule.get("is_hard")
        rule_is_hard = (
            rule_is_hard_raw if rule_is_hard_raw is not None else self.is_hard
        )
        priority = rule.get("priority", 1)

        if rule_type == "apart":
            self._apply_apart_rule(
                rule_id, worker_a, worker_b, scope, num_periods, rule_is_hard, priority
            )
        else:
            self._apply_together_rule(
                rule_id, worker_a, worker_b, scope, num_periods, rule_is_hard, priority
            )

    def _apply_apart_rule(
        self,
        rule_id: str,
        worker_a: str,
        worker_b: str,
        scope: list[str],
        num_periods: int,
        rule_is_hard: bool,
        priority: int,
    ) -> None:
        """Apply an "apart" rule: a/b must not share the same shift+period."""
        for period in range(num_periods):
            for shift_type_id in scope:
                try:
                    var_a = self.variables.get_assignment_var(
                        worker_a, period, shift_type_id
                    )
                    var_b = self.variables.get_assignment_var(
                        worker_b, period, shift_type_id
                    )
                except KeyError:
                    # No assignment variable for one of the workers/shift
                    # this period (e.g. shift not applicable that day) --
                    # nothing to conflict on.
                    continue

                if rule_is_hard:
                    self.model.add(var_a + var_b <= 1)
                    self._constraint_count += 1
                    continue

                violation_name = (
                    f"pairing_apart_viol_{rule_id}_{shift_type_id}_p{period}"
                )
                violation_var = self.model.new_bool_var(violation_name)
                self.model.add(violation_var >= var_a + var_b - 1)
                self._constraint_count += 1

                self._violation_variables[violation_name] = violation_var
                self._violation_priorities[violation_name] = priority

    def _apply_together_rule(
        self,
        rule_id: str,
        worker_a: str,
        worker_b: str,
        scope: list[str],
        num_periods: int,
        rule_is_hard: bool,
        priority: int,
    ) -> None:
        """Apply a "together" rule: b must be present whenever a works."""
        for period in range(num_periods):
            works_a = self._presence_indicator(worker_a, period, scope, rule_id, "a")
            works_b = self._presence_indicator(worker_b, period, scope, rule_id, "b")

            if works_a is None or works_b is None:
                # Neither worker has any candidate assignment variable this
                # period (e.g. no scope shift applies that day) -- nothing
                # to require presence for.
                continue

            if rule_is_hard:
                self.model.add(works_b >= works_a)
                self._constraint_count += 1
                continue

            violation_name = f"pairing_together_viol_{rule_id}_p{period}"
            violation_var = self.model.new_bool_var(violation_name)
            self.model.add(violation_var >= works_a - works_b)
            self._constraint_count += 1

            self._violation_variables[violation_name] = violation_var
            self._violation_priorities[violation_name] = priority

    def _presence_indicator(
        self,
        worker_id: str,
        period: int,
        scope: list[str],
        rule_id: str,
        tag: str,
    ) -> cp_model.IntVar | None:
        """
        Build (or return) a bidirectional boolean indicator that is true
        iff ``worker_id`` has >=1 assignment among ``scope`` at ``period``.

        Returns ``None`` if no assignment variables exist for this
        worker/period/scope combination.
        """
        candidate_vars: list[cp_model.IntVar] = []
        for shift_type_id in scope:
            try:
                candidate_vars.append(
                    self.variables.get_assignment_var(worker_id, period, shift_type_id)
                )
            except KeyError:
                continue

        if not candidate_vars:
            return None

        indicator = self.model.new_bool_var(
            f"pairing_works_{tag}_{rule_id}_{worker_id}_p{period}"
        )
        self.model.add(sum(candidate_vars) >= 1).only_enforce_if(indicator)
        self.model.add(sum(candidate_vars) == 0).only_enforce_if(indicator.negated())
        self._constraint_count += 2

        return indicator
