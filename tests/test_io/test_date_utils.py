"""Tests for date parsing utilities with format configuration."""

import logging
from datetime import date

import pytest

from shift_solver.io.date_utils import _is_ambiguous_date, _warned_dates, parse_date


class TestDateFormatDetection:
    """Tests for ambiguous date detection."""

    def test_ambiguous_date_both_valid_month_day(self) -> None:
        """Date like 01/02/2026 is ambiguous (could be Jan 2 or Feb 1)."""
        assert _is_ambiguous_date("01/02/2026") is True
        assert _is_ambiguous_date("03/04/2026") is True
        assert _is_ambiguous_date("12/11/2026") is True

    def test_unambiguous_date_day_over_12(self) -> None:
        """Date like 15/02/2026 is unambiguous (must be EU: Feb 15)."""
        assert _is_ambiguous_date("15/02/2026") is False
        assert _is_ambiguous_date("25/12/2026") is False

    def test_unambiguous_date_month_over_12(self) -> None:
        """Date like 02/15/2026 is unambiguous (must be US: Feb 15)."""
        assert _is_ambiguous_date("02/15/2026") is False
        assert _is_ambiguous_date("12/25/2026") is False

    def test_iso_format_not_ambiguous(self) -> None:
        """ISO format with hyphens is not ambiguous."""
        assert _is_ambiguous_date("2026-01-02") is False
        assert _is_ambiguous_date("2026-12-25") is False

    def test_same_day_month_not_ambiguous(self) -> None:
        """Date like 05/05/2026 is not ambiguous (same result either way)."""
        assert _is_ambiguous_date("05/05/2026") is False
        assert _is_ambiguous_date("12/12/2026") is False


class ExampleError(Exception):
    """Test exception class."""

    pass


class TestParseDateWithFormat:
    """Tests for parse_date with explicit format selection."""

    def setup_method(self) -> None:
        """Clear warned dates cache before each test."""
        _warned_dates.clear()

    def test_parse_iso_format_explicit(self) -> None:
        """Test parsing ISO format when explicitly specified."""
        result = parse_date(
            "2026-01-15", "test_field", 1, ExampleError, date_format="iso"
        )
        assert result == date(2026, 1, 15)

    def test_parse_us_format_explicit(self) -> None:
        """Test parsing US format when explicitly specified."""
        result = parse_date(
            "01/15/2026", "test_field", 1, ExampleError, date_format="us"
        )
        assert result == date(2026, 1, 15)

    def test_parse_eu_format_explicit(self) -> None:
        """Test parsing EU format when explicitly specified."""
        result = parse_date(
            "15/01/2026", "test_field", 1, ExampleError, date_format="eu"
        )
        assert result == date(2026, 1, 15)

    def test_eu_format_interprets_correctly(self) -> None:
        """Test that EU format correctly interprets day/month order."""
        # 02/01/2026 in EU format is Jan 2
        result = parse_date(
            "02/01/2026", "test_field", 1, ExampleError, date_format="eu"
        )
        assert result == date(2026, 1, 2)

    def test_us_format_interprets_correctly(self) -> None:
        """Test that US format correctly interprets month/day order."""
        # 01/02/2026 in US format is Jan 2
        result = parse_date(
            "01/02/2026", "test_field", 1, ExampleError, date_format="us"
        )
        assert result == date(2026, 1, 2)

    def test_wrong_format_raises_error(self) -> None:
        """Test that using wrong format raises error."""
        # ISO date with US format should fail
        with pytest.raises(ExampleError, match="Invalid date"):
            parse_date(
                "2026-01-15", "test_field", 1, ExampleError, date_format="us"
            )

    def test_auto_format_parses_all(self) -> None:
        """Test that auto format tries all formats."""
        # ISO
        result = parse_date(
            "2026-01-15", "test_field", 1, ExampleError, date_format="auto"
        )
        assert result == date(2026, 1, 15)

        # US (month > 12 makes it unambiguous)
        result = parse_date(
            "01/15/2026", "test_field", 1, ExampleError, date_format="auto"
        )
        assert result == date(2026, 1, 15)

        # EU (day > 12 makes it unambiguous)
        result = parse_date(
            "15/01/2026", "test_field", 1, ExampleError, date_format="auto"
        )
        assert result == date(2026, 1, 15)


class TestAmbiguousDateWarning:
    """Tests for ambiguous date warnings in auto mode."""

    def setup_method(self) -> None:
        """Clear warned dates cache before each test."""
        _warned_dates.clear()

    def test_ambiguous_date_logs_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test that ambiguous dates log a warning in auto mode."""
        with caplog.at_level(logging.WARNING):
            result = parse_date(
                "01/02/2026", "test_field", 5, ExampleError, date_format="auto"
            )
            # Should be interpreted as US format (Jan 2)
            assert result == date(2026, 1, 2)

        assert "Ambiguous date '01/02/2026'" in caplog.text
        assert "line 5" in caplog.text
        assert "US format" in caplog.text

    def test_warning_only_logged_once_per_date(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test that same ambiguous date only warns once."""
        with caplog.at_level(logging.WARNING):
            parse_date(
                "03/04/2026", "field1", 1, ExampleError, date_format="auto"
            )
            parse_date(
                "03/04/2026", "field2", 2, ExampleError, date_format="auto"
            )

        # Count warnings for this specific date
        warning_count = caplog.text.count("Ambiguous date '03/04/2026'")
        assert warning_count == 1

    def test_no_warning_for_unambiguous_dates(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test that unambiguous dates don't log warnings."""
        with caplog.at_level(logging.WARNING):
            parse_date(
                "15/01/2026", "test_field", 1, ExampleError, date_format="auto"
            )
            parse_date(
                "2026-01-15", "test_field", 2, ExampleError, date_format="auto"
            )

        assert "Ambiguous" not in caplog.text

    def test_no_warning_with_explicit_format(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test that explicit format doesn't log warnings."""
        with caplog.at_level(logging.WARNING):
            parse_date(
                "01/02/2026", "test_field", 1, ExampleError, date_format="us"
            )
            parse_date(
                "01/02/2026", "test_field", 2, ExampleError, date_format="eu"
            )

        assert "Ambiguous" not in caplog.text


class TestDateFormatErrorMessages:
    """Tests for error messages with different date formats."""

    def test_auto_format_error_shows_all_formats(self) -> None:
        """Test that auto format error shows all supported formats."""
        with pytest.raises(ExampleError) as exc_info:
            parse_date("invalid", "test_field", 1, ExampleError, date_format="auto")

        assert "YYYY-MM-DD" in str(exc_info.value)
        assert "MM/DD/YYYY" in str(exc_info.value)
        assert "DD/MM/YYYY" in str(exc_info.value)

    def test_explicit_format_error_shows_specific_format(self) -> None:
        """Test that explicit format error shows only that format."""
        with pytest.raises(ExampleError) as exc_info:
            parse_date("invalid", "test_field", 1, ExampleError, date_format="iso")

        assert "YYYY-MM-DD" in str(exc_info.value)
        assert "MM/DD/YYYY" not in str(exc_info.value)

        with pytest.raises(ExampleError) as exc_info:
            parse_date("invalid", "test_field", 1, ExampleError, date_format="eu")

        assert "DD/MM/YYYY" in str(exc_info.value)
        assert "MM/DD/YYYY" not in str(exc_info.value)
