"""Weekend constraint - complete weekends, identical shift type, and
weekend-count/consecutive-weekend limits.

Weekend-specific rules are a staple of rostering benchmarks (e.g. the
Nurse Rostering Competition INRC-II): workers who work part of a weekend
should often work all of it ("complete weekends"), should work the same
shift type on both days, and organizations frequently want to cap how
many weekends a worker works in total, or how many *consecutive*
weekends a worker can be scheduled without a break.
"""

from datetime import date, timedelta
from typing import TYPE_CHECKING, Any

from ortools.sat.python import cp_model

from shift_solver.constraints import _windows
from shift_solver.constraints.base import BaseConstraint, ConstraintConfig
from shift_solver.models import ShiftType, Worker
from shift_solver.utils import get_logger

if TYPE_CHECKING:
    from shift_solver.solver.types import SolverVariables

logger = get_logger("constraints.weekend")

DEFAULT_WEEKEND_DAYS = (5, 6)  # Python weekday numbers: Saturday, Sunday


class WeekendConstraint(BaseConstraint):
    """
    Weekend-specific scheduling rules.

    Groups calendar-day periods into "weekends" (runs of consecutive
    calendar days whose weekday number is in ``weekend_days``) and
    optionally enforces, per worker:

    - ``require_complete``: a worker who works part of a weekend must
      work all of it (no working just the Saturday, or just the Sunday).
    - ``identical_shift_type``: when a worker works both days of a
      weekend, they must work the *same* shift type both days.
    - ``max_working_weekends``: caps the total number of weekends (across
      the whole horizon) a worker may work at least one shift in.
    - ``max_consecutive_weekends``: caps the length of any run of
      consecutive working weekends for a worker.

    All four rules are independently optional -- set/enable only the
    ones relevant to a deployment. Each is encoded as a soft violation
    variable so that when this constraint is configured with
    ``is_hard=True`` (or the deployment enables it as a hard rule),
    ``ShiftSolver`` pinning every violation variable to 0 forces the
    corresponding hard behavior; see each ``_apply_*`` helper's
    docstring for why the pin is correct.

    This constraint is only meaningful when every period maps to exactly
    one calendar day (``period_start == period_end`` for every period in
    ``period_dates``) -- multi-day periods have no per-day resolution to
    group into weekends. If any period in the horizon spans more than
    one day, this constraint logs a warning and has no effect.

    Required context:
        - workers: list[Worker] - available workers
        - shift_types: list[ShiftType] - shift types
        - num_periods: int - number of scheduling periods
        - period_dates: list[tuple[date, date]] - (start, end) for each
            period; must be one-day periods for this constraint to do
            anything

    Config parameters:
        - weekend_days: list[int] - Python weekday numbers (0=Monday,
            6=Sunday) that count as weekend days (default: [5, 6], i.e.
            Saturday and Sunday)
        - require_complete: bool - if true, penalize/forbid working only
            part of a weekend (default: false)
        - identical_shift_type: bool - if true, penalize/forbid working
            different shift types on the two days of a weekend a worker
            works both days of (default: false)
        - max_working_weekends: int | None - maximum number of weekends a
            worker may work across the horizon (default: None, no limit)
        - max_consecutive_weekends: int | None - maximum run length of
            consecutive working weekends for a worker (default: None, no
            limit)
    """

    constraint_id = "weekend"

    def __init__(
        self,
        model: cp_model.CpModel,
        variables: "SolverVariables",
        config: ConstraintConfig | None = None,
    ) -> None:
        """Initialize weekend constraint."""
        super().__init__(model, variables, config)

    def apply(self, **context: Any) -> None:
        """
        Apply weekend constraint to the model.

        Args:
            **context: Must include workers, shift_types, num_periods,
                period_dates
        """
        if not self.is_enabled:
            return

        workers: list[Worker] = context["workers"]
        shift_types: list[ShiftType] = context["shift_types"]
        num_periods: int = context["num_periods"]
        period_dates: list[tuple[date, date]] = context["period_dates"]

        if not period_dates or num_periods <= 0:
            logger.warning(
                "weekend constraint: no period_dates/periods provided; "
                "constraint requires per-day period_dates and has no effect"
            )
            return

        effective_periods = min(num_periods, len(period_dates))
        if effective_periods < num_periods:
            logger.warning(
                "weekend constraint: period_dates has %d entries but "
                "num_periods=%d; only the first %d periods will be "
                "considered",
                len(period_dates),
                num_periods,
                effective_periods,
            )

        for idx in range(effective_periods):
            period_start, period_end = period_dates[idx]
            if period_start != period_end:
                logger.warning(
                    "weekend constraint: period %d spans %s..%s (multi-day); "
                    "this constraint requires one-day periods (period_start "
                    "== period_end) and has no effect",
                    idx,
                    period_start,
                    period_end,
                )
                return

        weekend_days = self._resolve_weekend_days()
        if not weekend_days:
            return

        require_complete: bool = bool(self.config.get_param("require_complete", False))
        identical_shift_type: bool = bool(
            self.config.get_param("identical_shift_type", False)
        )
        max_working_weekends: int | None = self.config.get_param("max_working_weekends")
        max_consecutive_weekends: int | None = self.config.get_param(
            "max_consecutive_weekends"
        )

        if not (
            require_complete
            or identical_shift_type
            or max_working_weekends is not None
            or max_consecutive_weekends is not None
        ):
            logger.warning(
                "weekend constraint: no rule enabled (require_complete, "
                "identical_shift_type, max_working_weekends, and "
                "max_consecutive_weekends are all unset/false); constraint "
                "has no effect"
            )
            return

        groups = self._build_weekend_groups(
            period_dates, effective_periods, weekend_days
        )
        if not groups:
            logger.warning(
                "weekend constraint: no weekend-day periods found for "
                "weekend_days=%s in the scheduling horizon; constraint has "
                "no effect",
                sorted(weekend_days),
            )
            return

        day_periods = sorted({p for group in groups for p in group})

        for worker in workers:
            works = self._build_works_indicators(worker, day_periods, shift_types)

            if require_complete:
                self._apply_require_complete(worker, groups, works)

            if identical_shift_type:
                self._apply_identical_shift_type(worker, groups, works, shift_types)

            if max_working_weekends is not None or max_consecutive_weekends is not None:
                wknd = self._build_weekend_indicators(worker, groups, works)

                if max_working_weekends is not None:
                    self._apply_max_working_weekends(worker, wknd, max_working_weekends)

                if max_consecutive_weekends is not None:
                    self._apply_max_consecutive_weekends(
                        worker, wknd, max_consecutive_weekends
                    )

    def _resolve_weekend_days(self) -> set[int]:
        """
        Resolve and validate the weekend_days parameter.

        Returns an empty set (after warning) if the resolved set is empty
        or every configured value is out of range -- callers must treat
        an empty return as "no-op".
        """
        weekend_days_param: list[int] | None = self.config.get_param("weekend_days")
        weekend_days = (
            set(DEFAULT_WEEKEND_DAYS)
            if weekend_days_param is None
            else set(weekend_days_param)
        )

        invalid = {d for d in weekend_days if d < 0 or d > 6}
        if invalid:
            logger.warning(
                "weekend constraint: weekend_days contains invalid weekday "
                "numbers %s (must be 0-6); ignoring the invalid values",
                sorted(invalid),
            )
            weekend_days -= invalid

        if not weekend_days:
            logger.warning(
                "weekend constraint: no valid weekend_days configured; "
                "constraint has no effect"
            )
        return weekend_days

    def _build_weekend_groups(
        self,
        period_dates: list[tuple[date, date]],
        effective_periods: int,
        weekend_days: set[int],
    ) -> list[list[int]]:
        """
        Group day-periods into weekends.

        A weekend group is a maximal run of periods whose calendar dates
        are (a) each on a configured weekend day and (b) each exactly one
        calendar day after the previous one in the run. With the default
        weekend_days=[5, 6] this produces one Sat+Sun group per weekend,
        with horizon truncation naturally producing a group of 1 (e.g. a
        lone trailing Saturday with no following Sunday in the horizon).
        """
        groups: list[list[int]] = []
        current: list[int] = []
        prev_date: date | None = None

        for period_idx in range(effective_periods):
            day = period_dates[period_idx][0]
            if day.weekday() in weekend_days:
                if (
                    current
                    and prev_date is not None
                    and day == prev_date + timedelta(days=1)
                ):
                    current.append(period_idx)
                else:
                    if current:
                        groups.append(current)
                    current = [period_idx]
                prev_date = day
            else:
                if current:
                    groups.append(current)
                    current = []
                prev_date = None

        if current:
            groups.append(current)

        return groups

    def _build_works_indicators(
        self,
        worker: Worker,
        day_periods: list[int],
        shift_types: list[ShiftType],
    ) -> dict[int, cp_model.IntVar]:
        """
        Build works[period] = OR(assignment vars for worker in that period
        across all shift types), for every weekend day-period.
        """
        works: dict[int, cp_model.IntVar] = {}

        for period in day_periods:
            candidate_vars = []
            for shift_type in shift_types:
                try:
                    candidate_vars.append(
                        self.variables.get_assignment_var(
                            worker.id, period, shift_type.id
                        )
                    )
                except KeyError:
                    continue

            works_var = self.model.new_bool_var(f"wknd_works_{worker.id}_p{period}")
            if candidate_vars:
                self.model.add(sum(candidate_vars) >= 1).only_enforce_if(works_var)
                self.model.add(sum(candidate_vars) == 0).only_enforce_if(
                    works_var.negated()
                )
                self._constraint_count += 2
            else:
                logger.warning(
                    "weekend constraint: no assignment variables for "
                    "worker '%s' in period %d; treating as never worked",
                    worker.id,
                    period,
                )
                self.model.add(works_var == 0)
                self._constraint_count += 1

            works[period] = works_var

        return works

    def _build_weekend_indicators(
        self,
        worker: Worker,
        groups: list[list[int]],
        works: dict[int, cp_model.IntVar],
    ) -> list[cp_model.IntVar]:
        """Build wknd[g] = OR(works[p] for p in group), one per weekend group."""
        wknd: list[cp_model.IntVar] = []

        for g_idx, group in enumerate(groups):
            day_vars = [works[p] for p in group]
            if len(day_vars) == 1:
                wknd.append(day_vars[0])
                continue

            wknd_var = self.model.new_bool_var(f"wknd_group_{worker.id}_g{g_idx}")
            self.model.add(sum(day_vars) >= 1).only_enforce_if(wknd_var)
            self.model.add(sum(day_vars) == 0).only_enforce_if(wknd_var.negated())
            self._constraint_count += 2
            wknd.append(wknd_var)

        return wknd

    def _apply_require_complete(
        self,
        worker: Worker,
        groups: list[list[int]],
        works: dict[int, cp_model.IntVar],
    ) -> None:
        """
        Penalize a worker working only part of a weekend.

        One violation variable per adjacent pair of days within a
        multi-day group (documented choice: not one per full pairwise
        combination), true whenever the two days' works[] indicators
        disagree. Chaining adjacent pairs is sufficient: forcing every
        adjacent pair's violation variable to 0 (e.g. via ShiftSolver's
        generic hard-mode pinning) makes works[] equal along the whole
        chain by transitivity, matching the hard formulation
        ``works[w,d1] == works[w,d2]`` for every day in the group.
        """
        for g_idx, group in enumerate(groups):
            if len(group) < 2:
                continue

            for i in range(len(group) - 1):
                d1, d2 = group[i], group[i + 1]
                w1, w2 = works[d1], works[d2]

                viol_name = f"wknd_complete_viol_{worker.id}_g{g_idx}_{d1}_{d2}"
                viol_var = self.model.new_int_var(0, 1, viol_name)
                self.model.add(viol_var >= w1 - w2)
                self.model.add(viol_var >= w2 - w1)
                self._constraint_count += 2

                self._violation_variables[viol_name] = viol_var

    def _apply_identical_shift_type(
        self,
        worker: Worker,
        groups: list[list[int]],
        works: dict[int, cp_model.IntVar],
        shift_types: list[ShiftType],
    ) -> None:
        """
        Penalize a worker working different shift types on the two days
        of a weekend they work both days of.

        For each adjacent pair of days within a multi-day group and each
        shift type, a violation variable is only enforced (>= the
        asymmetric difference of the two days' assignment variables for
        that shift type) when the worker works *both* days
        (``only_enforce_if([works[d1], works[d2]])``); when the worker
        doesn't work both days the variable is left unconstrained and
        minimized to 0 in soft mode, or unconditionally pinned to 0 by
        ShiftSolver's generic hard-mode enforcement -- which is a no-op
        given the enforcement condition doesn't hold, so hard mode
        correctly enforces "same shift type" only when both days are
        worked, not "must work both days" (that's require_complete's job).
        """
        for g_idx, group in enumerate(groups):
            if len(group) < 2:
                continue

            for i in range(len(group) - 1):
                d1, d2 = group[i], group[i + 1]
                w1, w2 = works[d1], works[d2]

                for shift_type in shift_types:
                    try:
                        x1 = self.variables.get_assignment_var(
                            worker.id, d1, shift_type.id
                        )
                        x2 = self.variables.get_assignment_var(
                            worker.id, d2, shift_type.id
                        )
                    except KeyError:
                        continue

                    viol_name = (
                        f"wknd_ident_viol_{worker.id}_g{g_idx}_{d1}_{d2}"
                        f"_{shift_type.id}"
                    )
                    viol_var = self.model.new_int_var(0, 1, viol_name)
                    self.model.add(viol_var >= x1 - x2).only_enforce_if([w1, w2])
                    self.model.add(viol_var >= x2 - x1).only_enforce_if([w1, w2])
                    self._constraint_count += 2

                    self._violation_variables[viol_name] = viol_var

    def _apply_max_working_weekends(
        self,
        worker: Worker,
        wknd_vars: list[cp_model.IntVar],
        max_working_weekends: int,
    ) -> None:
        """
        Cap the total number of weekends worked across the horizon.

        excess = max(0, sum(wknd) - max_working_weekends), encoded as a
        lower bound only (excess >= sum - max): in soft mode minimizing
        excess drives it to exactly that value; in hard mode pinning
        excess == 0 forces sum(wknd) <= max_working_weekends.
        """
        if max_working_weekends < 0:
            logger.warning(
                "weekend constraint: max_working_weekends=%d is negative "
                "for worker '%s'; ignoring",
                max_working_weekends,
                worker.id,
            )
            return

        if not wknd_vars:
            return

        excess_name = f"wknd_max_total_excess_{worker.id}"
        excess_var = self.model.new_int_var(0, len(wknd_vars), excess_name)
        self.model.add(excess_var >= sum(wknd_vars) - max_working_weekends)
        self._constraint_count += 1

        self._violation_variables[excess_name] = excess_var

    def _apply_max_consecutive_weekends(
        self,
        worker: Worker,
        wknd_vars: list[cp_model.IntVar],
        max_consecutive_weekends: int,
    ) -> None:
        """
        Cap the length of any run of consecutive working weekends.

        Standard "max N consecutive" encoding: for every sliding window
        of (max_consecutive_weekends + 1) consecutive weekend groups,
        excess >= sum(window) - max_consecutive_weekends. A window that
        can never contain more than max_consecutive_weekends working
        weekends (because _windows.iter_windows clamped it smaller than
        max_consecutive_weekends + 1, i.e. there aren't enough weekend
        groups in the horizon to violate the limit) is skipped -- it is
        trivially satisfied, not an independent violation.
        """
        if max_consecutive_weekends < 0:
            logger.warning(
                "weekend constraint: max_consecutive_weekends=%d is "
                "negative for worker '%s'; ignoring",
                max_consecutive_weekends,
                worker.id,
            )
            return

        if not wknd_vars:
            return

        window_size = max_consecutive_weekends + 1

        for window_start, window_end in _windows.iter_windows(
            len(wknd_vars),
            window_size,
            logger=logger,
            context=(
                f"weekend constraint (max_consecutive_weekends, worker={worker.id})"
            ),
        ):
            window_vars = wknd_vars[window_start:window_end]
            if len(window_vars) <= max_consecutive_weekends:
                # Clamped smaller than the run length being limited (fewer
                # weekend groups in the horizon than max + 1); trivially
                # satisfiable, nothing to constrain.
                continue

            excess_name = f"wknd_consec_excess_{worker.id}_w{window_start}"
            excess_var = self.model.new_int_var(0, len(window_vars), excess_name)
            self.model.add(excess_var >= sum(window_vars) - max_consecutive_weekends)
            self._constraint_count += 1

            self._violation_variables[excess_name] = excess_var
