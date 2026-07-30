"""Minimum rest constraint - enforces minimum rest hours between shifts."""

from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING, Any

from ortools.sat.python import cp_model

from shift_solver.constraints.base import BaseConstraint, ConstraintConfig
from shift_solver.models import ShiftType, Worker
from shift_solver.utils import get_logger

if TYPE_CHECKING:
    from shift_solver.solver.types import SolverVariables

logger = get_logger("constraints.min_rest")

# Arbitrary fixed anchor date used only to compute time-of-day gaps for
# same-period pairs, where the actual calendar date is irrelevant (the gap
# only depends on wall-clock start/end times, never a real date).
_TIME_OF_DAY_ANCHOR = date(2000, 1, 3)  # a Monday; the weekday is irrelevant


def _shift_interval(
    shift_type: ShiftType, anchor_day: date
) -> tuple[datetime, datetime]:
    """
    Compute the wall-clock (start, end) datetime interval for a shift type
    anchored on ``anchor_day``.

    A shift whose end_time is <= its start_time is treated as an overnight
    shift that wraps into the calendar day after ``anchor_day``.
    """
    start_dt = datetime.combine(anchor_day, shift_type.start_time)
    if shift_type.end_time <= shift_type.start_time:
        end_dt = datetime.combine(anchor_day + timedelta(days=1), shift_type.end_time)
    else:
        end_dt = datetime.combine(anchor_day, shift_type.end_time)
    return start_dt, end_dt


def _rest_gap_hours(
    a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime
) -> float:
    """
    Return the rest gap (in hours) between two shift intervals.

    Positive means the intervals don't overlap, with that many hours
    separating them (regardless of which interval comes first). Negative
    means the intervals overlap, with the magnitude equal to the overlap
    duration -- this always registers as a violation against any
    non-negative min_rest_hours threshold.
    """
    if b_start >= a_end:
        return (b_start - a_end).total_seconds() / 3600.0
    if a_start >= b_end:
        return (a_start - b_end).total_seconds() / 3600.0
    overlap = min(a_end, b_end) - max(a_start, b_start)
    return -(overlap.total_seconds() / 3600.0)


