"""Solution callback for reporting solver progress and supporting cancellation."""

import threading
import time
from collections.abc import Callable
from typing import Any

from ortools.sat.python import cp_model


class SolverProgressCallback(cp_model.CpSolverSolutionCallback):
    """CP-SAT solution callback that reports progress and checks for cancellation.

    Args:
        cancel_event: Threading event checked each callback; triggers StopSearch() if set.
        on_progress: Callable receiving a dict of progress data, throttled to
            once per ``throttle_seconds``.
        throttle_seconds: Minimum interval between on_progress calls.
    """

    def __init__(
        self,
        cancel_event: threading.Event | None = None,
        on_progress: Callable[[dict[str, Any]], None] | None = None,
        throttle_seconds: float = 1.0,
    ) -> None:
        super().__init__()
        self._cancel_event = cancel_event
        self._on_progress = on_progress
        self._throttle_seconds = throttle_seconds
        self._solutions_found = 0
        self._last_report_time = 0.0
        self._start_time = time.monotonic()

    @property
    def solutions_found(self) -> int:
        return self._solutions_found

    def on_solution_callback(self) -> None:
        self._solutions_found += 1

        # Check cancellation
        if self._cancel_event is not None and self._cancel_event.is_set():
            self.StopSearch()
            return

        # Throttled progress reporting
        if self._on_progress is not None:
            now = time.monotonic()
            if now - self._last_report_time >= self._throttle_seconds:
                self._last_report_time = now
                objective = self.ObjectiveValue()
                best_bound = self.BestObjectiveBound()
                gap = (
                    abs(objective - best_bound)
                    / max(1.0, abs(objective))
                    * 100
                )
                self._on_progress(
                    {
                        "phase": "solving",
                        "solutions_found": self._solutions_found,
                        "objective_value": objective,
                        "best_bound": best_bound,
                        "gap_percent": round(gap, 2),
                        "wall_time": round(now - self._start_time, 1),
                    }
                )
