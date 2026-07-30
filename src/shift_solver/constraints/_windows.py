"""Shared sliding-window helpers for periodic "must work within N periods"
constraints.

Several constraints (:class:`~shift_solver.constraints.frequency.FrequencyConstraint`,
:class:`~shift_solver.constraints.max_absence.MaxAbsenceConstraint`, and
``ShiftFrequencyConstraint``) all implement variants of the same idea: slide
a window of ``window_size`` consecutive periods across the schedule horizon
and flag (or forbid) any window in which a worker has zero assignments
across a set of candidate shift types. This module centralizes the window
math and the CP-SAT violation-variable wiring so the edge-case policy only
has to be reasoned about once.

Policy
------
This module implements ONE consistent policy for the two edge cases that
previously diverged across the three call sites:

- **Oversized window** (``window_size > num_periods``): :func:`iter_windows`
    *clamps* ``window_size`` down to ``num_periods``, producing a single
    window spanning the entire horizon, and logs a warning (if a logger is
    given) naming the requested window size and the horizon. This matches
    ``ShiftFrequencyConstraint``'s existing "clamp to the full horizon"
    behavior.

    ``FrequencyConstraint`` and ``MaxAbsenceConstraint`` are pinned by
    existing tests to an older, stricter policy for this same case --
    skip the window sliding entirely (zero windows, zero violation
    variables) rather than clamping to one full-horizon window. Their
    ``apply()`` methods therefore perform their own oversized-window guard
    *before* delegating to :func:`iter_windows`, so in practice
    :func:`iter_windows` is only ever called by them with a
    ``window_size <= num_periods`` and its clamp branch never fires for
    those two callers. This is a deliberate, documented divergence -- see
    each constraint's docstring -- not an inconsistency in this module.

- **Empty candidate variable list for a window** (e.g. a worker is
    restricted from every candidate shift type for every period in the
    window): :func:`build_absence_violation` logs a warning and skips that
    window -- it is a soft no-op, not an error. No violation variable and
    no CP-SAT constraint is created for that window.

Degenerate ``window_size <= 0`` is treated as "nothing to check": no
windows are produced and no warning is logged (this is a valid, harmless
configuration value -- e.g. ``max_periods_between=0`` -- not an oversized
window).
"""

from collections.abc import Iterator
from logging import Logger

from ortools.sat.python import cp_model


def iter_windows(
    num_periods: int,
    window_size: int,
    *,
    logger: Logger | None = None,
    context: str = "",
) -> Iterator[tuple[int, int]]:
    """
    Yield ``(window_start, window_end)`` pairs for every sliding window of
    ``window_size`` consecutive periods across ``[0, num_periods)``.

    ``window_end`` is exclusive, so the periods in a window are
    ``range(window_start, window_end)``.

    Args:
        num_periods: number of scheduling periods in the horizon.
        window_size: number of consecutive periods per window. Values
            ``<= 0`` yield no windows. Values ``> num_periods`` are
            clamped to ``num_periods`` (one window covering the whole
            horizon) -- see the module docstring's Policy section.
        logger: optional logger used to warn when clamping occurs.
        context: short prefix identifying the caller (e.g. the
            constraint id and parameter name) included in the warning
            message so it's clear which constraint/config triggered it.
    """
    if window_size <= 0 or num_periods <= 0:
        return

    if window_size > num_periods:
        if logger is not None:
            logger.warning(
                "%swindow_size=%d exceeds horizon of num_periods=%d periods; "
                "clamping to the full horizon",
                f"{context}: " if context else "",
                window_size,
                num_periods,
            )
        window_size = num_periods

    for window_start in range(num_periods - window_size + 1):
        yield window_start, window_start + window_size


def build_absence_violation(
    model: cp_model.CpModel,
    window_vars: list[cp_model.IntVar],
    violation_name: str,
    has_assignment_name: str,
    *,
    logger: Logger | None = None,
    context: str = "",
) -> cp_model.IntVar | None:
    """
    Build a boolean violation variable for a single window that is true
    iff none of ``window_vars`` (the candidate assignment variables for
    that window) is set.

    Adds three CP-SAT constraints tying an intermediate ``has_assignment``
    indicator and ``violation_name`` together:
        - has_assignment  <=>  sum(window_vars) >= 1
        - violation        ==  NOT has_assignment

    Args:
        model: CP-SAT model to add constraints to.
        window_vars: candidate assignment variables for this window. If
            empty (e.g. a worker is restricted from every candidate shift
            type in every period of the window), a warning is logged and
            ``None`` is returned -- no variable or constraint is created
            (soft no-op; see the module docstring's Policy section).
        violation_name: name for the created violation BoolVar.
        has_assignment_name: name for the intermediate has-assignment
            BoolVar.
        logger: optional logger used to warn on the empty-window case.
        context: short prefix identifying the caller, included in the
            warning message.

    Returns:
        The violation BoolVar, or ``None`` if ``window_vars`` was empty.
    """
    if not window_vars:
        if logger is not None:
            logger.warning(
                "%sno candidate assignment variables for window %r; skipping",
                f"{context}: " if context else "",
                violation_name,
            )
        return None

    violation_var = model.new_bool_var(violation_name)
    has_assignment = model.new_bool_var(has_assignment_name)

    # has_assignment is true iff sum(window_vars) >= 1
    model.add(sum(window_vars) >= 1).only_enforce_if(has_assignment)
    model.add(sum(window_vars) == 0).only_enforce_if(has_assignment.negated())

    # violation = NOT has_assignment
    model.add(violation_var == has_assignment.negated())

    return violation_var