class MinRestConstraint(BaseConstraint):
    """
    Minimum rest hours between shifts (the "clopening" rule).

    Forbids (hard) or penalizes (soft) a worker being assigned to two
    shifts whose combined wall-clock schedule leaves less than
    ``min_rest_hours`` of rest between them. Two cases are handled:

    1. **Same-period pairs** -- when BOTH periods involved are single-day
       periods (``period_start == period_end``), any two *different*
       shift types assigned to the same worker in the SAME period are
       checked for overlap/insufficient gap using their wall-clock
       start/end times on that calendar day. Overnight shifts
       (``end_time <= start_time``) are treated as wrapping into the next
       calendar day.

       Multi-day periods are NOT checked for same-period pairs: a single
       assignment variable represents the whole period, and this
       constraint has no way to know which day(s) within a multi-day
       period a shift instance actually falls on, so no meaningful
       same-period rest check can be constructed. Only the adjacent-period
       boundary check below applies to (and is sufficient for) multi-day
       periods.

    2. **Adjacent-period pairs** -- for every pair of ADJACENT periods
       (p, p+1), every ordered combination of shift type `a` (assignable
       in period p) and shift type `b` (assignable in period p+1) --
       including a == b -- is checked using the actual calendar dates
       from `period_dates`: `a`'s interval is anchored on the LAST day of
       period p, `b`'s interval is anchored on the FIRST day of period
       p+1. The gap is always computed from the real dates, never assumed
       -- periods that happen to have a multi-day calendar gap between
       them will correctly produce no violation once that gap already
       exceeds min_rest_hours.

       This also correctly covers multi-day periods: the only day pairing
       that can possibly straddle a period boundary is period p's last day
       against period p+1's first day -- every other day pairing inside a
       multi-day period is further apart in time and cannot produce a
       *tighter* rest gap than the boundary days.

       Only ADJACENT periods (index p and p+1) are checked; periods
       further apart are assumed to have enough calendar separation
       already (at least one full period width) that a rest violation
       cannot occur. This matches conventional daily/weekly scheduling
       horizons and is a documented simplification, not a universal
       guarantee for exotic period layouts.

    Encoding: for every conflicting pair, a single violation BoolVar `v`
    is created with `model.add(v >= x_a + x_b - 1)` (one-directional --
    relies on the objective's minimization pressure, or on the generic
    hard-mode pinning below, to drive `v` down to its true value; it is
    never forced to 0 by this constraint itself). When this constraint's
    config is hard, `ShiftSolver`'s generic soft->hard enforcement pins
    every one of these violation vars to 0, which -- given the `>=`
    direction -- forces `x_a + x_b <= 1`, exactly the desired hard
    encoding. This constraint therefore does NOT set
    ``handles_hard_mode`` and does not branch on ``self.is_hard`` itself.

    Required context:
        - workers: list[Worker] - available workers
        - shift_types: list[ShiftType] - shift types with start/end times
        - num_periods: int - number of scheduling periods
        - period_dates: list[tuple[date, date]] - (start, end) for each
          period. REQUIRED -- if missing (or empty), a warning is logged
          and the constraint is skipped entirely, since no rest gap can be
          computed without real calendar dates.

    Config parameters:
        - min_rest_hours: float - minimum required rest, in hours, between
          two shifts (default: 11.0, per common EU working-time norms)
        - shift_types: list[str] | None - if set, only shift types in this
          list are subject to the rule (BOTH shifts in a checked pair must
          be in this set); default None = all shift types are subject
        - per_worker_overrides: dict[str, float] | None - per-worker
          override of min_rest_hours, keyed by worker_id; workers not
          present in this mapping use `min_rest_hours`
    """

    constraint_id = "min_rest"

    def __init__(
        self,
        model: cp_model.CpModel,
        variables: "SolverVariables",
        config: ConstraintConfig | None = None,
    ) -> None:
        """Initialize min rest constraint."""
        # Default config handled by BaseConstraint
        # Registry provides config when instantiated via solver
        super().__init__(model, variables, config)

    def apply(self, **context: Any) -> None:
        """
        Apply minimum rest constraints to the model.

        Creates one violation BoolVar per (worker, conflicting shift pair)
        -- see the class docstring for the two kinds of pairs considered
        and the hard/soft encoding.

        Args:
            **context: Must include workers, shift_types, num_periods,
                period_dates.
        """
        if not self.is_enabled:
            return

        workers: list[Worker] = context["workers"]
        shift_types: list[ShiftType] = context["shift_types"]
        num_periods: int = context["num_periods"]
        period_dates: list[tuple[date, date]] | None = context.get("period_dates")

        if not period_dates:
            logger.warning(
                "min_rest constraint: period_dates missing from context; "
                "cannot compute rest gaps without calendar dates, skipping"
            )
            return

        if num_periods < 1:
            logger.warning(
                "min_rest constraint: num_periods=%d, nothing to check",
                num_periods,
            )
            return

        default_min_rest_hours: float = self.config.get_param("min_rest_hours", 11.0)
        target_shift_type_ids: list[str] | None = self.config.get_param("shift_types")
        per_worker_overrides: dict[str, float] = (
            self.config.get_param("per_worker_overrides") or {}
        )

        if target_shift_type_ids is not None:
            filtered_shifts = [
                st for st in shift_types if st.id in target_shift_type_ids
            ]
        else:
            filtered_shifts = shift_types

        if not filtered_shifts:
            logger.warning(
                "min_rest constraint: no shift types selected after applying "
                "the shift_types filter; constraint has no effect"
            )
            return

        same_period_gaps = self._compute_same_period_gaps(filtered_shifts)
        adjacent_period_gaps = self._compute_adjacent_period_gaps(
            filtered_shifts, num_periods, period_dates
        )

        pair_count = 0

        for worker in workers:
            min_rest_hours = per_worker_overrides.get(worker.id, default_min_rest_hours)

            # Same-period pairs (single-day periods only).
            for period in range(num_periods):
                if period >= len(period_dates):
                    continue
                p_start, p_end = period_dates[period]
                if p_start != p_end:
                    continue  # multi-day period: no same-period check
                for (a_id, b_id), gap in same_period_gaps.items():
                    if gap >= min_rest_hours:
                        continue
                    added = self._add_pair_constraint(
                        worker.id, period, a_id, period, b_id
                    )
                    if added:
                        pair_count += 1

            # Adjacent-period pairs.
            for p, pair_gaps in adjacent_period_gaps.items():
                q = p + 1
                for (a_id, b_id), gap in pair_gaps.items():
                    if gap >= min_rest_hours:
                        continue
                    added = self._add_pair_constraint(worker.id, p, a_id, q, b_id)
                    if added:
                        pair_count += 1

        if pair_count == 0:
            logger.warning(
                "min_rest constraint: no conflicting shift pairs found for "
                "the configured min_rest_hours and horizon; constraint has "
                "no effect"
            )
            return

        # Store total for debugging. Registered as "auxiliary" so
        # ObjectiveBuilder skips it -- it is a derived sum of the
        # rest_viol_* variables above, not an independent penalty, and
        # would otherwise double the effective weight of this constraint
        # in the objective.
        viol_vars = [
            v
            for k, v in self._violation_variables.items()
            if k.startswith("rest_viol_")
        ]
        if viol_vars:
            total_var = self.model.new_int_var(
                0, len(viol_vars), "min_rest_total_violations"
            )
            self.model.add(total_var == sum(viol_vars))
            self._violation_variables["total"] = total_var
            self._violation_variable_types["total"] = "auxiliary"

    def _compute_same_period_gaps(
        self, filtered_shifts: list[ShiftType]
    ) -> dict[tuple[str, str], float]:
        """
        Precompute the rest gap (in hours) for every unordered pair of
        DIFFERENT shift types {a, b} when both fall on the same calendar
        day. This is date-independent (depends only on time-of-day), so it
        is computed once and reused across every single-day period and
        every worker.
        """
        gaps: dict[tuple[str, str], float] = {}
        for i, a in enumerate(filtered_shifts):
            a_start, a_end = _shift_interval(a, _TIME_OF_DAY_ANCHOR)
            for b in filtered_shifts[i + 1 :]:
                b_start, b_end = _shift_interval(b, _TIME_OF_DAY_ANCHOR)
                gaps[(a.id, b.id)] = _rest_gap_hours(a_start, a_end, b_start, b_end)
        return gaps

    def _compute_adjacent_period_gaps(
        self,
        filtered_shifts: list[ShiftType],
        num_periods: int,
        period_dates: list[tuple[date, date]],
    ) -> dict[int, dict[tuple[str, str], float]]:
        """
        Precompute the rest gap (in hours) for every ORDERED pair of shift
        types (a, b) -- a assignable in period p, b assignable in period
        p+1 -- keyed by p, using the real calendar dates in period_dates:
        a is anchored on period p's LAST day, b is anchored on period
        p+1's FIRST day.
        """
        result: dict[int, dict[tuple[str, str], float]] = {}
        for p in range(num_periods - 1):
            q = p + 1
            if p >= len(period_dates) or q >= len(period_dates):
                continue
            p_last_day = period_dates[p][1]
            q_first_day = period_dates[q][0]

            pair_gaps: dict[tuple[str, str], float] = {}
            for a in filtered_shifts:
                a_start, a_end = _shift_interval(a, p_last_day)
                for b in filtered_shifts:
                    b_start, b_end = _shift_interval(b, q_first_day)
                    pair_gaps[(a.id, b.id)] = _rest_gap_hours(
                        a_start, a_end, b_start, b_end
                    )
            result[p] = pair_gaps
        return result

    def _add_pair_constraint(
        self,
        worker_id: str,
        period_a: int,
        shift_a_id: str,
        period_b: int,
        shift_b_id: str,
    ) -> bool:
        """
        Add a soft-shaped conflict violation variable between two
        assignment variables for the same worker: `v >= x_a + x_b - 1`.

        Returns:
            True if a constraint was added (both assignment variables
            existed), False if either variable was missing (e.g. the
            shift does not apply that period) -- a soft no-op, not an
            error, since callers already filtered by configured shift
            types and only pass periods that exist.
        """
        try:
            var_a = self.variables.get_assignment_var(worker_id, period_a, shift_a_id)
        except KeyError:
            return False
        try:
            var_b = self.variables.get_assignment_var(worker_id, period_b, shift_b_id)
        except KeyError:
            return False

        violation_name = (
            f"rest_viol_{worker_id}_p{period_a}_{shift_a_id}_p{period_b}_{shift_b_id}"
        )
        violation_var = self.model.new_bool_var(violation_name)
        self.model.add(violation_var >= var_a + var_b - 1)

        self._violation_variables[violation_name] = violation_var
        self._constraint_count += 1
        return True
