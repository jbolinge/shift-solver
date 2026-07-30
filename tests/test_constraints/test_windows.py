"""Direct unit tests for the shared sliding-window helpers in _windows.py."""

import logging

import pytest
from ortools.sat.python import cp_model

from shift_solver.constraints import _windows


class TestIterWindows:
    """Tests for iter_windows()."""

    def test_basic_sliding_windows(self) -> None:
        """window_size < num_periods yields the expected count and pairs."""
        windows = list(_windows.iter_windows(num_periods=6, window_size=3))

        assert windows == [(0, 3), (1, 4), (2, 5), (3, 6)]

    def test_window_size_one_yields_one_window_per_period(self) -> None:
        windows = list(_windows.iter_windows(num_periods=4, window_size=1))

        assert windows == [(0, 1), (1, 2), (2, 3), (3, 4)]

    def test_window_size_equals_num_periods_yields_one_window(self) -> None:
        windows = list(_windows.iter_windows(num_periods=5, window_size=5))

        assert windows == [(0, 5)]

    def test_window_size_zero_yields_no_windows_and_no_warning(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Degenerate window_size=0 is harmless: no windows, no warning."""
        logger = logging.getLogger("test_windows")
        with caplog.at_level(logging.WARNING):
            windows = list(
                _windows.iter_windows(
                    num_periods=4, window_size=0, logger=logger, context="test"
                )
            )

        assert windows == []
        assert caplog.text == ""

    def test_negative_window_size_yields_no_windows(self) -> None:
        assert list(_windows.iter_windows(num_periods=4, window_size=-1)) == []

    def test_zero_num_periods_yields_no_windows(self) -> None:
        assert list(_windows.iter_windows(num_periods=0, window_size=3)) == []

    def test_oversized_window_clamps_to_full_horizon(self) -> None:
        """window_size > num_periods clamps to a single window covering the
        whole horizon (this module's own policy; individual constraints may
        guard against this case themselves before delegating here -- see
        frequency.py / max_absence.py)."""
        windows = list(_windows.iter_windows(num_periods=4, window_size=100))

        assert windows == [(0, 4)]

    def test_oversized_window_logs_warning_with_context(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        logger = logging.getLogger("test_windows")
        with caplog.at_level(logging.WARNING):
            list(
                _windows.iter_windows(
                    num_periods=4,
                    window_size=10,
                    logger=logger,
                    context="my_constraint",
                )
            )

        assert "my_constraint" in caplog.text
        assert "10" in caplog.text
        assert "4" in caplog.text

    def test_oversized_window_without_logger_does_not_raise(self) -> None:
        """logger is optional -- clamping still happens silently."""
        windows = list(_windows.iter_windows(num_periods=3, window_size=9))

        assert windows == [(0, 3)]


class TestBuildAbsenceViolation:
    """Tests for build_absence_violation()."""

    def test_empty_window_vars_returns_none_and_logs_warning(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        model = cp_model.CpModel()
        logger = logging.getLogger("test_windows")

        with caplog.at_level(logging.WARNING):
            result = _windows.build_absence_violation(
                model,
                [],
                "viol_w0",
                "has_w0",
                logger=logger,
                context="my_constraint",
            )

        assert result is None
        assert "my_constraint" in caplog.text
        assert "viol_w0" in caplog.text

    def test_empty_window_vars_without_logger_does_not_raise(self) -> None:
        model = cp_model.CpModel()

        result = _windows.build_absence_violation(model, [], "viol_w0", "has_w0")

        assert result is None

    def test_nonempty_window_vars_creates_violation_var(self) -> None:
        model = cp_model.CpModel()
        a = model.new_bool_var("a")
        b = model.new_bool_var("b")

        violation = _windows.build_absence_violation(model, [a, b], "viol_w0", "has_w0")

        assert violation is not None
        assert violation.name == "viol_w0"

    def test_violation_true_when_no_assignment(self) -> None:
        """Solving with all candidate vars forced to 0 must force the
        violation variable to 1."""
        model = cp_model.CpModel()
        a = model.new_bool_var("a")
        b = model.new_bool_var("b")
        violation = _windows.build_absence_violation(model, [a, b], "viol", "has")
        assert violation is not None

        model.add(a == 0)
        model.add(b == 0)

        solver = cp_model.CpSolver()
        status = solver.solve(model)

        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
        assert solver.value(violation) == 1

    def test_violation_false_when_assignment_present(self) -> None:
        """Solving with at least one candidate var forced to 1 must force the
        violation variable to 0."""
        model = cp_model.CpModel()
        a = model.new_bool_var("a")
        b = model.new_bool_var("b")
        violation = _windows.build_absence_violation(model, [a, b], "viol", "has")
        assert violation is not None

        model.add(a == 1)
        model.add(b == 0)

        solver = cp_model.CpSolver()
        status = solver.solve(model)

        assert status in (cp_model.OPTIMAL, cp_model.FEASIBLE)
        assert solver.value(violation) == 0
