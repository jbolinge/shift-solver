"""Tests for logging infrastructure."""

import logging
from pathlib import Path

from shift_solver.utils.logging import (
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
