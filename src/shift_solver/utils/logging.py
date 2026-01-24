"""Logging infrastructure for shift-solver."""

import logging
import sys
from pathlib import Path
from typing import Any

# Root logger name for all shift-solver loggers
ROOT_LOGGER_NAME = "shift_solver"


def setup_logging(
    level: str = "INFO",
    log_file: Path | None = None,
    json_format: bool = False,
) -> None:
    """
    Configure logging for shift-solver.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR)
        log_file: Optional file path to write logs
        json_format: If True, output structured JSON logs
    """
    root_logger = logging.getLogger(ROOT_LOGGER_NAME)
    root_logger.setLevel(getattr(logging, level.upper()))

    # Clear existing handlers
    root_logger.handlers.clear()

    # Create formatter
    formatter: logging.Formatter
    if json_format:
        formatter = JsonFormatter()
    else:
        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    # Console handler
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File handler (if specified)
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)


def get_logger(name: str | None = None) -> logging.Logger:
    """
    Get a logger for the specified module.

    Args:
        name: Module name (will be prefixed with shift_solver)

    Returns:
        Logger instance
    """
    if name:
        return logging.getLogger(f"{ROOT_LOGGER_NAME}.{name}")
    return logging.getLogger(ROOT_LOGGER_NAME)


class JsonFormatter(logging.Formatter):
    """Format log records as JSON for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        """Format record as JSON string."""
        import json

        log_data = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Include extra fields
        for key, value in record.__dict__.items():
            if key not in (
                "name",
                "msg",
                "args",
                "created",
                "filename",
                "funcName",
                "levelname",
                "levelno",
                "lineno",
                "module",
                "msecs",
                "pathname",
                "process",
                "processName",
                "relativeCreated",
                "stack_info",
                "exc_info",
                "exc_text",
                "thread",
                "threadName",
                "taskName",
                "message",
            ):
                log_data[key] = value

        return json.dumps(log_data)


class SolverProgressCallback:
    """
    Callback for tracking solver progress.

    Used to monitor long-running solve operations and log
    intermediate solutions and progress.
    """

    def __init__(
        self,
        time_limit_seconds: float = 300.0,
        log_interval_seconds: float = 30.0,
    ) -> None:
        """
        Initialize progress callback.

        Args:
            time_limit_seconds: Expected time limit for solving
            log_interval_seconds: Minimum interval between progress logs
        """
        self.time_limit_seconds = time_limit_seconds
        self.log_interval_seconds = log_interval_seconds
        self.solution_count = 0
        self.best_objective: float | None = None
        self.last_improvement_time: float = 0.0
        self._last_log_time: float = 0.0
        self._logger = get_logger("solver.progress")

    @property
    def progress_percentage(self) -> float:
        """Get progress as percentage of time limit."""
        if self.time_limit_seconds <= 0:
            return 0.0
        return (self.last_improvement_time / self.time_limit_seconds) * 100.0

    def on_solution_found(self, objective: float, time_elapsed: float) -> None:
        """
        Called when a new solution is found.

        Args:
            objective: Objective value of the solution
            time_elapsed: Time since solve started
        """
        self.solution_count += 1

        # Track best objective (minimization)
        if self.best_objective is None or objective < self.best_objective:
            self.best_objective = objective
            self.last_improvement_time = time_elapsed

        # Log progress at intervals
        if time_elapsed - self._last_log_time >= self.log_interval_seconds:
            self._log_progress(time_elapsed)
            self._last_log_time = time_elapsed

    def _log_progress(self, time_elapsed: float) -> None:
        """Log current progress."""
        self._logger.info(
            f"Progress: {self.solution_count} solutions found, "
            f"best={self.best_objective:.1f}, "
            f"time={time_elapsed:.1f}s"
        )

    def get_summary(self) -> dict[str, Any]:
        """Get summary statistics."""
        return {
            "solution_count": self.solution_count,
            "best_objective": self.best_objective,
            "last_improvement_time": self.last_improvement_time,
        }
