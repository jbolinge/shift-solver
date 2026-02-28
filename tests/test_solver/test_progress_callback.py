"""Tests for SolverProgressCallback."""

import threading

from shift_solver.solver.progress_callback import SolverProgressCallback


class FakeCallback(SolverProgressCallback):
    """Subclass that stubs ObjectiveValue/BestObjectiveBound/StopSearch.

    Since we can't call these outside a real solve, we override them.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._stopped = False
        self._fake_objective = 42.0
        self._fake_bound = 40.0

    def ObjectiveValue(self):
        return self._fake_objective

    def BestObjectiveBound(self):
        return self._fake_bound

    def StopSearch(self):
        self._stopped = True


class TestSolverProgressCallback:
    """Tests for the progress callback."""

    def test_solution_count_increments(self):
        """Each call to on_solution_callback increments the counter."""
        cb = FakeCallback()
        assert cb.solutions_found == 0
        cb.on_solution_callback()
        assert cb.solutions_found == 1
        cb.on_solution_callback()
        assert cb.solutions_found == 2

    def test_cancel_event_triggers_stop_search(self):
        """Setting the cancel event calls StopSearch."""
        event = threading.Event()
        cb = FakeCallback(cancel_event=event)
        event.set()
        cb.on_solution_callback()
        assert cb._stopped

    def test_no_cancel_does_not_stop(self):
        """Without cancel event, StopSearch is not called."""
        cb = FakeCallback()
        cb.on_solution_callback()
        assert not cb._stopped

    def test_on_progress_called(self):
        """Progress callback is invoked with correct data shape."""
        received = []
        cb = FakeCallback(
            on_progress=lambda data: received.append(data),
            throttle_seconds=0,
        )
        cb.on_solution_callback()
        assert len(received) == 1
        data = received[0]
        assert data["phase"] == "solving"
        assert data["solutions_found"] == 1
        assert data["objective_value"] == 42.0
        assert data["best_bound"] == 40.0
        assert isinstance(data["gap_percent"], float)
        assert isinstance(data["wall_time"], float)

    def test_throttling(self):
        """Progress callback is throttled to throttle_seconds interval."""
        received = []
        cb = FakeCallback(
            on_progress=lambda data: received.append(data),
            throttle_seconds=10.0,  # Very high — second call should be throttled
        )
        cb.on_solution_callback()
        assert len(received) == 1
        cb.on_solution_callback()
        assert len(received) == 1  # Still 1 — throttled

    def test_gap_calculation(self):
        """Gap percent is calculated correctly."""
        received = []
        cb = FakeCallback(
            on_progress=lambda data: received.append(data),
            throttle_seconds=0,
        )
        cb.on_solution_callback()
        data = received[0]
        # gap = abs(42 - 40) / max(1, abs(42)) * 100 = 2/42 * 100 ≈ 4.76
        expected_gap = round(abs(42.0 - 40.0) / max(1.0, abs(42.0)) * 100, 2)
        assert data["gap_percent"] == expected_gap

    def test_cancel_event_stops_before_progress(self):
        """When cancel is set, StopSearch fires and progress is not called."""
        received = []
        event = threading.Event()
        event.set()
        cb = FakeCallback(
            cancel_event=event,
            on_progress=lambda data: received.append(data),
            throttle_seconds=0,
        )
        cb.on_solution_callback()
        assert cb._stopped
        assert len(received) == 0  # Progress not called after cancel
