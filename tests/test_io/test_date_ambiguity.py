"""Tests for date ambiguity handling in CSV and Excel loaders.

These tests verify proper handling of ambiguous dates (where day and month
are both <= 12) across different format configurations.

Issue: scheduler-78
"""

import logging
from datetime import date
from pathlib import Path

import openpyxl
import pytest

from shift_solver.io.csv_loader import CSVLoader
from shift_solver.io.date_utils import _warned_dates, parse_date
from shift_solver.io.excel_handler import ExcelLoader


class ExampleError(Exception):
    """Test exception class."""

    pass


class TestAmbiguousDateInterpretation:
    """Tests for how ambiguous dates are interpreted in different formats."""

    def setup_method(self) -> None:
        """Clear warned dates cache before each test."""
        _warned_dates.clear()

    def test_ambiguous_date_us_interpretation(self) -> None:
        """In auto mode, ambiguous dates are interpreted as US (MM/DD/YYYY)."""
        # 01/02/2026 should be January 2nd, not February 1st
        result = parse_date("01/02/2026", "test", 1, ExampleError, date_format="auto")
        assert result == date(2026, 1, 2)

    def test_ambiguous_date_eu_override(self) -> None:
        """With EU format, ambiguous dates are interpreted as EU (DD/MM/YYYY)."""
        # 01/02/2026 should be February 1st when EU format is specified
        result = parse_date("01/02/2026", "test", 1, ExampleError, date_format="eu")
        assert result == date(2026, 2, 1)

    def test_ambiguous_date_us_override(self) -> None:
        """With US format, ambiguous dates are interpreted as US (MM/DD/YYYY)."""
        # 01/02/2026 should be January 2nd when US format is specified
        result = parse_date("01/02/2026", "test", 1, ExampleError, date_format="us")
        assert result == date(2026, 1, 2)

    def test_month_boundary_ambiguous(self) -> None:
        """Test ambiguous dates at month boundaries."""
        _warned_dates.clear()
        # 12/01/2026 is ambiguous: could be Dec 1 (US) or Jan 12 (EU)
        result = parse_date("12/01/2026", "test", 1, ExampleError, date_format="auto")
        assert result == date(2026, 12, 1)  # US interpretation

        result_eu = parse_date("12/01/2026", "test", 1, ExampleError, date_format="eu")
        assert result_eu == date(2026, 1, 12)  # EU interpretation

    def test_same_day_month_not_ambiguous(self) -> None:
        """Dates with same day and month are not ambiguous."""
        _warned_dates.clear()
        # 06/06/2026 results in same date regardless of format
        result = parse_date("06/06/2026", "test", 1, ExampleError, date_format="auto")
        assert result == date(2026, 6, 6)


