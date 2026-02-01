"""Tests for logging infrastructure."""

import logging
from pathlib import Path

import pytest

from shift_solver.utils.logging import (
    SolverProgressCallback,
    get_logger,
    setup_logging,
)


class TestLoggingSetup:
    """Test logging configuration."""

    def test_setup_logging_default(self) -> None:
        """Default setup should configure INFO level."""
        setup_logging()
        logger = get_logger("test")
        assert logger.level <= logging.INFO

    def test_setup_logging_debug(self) -> None:
        """Debug setup should configure DEBUG level."""
        setup_logging(level="DEBUG")
        logger = get_logger("test.debug")
        assert logger.isEnabledFor(logging.DEBUG)

    def test_setup_logging_quiet(self) -> None:
        """Quiet setup should only log warnings and above."""
        setup_logging(level="WARNING")
        logger = get_logger("test.quiet")
        assert logger.isEnabledFor(logging.WARNING)
        assert not logger.isEnabledFor(logging.INFO)

    def test_setup_logging_with_file(self, tmp_path: Path) -> None:
        """Logging can write to file."""
        log_file = tmp_path / "test.log"
        setup_logging(log_file=log_file)
        logger = get_logger("test.file")
        logger.info("Test message")

        # Flush handlers
        for handler in logger.handlers:
            handler.flush()

        # File should exist (may be empty due to buffering)
        assert log_file.exists()

    def test_get_logger_creates_child_logger(self) -> None:
        """get_logger should create child of shift_solver logger."""
        logger = get_logger("mymodule")
        assert "shift_solver" in logger.name

    def test_get_logger_without_name(self) -> None:
        """get_logger without name returns root shift_solver logger."""
        logger = get_logger()
        assert logger.name == "shift_solver"


class TestSolverProgressCallback:
    """Test solver progress tracking."""

    def test_callback_creation(self) -> None:
        """Callback should be created with defaults."""
        callback = SolverProgressCallback()
        assert callback is not None

    def test_callback_tracks_solutions(self) -> None:
        """Callback should track solution count."""
        callback = SolverProgressCallback()
        # Simulate finding solutions
        callback.on_solution_found(objective=100.0, time_elapsed=1.0)
        callback.on_solution_found(objective=90.0, time_elapsed=2.0)
        assert callback.solution_count == 2

    def test_callback_tracks_best_objective(self) -> None:
        """Callback should track best objective value."""
        callback = SolverProgressCallback()
        callback.on_solution_found(objective=100.0, time_elapsed=1.0)
        callback.on_solution_found(objective=80.0, time_elapsed=2.0)
        callback.on_solution_found(objective=90.0, time_elapsed=3.0)
        assert callback.best_objective == 80.0

    def test_callback_progress_percentage(self) -> None:
        """Callback should report progress percentage."""
        callback = SolverProgressCallback(time_limit_seconds=100)
        callback.on_solution_found(objective=100.0, time_elapsed=50.0)
        assert callback.progress_percentage == 50.0

    def test_callback_logs_progress(self, caplog: pytest.LogCaptureFixture) -> None:
        """Callback should log progress at intervals."""
        callback = SolverProgressCallback(log_interval_seconds=0)  # Log immediately
        with caplog.at_level(logging.INFO, logger="shift_solver"):
            callback.on_solution_found(objective=100.0, time_elapsed=1.0)
        # Should have logged something
        assert len(caplog.records) > 0

    def test_callback_summary(self) -> None:
        """Callback should provide summary statistics."""
        callback = SolverProgressCallback(time_limit_seconds=100)
        callback.on_solution_found(objective=100.0, time_elapsed=10.0)
        callback.on_solution_found(objective=80.0, time_elapsed=30.0)

        summary = callback.get_summary()
        assert summary["solution_count"] == 2
        assert summary["best_objective"] == 80.0
        assert summary["last_improvement_time"] == 30.0
