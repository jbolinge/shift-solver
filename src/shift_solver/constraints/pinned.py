"""Pinned assignment constraint - forces specific assignment values."""

from typing import TYPE_CHECKING, Any

from ortools.sat.python import cp_model

from shift_solver.constraints.base import BaseConstraint, ConstraintConfig
from shift_solver.models import ShiftType, Worker
from shift_solver.utils import get_logger

if TYPE_CHECKING:
    from shift_solver.solver.types import SolverVariables

logger = get_logger("constraints.pinned")


class PinnedAssignmentConstraint(BaseConstraint):
    """
    Hard constraint forcing specific worker/period/shift assignments.

    This is the engine hook for republishing a schedule without disturbing
    already-published periods, and for rolling re-solves in general: the
    caller supplies the exact assignment values that must hold (both
    "must work" and "must not work" pins), and this constraint pins those
    assignment variables directly, leaving every other assignment free for
    the solver to optimize.

    Each pin is forced with ``model.add(x == value)`` and also passed to
    ``model.add_hint`` so CP-SAT can warm-start its search from the pinned
    solution instead of rediscovering it -- this matters for rolling
    re-solves where most of the schedule is unchanged from the prior solve.

    This constraint has no soft-mode semantics: a pin is either applied or
    it is skipped as invalid. It does not create violation variables and is
    always enforced when enabled, regardless of ``config.is_hard``.

    Required context:
        - workers: list[Worker] - available workers
        - shift_types: list[ShiftType] - shift types
        - num_periods: int - number of scheduling periods

    Config parameters:
        - assignments: list[dict] - pins to apply. Each dict has:
            - worker_id: str - must reference a known worker
            - period_index: int - must be in range [0, num_periods)
            - shift_type_id: str - must reference a known shift type
            - value: int - 1 = worker must work this shift/period,
              0 = worker must not work this shift/period

    Records referencing an unknown worker_id/shift_type_id, an
    out-of-range period_index, or a value other than 0/1 are skipped with
    a warning (not an error) -- this keeps a stale pin (e.g. referencing a
    shift type removed from config) from crashing a re-solve.
    """

    constraint_id = "pinned"

    def __init__(
        self,
        model: cp_model.CpModel,
        variables: "SolverVariables",
        config: ConstraintConfig | None = None,
    ) -> None:
        """Initialize pinned assignment constraint."""
        super().__init__(model, variables, config)

    def apply(self, **context: Any) -> None:
        """
        Apply pinned assignment constraints to the model.

        Args:
            **context: Must include workers, shift_types, num_periods
        """
        if not self.is_enabled:
            return

        workers: list[Worker] = context["workers"]
        shift_types: list[ShiftType] = context["shift_types"]
        num_periods: int = context["num_periods"]

        assignments: list[Any] | None = self.config.get_param("assignments")
        if not assignments:
            logger.warning(
                "pinned constraint enabled but no assignments configured; "
                "constraint has no effect"
            )
            return

        valid_worker_ids = {w.id for w in workers}
        valid_shift_ids = {st.id for st in shift_types}

        for idx, record in enumerate(assignments):
            self._apply_pin(
                record=record,
                idx=idx,
                valid_worker_ids=valid_worker_ids,
                valid_shift_ids=valid_shift_ids,
                num_periods=num_periods,
            )

    def _apply_pin(
        self,
        record: Any,
        idx: int,
        valid_worker_ids: set[str],
        valid_shift_ids: set[str],
        num_periods: int,
    ) -> None:
        """Validate and apply a single pinned-assignment record."""
        if not isinstance(record, dict):
            logger.warning(
                "pinned: skipping assignment at index %d: expected a dict, got %s",
                idx,
                type(record).__name__,
            )
            return

        worker_id = record.get("worker_id")
        period_index = record.get("period_index")
        shift_type_id = record.get("shift_type_id")
        value = record.get("value")

        if worker_id not in valid_worker_ids:
            logger.warning(
                "pinned: skipping assignment at index %d: unknown worker_id %r",
                idx,
                worker_id,
            )
            return

        if shift_type_id not in valid_shift_ids:
            logger.warning(
                "pinned: skipping assignment at index %d: unknown shift_type_id %r",
                idx,
                shift_type_id,
            )
            return

        if (
            not isinstance(period_index, int)
            or isinstance(period_index, bool)
            or not (0 <= period_index < num_periods)
        ):
            logger.warning(
                "pinned: skipping assignment at index %d: period_index %r "
                "out of range [0, %d)",
                idx,
                period_index,
                num_periods,
            )
            return

        if value not in (0, 1):
            logger.warning(
                "pinned: skipping assignment at index %d: value must be 0 or 1, got %r",
                idx,
                value,
            )
            return

        try:
            assignment_var = self.variables.get_assignment_var(
                worker_id, period_index, shift_type_id
            )
        except KeyError:
            logger.warning(
                "pinned: skipping assignment at index %d: no assignment "
                "variable for worker_id=%s, period_index=%d, "
                "shift_type_id=%s",
                idx,
                worker_id,
                period_index,
                shift_type_id,
            )
            return

        self.model.add(assignment_var == value)
        self.model.add_hint(assignment_var, value)
        self._constraint_count += 1
