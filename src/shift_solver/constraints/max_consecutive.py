"""Max consecutive constraint - caps (and optionally floors) run lengths of
consecutive working periods."""

from typing import TYPE_CHECKING, Any

from ortools.sat.python import cp_model

from shift_solver.constraints import _windows
from shift_solver.constraints.base import BaseConstraint, ConstraintConfig
from shift_solver.models import ShiftType, Worker
from shift_solver.utils import get_logger

if TYPE_CHECKING:
    from shift_solver.solver.types import SolverVariables

logger = get_logger("constraints.max_consecutive")


class MaxConsecutiveConstraint(BaseConstraint):
    """
    Soft constraint capping (and optionally flooring) how many periods in a
    row a worker may be assigned "working" shifts.

    "Working" means assigned to any of the filtered shift types/categories
    in a period -- one boolean indicator per (worker, period) is derived
    from the underlying assignment variables and reused by both halves of
    this constraint:

    - **Max run length** (``max_consecutive_periods``): for every sliding
      window of ``max_consecutive_periods + 1`` consecutive periods, an
      ``excess`` violation variable is bounded below by how far the count
      of working periods in that window exceeds ``max_consecutive_periods``
      (``excess >= sum(window) - max_consecutive_periods``, ``excess >= 0``).
      A window of a worker being "on" for the entire window sets
      ``excess`` no lower than 1, which is exactly the failure signal for
      "more than max_consecutive_periods in a row" once every period in the
      window is worked. If the configured window would exceed the
      schedule horizon, :func:`shift_solver.constraints._windows.iter_windows`
      clamps it to the full horizon; since that only happens when
      ``max_consecutive_periods >= num_periods``, the resulting window is
      never restrictive (the sum of working periods can never exceed
      ``num_periods <= max_consecutive_periods``), so this is a safe no-op,
      not a silently-wrong constraint.

    - **Min run length** (``min_consecutive_periods``): a run-start
      indicator ``start[w, p]`` is true iff the worker starts working at
      period ``p`` (working at ``p``, and either ``p`` is the first period
      or the worker was not working at ``p - 1``). For every period offset
      ``k`` in ``1 .. min_consecutive_periods - 1`` such that ``p + k`` is
      still inside the horizon, a violation variable is bounded below by
      ``start[w, p] - works[w, p + k]``, i.e. it must go true if the run
      starting at ``p`` does not continue working through ``p + k``.

      **Boundary policy**: runs that start too close to the end of the
      horizon to ever reach ``min_consecutive_periods`` (i.e. any ``k``
      with ``p + k >= num_periods``) are exempt for that offset -- there is
      no way to know or require what would have happened past the
      scheduling horizon, so a run truncated by the end of the schedule is
      never penalized for being "too short". This is the standard,
      lenient rostering convention (a shift assignment run is allowed to
      be cut short by the edge of the published schedule).

    Both violation kinds use a lower-bound (``>=``) encoding so that
    ``ShiftSolver``'s generic hard-mode enforcement (forcing every
    non-auxiliary violation variable to 0 when this constraint's
    ``is_hard`` is True) is sufficient to make the constraint hard: forcing
    ``excess == 0`` forces ``sum(window) <= max_consecutive_periods``, and
    forcing every min-run violation to 0 forces ``works[w, p + k] == 1``
    whenever a run starts at ``p``. No per-record hard/soft handling is
    needed, so ``handles_hard_mode`` stays at its default of False.

    Required context:
        - workers: list[Worker] - available workers
        - shift_types: list[ShiftType] - shift types
        - num_periods: int - number of scheduling periods

    Config parameters:
        - max_consecutive_periods: int | None - maximum number of
            consecutive "working" periods allowed before a violation is
            recorded (default: None, meaning no cap)
        - min_consecutive_periods: int | None - minimum run length a
            "working" streak must reach once started, subject to the
            boundary policy above (default: None, meaning no floor)
            At least one of max_consecutive_periods/min_consecutive_periods
            must be set, else this constraint warns and does nothing.
            Values of min_consecutive_periods <= 1 are degenerate (every
            run of length >= 1 already satisfies them) and are silently
            treated as "no floor" -- not an error.
        - shift_types: list[str] | None - if set, only these shift type ids
            count towards "working" (default: None, no filter)
        - categories: list[str] | None - if set, only shift types in these
            categories count towards "working" (default: None, no filter)
            When both shift_types and categories are set, a shift type must
            match BOTH to count (AND semantics, not OR).
    """

    constraint_id = "max_consecutive"

    def __init__(
        self,
        model: cp_model.CpModel,
        variables: "SolverVariables",
        config: ConstraintConfig | None = None,
    ) -> None:
        """Initialize max consecutive constraint."""
        # Default config handled by BaseConstraint
        # Registry provides config when instantiated via solver
        super().__init__(model, variables, config)

    def apply(self, **context: Any) -> None:
        """
        Apply max/min consecutive-period constraints to the model.

        Args:
            **context: Must include workers, shift_types, num_periods
        """
        if not self.is_enabled:
            return

        workers: list[Worker] = context["workers"]
        shift_types: list[ShiftType] = context["shift_types"]
        num_periods: int = context["num_periods"]

        max_consecutive_periods: int | None = self.config.get_param(
            "max_consecutive_periods"
        )
        min_consecutive_periods: int | None = self.config.get_param(
            "min_consecutive_periods"
        )

        if max_consecutive_periods is None and min_consecutive_periods is None:
            logger.warning(
                "max_consecutive constraint: neither max_consecutive_periods "
                "nor min_consecutive_periods is configured; nothing to "
                "constrain"
            )
            return

        if not workers or num_periods <= 0:
            logger.warning(
                "max_consecutive constraint: no workers (%d) or no periods "
                "(%d); nothing to constrain",
                len(workers),
                num_periods,
            )
            return

        # Get target filters
        target_shift_types: list[str] | None = self.config.get_param("shift_types")
        target_categories: list[str] | None = self.config.get_param("categories")

        filtered_shifts = [
            st
            for st in shift_types
            if (target_shift_types is None or st.id in target_shift_types)
            and (target_categories is None or st.category in target_categories)
        ]

        if not filtered_shifts:
            logger.warning(
                "max_consecutive constraint: no shift types match configured "
                "shift_types=%s / categories=%s filters; nothing to "
                "constrain",
                target_shift_types,
                target_categories,
            )
            return

        # Build the per-(worker, period) "working" indicator once, shared
        # by both the max-run and min-run halves below.
        works: dict[str, dict[int, cp_model.IntVar]] = {}
        for worker in workers:
            works[worker.id] = {}
            for period in range(num_periods):
                period_vars = [
                    self.variables.get_assignment_var(worker.id, period, st.id)
                    for st in filtered_shifts
                ]
                works_var = self.model.new_bool_var(
                    f"maxcon_works_{worker.id}_p{period}"
                )
                self.model.add_max_equality(works_var, period_vars)
                self._constraint_count += 1
                works[worker.id][period] = works_var

        if max_consecutive_periods is not None:
            self._apply_max_run(workers, num_periods, works, max_consecutive_periods)

        if min_consecutive_periods is not None and min_consecutive_periods > 1:
            self._apply_min_run(workers, num_periods, works, min_consecutive_periods)

    def _apply_max_run(
        self,
        workers: list[Worker],
        num_periods: int,
        works: dict[str, dict[int, cp_model.IntVar]],
        max_consecutive_periods: int,
    ) -> None:
        """
        Bound the number of consecutive "working" periods to at most
        max_consecutive_periods, using one excess violation variable per
        (worker, sliding window of max_consecutive_periods + 1 periods).
        """
        window_size = max_consecutive_periods + 1
        excess_count = 0

        for worker in workers:
            for window_start, window_end in _windows.iter_windows(
                num_periods,
                window_size,
                logger=logger,
                context="max_consecutive constraint (max_consecutive_periods)",
            ):
                window_works = [
                    works[worker.id][p] for p in range(window_start, window_end)
                ]
                excess_name = f"maxcon_excess_{worker.id}_w{window_start}"
                excess_var = self.model.new_int_var(0, len(window_works), excess_name)
                # excess >= sum(window) - max_consecutive_periods (and >= 0),
                # driven to its tightest feasible value by hard-mode pinning
                # or by the objective in soft mode.
                self.model.add(
                    excess_var >= sum(window_works) - max_consecutive_periods
                )
                self._constraint_count += 1
                self._violation_variables[excess_name] = excess_var
                excess_count += 1

        # Debug aggregate, excluded from the objective (auxiliary): a
        # derived sum of the maxcon_excess_* variables above, not an
        # independent penalty.
        if excess_count > 0:
            total_var = self.model.new_int_var(
                0, excess_count * num_periods, "maxcon_total_excess"
            )
            excess_vars = [
                v
                for k, v in self._violation_variables.items()
                if k.startswith("maxcon_excess_")
            ]
            self.model.add(total_var == sum(excess_vars))
            self._violation_variables["total_max"] = total_var
            self._violation_variable_types["total_max"] = "auxiliary"

    def _apply_min_run(
        self,
        workers: list[Worker],
        num_periods: int,
        works: dict[str, dict[int, cp_model.IntVar]],
        min_consecutive_periods: int,
    ) -> None:
        """
        Once a "working" run starts, penalize it not continuing for at
        least min_consecutive_periods periods -- except for runs that start
        too close to the end of the horizon to ever reach that length (see
        the boundary policy documented on the class).
        """
        viol_count = 0

        for worker in workers:
            worker_works = works[worker.id]
            for p in range(num_periods):
                start_var = self._build_start_indicator(worker.id, p, worker_works)

                for k in range(1, min_consecutive_periods):
                    if p + k >= num_periods:
                        # Boundary policy: run is truncated by the horizon
                        # end, exempt from this offset's requirement.
                        continue

                    viol_name = f"maxcon_minrun_viol_{worker.id}_p{p}_k{k}"
                    viol_var = self.model.new_bool_var(viol_name)
                    # viol >= start[w,p] - works[w,p+k] (and >= 0): forces
                    # works[w,p+k] == 1 whenever start[w,p] == 1 and viol is
                    # pinned to 0 (hard mode).
                    self.model.add(viol_var >= start_var - worker_works[p + k])
                    self._constraint_count += 1
                    self._violation_variables[viol_name] = viol_var
                    viol_count += 1

        # Debug aggregate, excluded from the objective (auxiliary): a
        # derived sum of the maxcon_minrun_viol_* variables above, not an
        # independent penalty.
        if viol_count > 0:
            total_var = self.model.new_int_var(
                0, viol_count, "maxcon_total_minrun_violations"
            )
            viol_vars = [
                v
                for k, v in self._violation_variables.items()
                if k.startswith("maxcon_minrun_viol_")
            ]
            self.model.add(total_var == sum(viol_vars))
            self._violation_variables["total_min"] = total_var
            self._violation_variable_types["total_min"] = "auxiliary"

    def _build_start_indicator(
        self,
        worker_id: str,
        period: int,
        worker_works: dict[int, cp_model.IntVar],
    ) -> cp_model.IntVar:
        """
        Return a BoolVar true iff a "working" run starts at ``period`` for
        this worker: working at ``period``, and either ``period == 0`` or
        not working at ``period - 1``.

        For period 0 the works indicator itself already has these exact
        semantics (there is no period -1 to compare against), so it is
        reused directly instead of creating a redundant variable.
        """
        if period == 0:
            return worker_works[0]

        start_name = f"maxcon_start_{worker_id}_p{period}"
        start_var = self.model.new_bool_var(start_name)
        current = worker_works[period]
        previous = worker_works[period - 1]

        # start = current AND NOT previous
        self.model.add_bool_and([current, previous.negated()]).only_enforce_if(
            start_var
        )
        self.model.add_bool_or([current.negated(), previous]).only_enforce_if(
            start_var.negated()
        )
        self._constraint_count += 2

        return start_var
