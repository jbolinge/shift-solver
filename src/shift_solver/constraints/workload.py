"""Workload constraint - bounds worker workload over the horizon or in
rolling windows, by shift count or by hours."""

from typing import TYPE_CHECKING, Any

from ortools.sat.python import cp_model

from shift_solver.constraints import _windows
from shift_solver.constraints.base import BaseConstraint, ConstraintConfig
from shift_solver.models import ShiftType, Worker
from shift_solver.utils import get_logger

if TYPE_CHECKING:
    from shift_solver.solver.types import SolverVariables

logger = get_logger("constraints.workload")


class WorkloadConstraint(BaseConstraint):
    """
    Soft constraint bounding each worker's total workload, either over the
    whole horizon or over every rolling window of a configured size, in
    either shift-count or hour units, optionally restricted to a subset of
    shift types/categories.

    For every worker (and, when ``window_periods`` is set, every sliding
    window of that many periods) a total variable is built as the
    coefficient-weighted sum of that worker's assignment variables for the
    filtered shift types in that span. ``unit="shifts"`` uses a coefficient
    of 1 per assignment (so the total is a shift count, matching the
    original behavior of this constraint exactly when no window/filters are
    configured). ``unit="hours"`` uses each shift type's
    ``duration_hours`` scaled to integer minutes
    (``round(duration_hours * 60)``) as the coefficient, so CP-SAT stays in
    integer arithmetic; bounds given in ``min_total_hours``/
    ``max_total_hours`` are scaled the same way for comparison.

    Shortfall and excess are tracked as separate integer violation amounts
    (per worker, or per worker+window) so ObjectiveBuilder can weight them
    by how far under/over the bound the total is. In hard mode, the generic
    is_hard enforcement in ShiftSolver forces every non-auxiliary violation
    variable to zero, which pins each total into the configured range.

    Backward compatibility: with the defaults ``unit="shifts"`` and
    ``window_periods=None`` (and no shift_types/categories filters), this
    constraint behaves identically to the pre-upgrade version -- one
    "total_{worker_id}" / "shortfall_{worker_id}" / "excess_{worker_id}"
    triple per worker, bounded by min_total_shifts/max_total_shifts across
    the whole horizon.

    Required context:
        - workers: list[Worker] - available workers
        - shift_types: list[ShiftType] - shift types
        - num_periods: int - number of scheduling periods

    Config parameters:
        - unit: "shifts" | "hours" - what a "1" in the total means
            (default: "shifts")
        - window_periods: int | None - if set, apply min/max to every
            rolling window of this many consecutive periods instead of the
            whole horizon (default: None, whole horizon)
        - shift_types: list[str] | None - if set, only count assignments to
            these shift type ids (default: all shift types)
        - categories: list[str] | None - if set, only count assignments to
            shift types in these categories (default: all categories).
            Combines with shift_types via AND when both are set.
        - min_total_shifts: int - minimum shifts a worker should be
            assigned in-scope, used when unit="shifts" (default: 0)
        - max_total_shifts: int | None - maximum shifts a worker should be
            assigned in-scope, used when unit="shifts" (default: None,
            unbounded)
        - min_total_hours: float | None - minimum hours a worker should be
            assigned in-scope, used when unit="hours" (default: None, no
            minimum)
        - max_total_hours: float | None - maximum hours a worker should be
            assigned in-scope, used when unit="hours" (default: None,
            unbounded)
    """

    constraint_id = "workload"

    def __init__(
        self,
        model: cp_model.CpModel,
        variables: "SolverVariables",
        config: ConstraintConfig | None = None,
    ) -> None:
        """Initialize workload constraint."""
        super().__init__(model, variables, config)

    def apply(self, **context: Any) -> None:
        """
        Apply per-worker (optionally per-window) workload bounds to the
        model.

        Creates a total variable per worker (or per worker+window, when
        window_periods is set) -- auxiliary, not penalized directly --
        plus shortfall/excess violation variables measuring how far the
        total strays outside the configured [min, max] bound.

        Args:
            **context: Must include workers, shift_types, num_periods
        """
        if not self.is_enabled:
            return

        workers: list[Worker] = context["workers"]
        shift_types: list[ShiftType] = context["shift_types"]
        num_periods: int = context["num_periods"]

        if not workers or not shift_types:
            return

        unit: str = self.config.get_param("unit", "shifts")
        if unit not in ("shifts", "hours"):
            logger.warning(
                "workload constraint: unknown unit=%r (expected 'shifts' or "
                "'hours'); defaulting to 'shifts'",
                unit,
            )
            unit = "shifts"

        shift_type_filter: list[str] | None = self.config.get_param("shift_types")
        category_filter: list[str] | None = self.config.get_param("categories")

        filtered_shifts = [
            st
            for st in shift_types
            if (shift_type_filter is None or st.id in shift_type_filter)
            and (category_filter is None or st.category in category_filter)
        ]

        if not filtered_shifts:
            logger.warning(
                "workload constraint: shift_types/categories filters "
                "(shift_types=%r, categories=%r) matched no shift types; "
                "constraint has no effect",
                shift_type_filter,
                category_filter,
            )
            return

        min_total_shifts: int = self.config.get_param("min_total_shifts", 0)
        max_total_shifts: int | None = self.config.get_param("max_total_shifts")
        min_total_hours: float | None = self.config.get_param("min_total_hours")
        max_total_hours: float | None = self.config.get_param("max_total_hours")

        if unit == "hours":
            if min_total_shifts or max_total_shifts is not None:
                logger.warning(
                    "workload constraint: unit='hours' but "
                    "min_total_shifts/max_total_shifts were also set; "
                    "those are ignored (use min_total_hours/max_total_hours)",
                )
            coefficients = {
                st.id: round(st.duration_hours * 60) for st in filtered_shifts
            }
            min_bound = (
                round(min_total_hours * 60) if min_total_hours is not None else 0
            )
            max_bound = (
                round(max_total_hours * 60) if max_total_hours is not None else None
            )
        else:
            if min_total_hours is not None or max_total_hours is not None:
                logger.warning(
                    "workload constraint: unit='shifts' but "
                    "min_total_hours/max_total_hours were also set; those "
                    "are ignored (use min_total_shifts/max_total_shifts)",
                )
            coefficients = {st.id: 1 for st in filtered_shifts}
            min_bound = min_total_shifts
            max_bound = max_total_shifts

        sum_coef = sum(coefficients.values())

        window_periods: int | None = self.config.get_param("window_periods")
        if window_periods is None:
            windows: list[tuple[int, int]] = [(0, num_periods)]
            windowed = False
        else:
            windows = list(
                _windows.iter_windows(
                    num_periods,
                    window_periods,
                    logger=logger,
                    context="workload constraint",
                )
            )
            windowed = True

        for worker in workers:
            for window_start, window_end in windows:
                window_len = window_end - window_start
                max_possible = window_len * sum_coef

                term_vars: list[tuple[int, cp_model.IntVar]] = []
                for period in range(window_start, window_end):
                    for st in filtered_shifts:
                        try:
                            var = self.variables.get_assignment_var(
                                worker.id, period, st.id
                            )
                        except KeyError:
                            continue
                        term_vars.append((coefficients[st.id], var))

                suffix = f"_w{window_start}" if windowed else ""

                total_name = f"total_{worker.id}{suffix}"
                total_var = self.model.new_int_var(
                    0, max_possible, f"workload_{total_name}"
                )
                if term_vars:
                    self.model.add(
                        total_var == sum(coef * var for coef, var in term_vars)
                    )
                else:
                    self.model.add(total_var == 0)
                self._constraint_count += 1

                # Auxiliary total - not itself a penalty, excluded from
                # objective.
                self._violation_variables[total_name] = total_var
                self._violation_variable_types[total_name] = "auxiliary"

                if min_bound > 0:
                    shortfall_name = f"shortfall_{worker.id}{suffix}"
                    shortfall_var = self.model.new_int_var(
                        0, min_bound, f"workload_{shortfall_name}"
                    )
                    # shortfall >= min_bound - total (and >= 0), minimized
                    # to its tightest feasible value by the
                    # objective/hard mode.
                    self.model.add(shortfall_var >= min_bound - total_var)
                    self._constraint_count += 1
                    self._violation_variables[shortfall_name] = shortfall_var

                if max_bound is not None:
                    excess_name = f"excess_{worker.id}{suffix}"
                    excess_var = self.model.new_int_var(
                        0, max_possible, f"workload_{excess_name}"
                    )
                    # excess >= total - max_bound (and >= 0)
                    self.model.add(excess_var >= total_var - max_bound)
                    self._constraint_count += 1
                    self._violation_variables[excess_name] = excess_var