class TestWarningDeduplication:
    """Tests for warning deduplication across multiple parses."""

    def setup_method(self) -> None:
        """Clear warned dates cache before each test."""
        _warned_dates.clear()

    def test_same_date_different_fields_warns_once(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Same date in different fields should only warn once."""
        with caplog.at_level(logging.WARNING):
            parse_date("01/02/2026", "start_date", 1, ExampleError)
            parse_date("01/02/2026", "end_date", 1, ExampleError)
            parse_date("01/02/2026", "other_date", 2, ExampleError)

        warning_count = caplog.text.count("Ambiguous date '01/02/2026'")
        assert warning_count == 1

    def test_different_ambiguous_dates_each_warn(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Different ambiguous dates should each get their own warning."""
        with caplog.at_level(logging.WARNING):
            parse_date("01/02/2026", "field1", 1, ExampleError)
            parse_date("03/04/2026", "field2", 2, ExampleError)
            parse_date("05/06/2026", "field3", 3, ExampleError)

        assert "Ambiguous date '01/02/2026'" in caplog.text
        assert "Ambiguous date '03/04/2026'" in caplog.text
        # 05/06 is not ambiguous since 5 == 5 would make it same date
        # Actually wait, 05/06 is ambiguous: May 6 vs June 5
        # Let me check: first=5, second=6, both <=12, and 5 != 6
        assert "Ambiguous date '05/06/2026'" in caplog.text

    def test_warning_cache_can_be_cleared(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Clearing the cache should allow warnings again."""
        with caplog.at_level(logging.WARNING):
            parse_date("01/02/2026", "field1", 1, ExampleError)

        assert "Ambiguous date '01/02/2026'" in caplog.text
        caplog.clear()

        # Clear cache
        _warned_dates.clear()

        with caplog.at_level(logging.WARNING):
            parse_date("01/02/2026", "field2", 2, ExampleError)

        # Should warn again after cache clear
        assert "Ambiguous date '01/02/2026'" in caplog.text


class TestUnambiguousDates:
    """Tests for dates that are unambiguously one format or another."""

    def setup_method(self) -> None:
        """Clear warned dates cache before each test."""
        _warned_dates.clear()

    def test_day_over_12_is_eu(self, caplog: pytest.LogCaptureFixture) -> None:
        """Date with day > 12 must be EU format and doesn't warn."""
        with caplog.at_level(logging.WARNING):
            result = parse_date("25/12/2026", "test", 1, ExampleError)
            assert result == date(2026, 12, 25)  # Christmas

        assert "Ambiguous" not in caplog.text

    def test_month_over_12_is_us(self, caplog: pytest.LogCaptureFixture) -> None:
        """Date with second number > 12 must be US format and doesn't warn."""
        with caplog.at_level(logging.WARNING):
            result = parse_date("12/25/2026", "test", 1, ExampleError)
            assert result == date(2026, 12, 25)  # Christmas

        assert "Ambiguous" not in caplog.text

    def test_iso_format_never_warns(self, caplog: pytest.LogCaptureFixture) -> None:
        """ISO format dates never warn about ambiguity."""
        with caplog.at_level(logging.WARNING):
            result = parse_date("2026-01-02", "test", 1, ExampleError)
            assert result == date(2026, 1, 2)

        assert "Ambiguous" not in caplog.text


class TestCSVLoaderDateAmbiguity:
    """Tests for date ambiguity handling in CSV loader."""

    def setup_method(self) -> None:
        """Clear warned dates cache before each test."""
        _warned_dates.clear()

    def test_mixed_unambiguous_dates(self, tmp_path: Path) -> None:
        """CSV with all unambiguous dates should parse correctly."""
        csv_file = tmp_path / "availability.csv"
        csv_file.write_text(
            "worker_id,start_date,end_date,availability_type\n"
            "W001,2026-01-15,2026-01-20,unavailable\n"  # ISO
            "W002,01/15/2026,01/20/2026,unavailable\n"  # US (unambiguous)
            "W003,15/01/2026,20/01/2026,unavailable\n"  # EU (unambiguous)
        )

        loader = CSVLoader()
        avails = loader.load_availability(csv_file)

        assert len(avails) == 3
        assert avails[0].start_date == date(2026, 1, 15)
        assert avails[1].start_date == date(2026, 1, 15)
        assert avails[2].start_date == date(2026, 1, 15)

    def test_ambiguous_dates_use_us_format(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """CSV with ambiguous dates should use US format and warn."""
        csv_file = tmp_path / "availability.csv"
        csv_file.write_text(
            "worker_id,start_date,end_date,availability_type\n"
            "W001,01/02/2026,01/03/2026,unavailable\n"  # Ambiguous
        )

        with caplog.at_level(logging.WARNING):
            loader = CSVLoader()
            avails = loader.load_availability(csv_file)

        assert len(avails) == 1
        # Should be interpreted as US: January 2nd and January 3rd
        assert avails[0].start_date == date(2026, 1, 2)
        assert avails[0].end_date == date(2026, 1, 3)

        # Should have logged warnings
        assert "Ambiguous date" in caplog.text


class TestExcelLoaderDateAmbiguity:
    """Tests for date ambiguity handling in Excel loader."""

    def setup_method(self) -> None:
        """Clear warned dates cache before each test."""
        _warned_dates.clear()

    def test_excel_date_objects_no_ambiguity(self, tmp_path: Path) -> None:
        """Excel with native date objects has no ambiguity."""
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Availability"
        ws.append(["worker_id", "start_date", "end_date", "availability_type"])
        # Native date objects - no ambiguity possible
        ws.append(["W001", date(2026, 1, 2), date(2026, 1, 3), "unavailable"])

        excel_file = tmp_path / "input.xlsx"
        wb.save(excel_file)

        loader = ExcelLoader()
        avails = loader.load_availability(excel_file)

        assert len(avails) == 1
        assert avails[0].start_date == date(2026, 1, 2)
        assert avails[0].end_date == date(2026, 1, 3)

    def test_excel_string_dates_with_ambiguity(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Excel with string dates should handle ambiguity like CSV."""
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Availability"
        ws.append(["worker_id", "start_date", "end_date", "availability_type"])
        # String dates - ambiguity possible
        ws.append(["W001", "01/02/2026", "01/03/2026", "unavailable"])

        excel_file = tmp_path / "input.xlsx"
        wb.save(excel_file)

        with caplog.at_level(logging.WARNING):
            loader = ExcelLoader()
            avails = loader.load_availability(excel_file)

        assert len(avails) == 1
        # Should be interpreted as US: January 2nd and January 3rd
        assert avails[0].start_date == date(2026, 1, 2)
        assert avails[0].end_date == date(2026, 1, 3)


class TestDateEdgeCases:
    """Tests for edge cases in date parsing."""

    def setup_method(self) -> None:
        """Clear warned dates cache before each test."""
        _warned_dates.clear()

    def test_leap_year_date(self) -> None:
        """Test parsing leap year dates."""
        # 2024 is a leap year
        result = parse_date("02/29/2024", "test", 1, ExampleError, date_format="us")
        assert result == date(2024, 2, 29)

        result = parse_date("29/02/2024", "test", 1, ExampleError, date_format="eu")
        assert result == date(2024, 2, 29)

    def test_invalid_leap_year_raises_error(self) -> None:
        """Test that invalid leap year date raises error."""
        # 2026 is not a leap year
        with pytest.raises(ExampleError, match="Invalid date"):
            parse_date("02/29/2026", "test", 1, ExampleError, date_format="us")

    def test_year_end_dates(self) -> None:
        """Test parsing dates at year boundaries."""
        result = parse_date("12/31/2026", "test", 1, ExampleError, date_format="us")
        assert result == date(2026, 12, 31)

        result = parse_date("01/01/2027", "test", 1, ExampleError, date_format="us")
        assert result == date(2027, 1, 1)

    def test_first_of_month_ambiguity(self) -> None:
        """Test ambiguity on first of month dates."""
        _warned_dates.clear()
        # 01/01/2026 is not ambiguous (same day and month)
        result = parse_date("01/01/2026", "test", 1, ExampleError)
        assert result == date(2026, 1, 1)

        # 02/01/2026 is ambiguous
        result = parse_date("02/01/2026", "test", 1, ExampleError)
        assert result == date(2026, 2, 1)  # US: February 1st

        result_eu = parse_date("02/01/2026", "test", 1, ExampleError, date_format="eu")
        assert result_eu == date(2026, 1, 2)  # EU: January 2nd
