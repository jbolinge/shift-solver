"""Tests for priority field coercion consistency across CSV and Excel loaders.

These tests verify that both loaders handle priority values identically,
including edge cases like floats, negative numbers, and invalid strings.

Issue: scheduler-75
"""

from datetime import date
from pathlib import Path

import openpyxl
import pytest

from shift_solver.io.csv_loader import CSVLoader, CSVLoaderError
from shift_solver.io.excel_handler import ExcelHandlerError, ExcelLoader


class TestPriorityCoercionCSV:
    """Tests for priority coercion in CSV loader."""

    def _create_request_csv(self, tmp_path: Path, priority_value: str) -> Path:
        """Helper to create a request CSV with a specific priority value."""
        csv_file = tmp_path / "requests.csv"
        csv_file.write_text(
            "worker_id,start_date,end_date,request_type,shift_type_id,priority\n"
            f"W001,2026-01-10,2026-01-10,positive,day,{priority_value}\n"
        )
        return csv_file

    def test_valid_integer(self, tmp_path: Path) -> None:
        """Test valid integer priority."""
        csv_file = self._create_request_csv(tmp_path, "2")
        loader = CSVLoader()
        requests = loader.load_requests(csv_file)
        assert requests[0].priority == 2

    def test_empty_string_defaults_to_one(self, tmp_path: Path) -> None:
        """Test empty string returns default priority 1."""
        csv_file = self._create_request_csv(tmp_path, "")
        loader = CSVLoader()
        requests = loader.load_requests(csv_file)
        assert requests[0].priority == 1

    def test_float_string_raises_error(self, tmp_path: Path) -> None:
        """Test float string raises error."""
        csv_file = self._create_request_csv(tmp_path, "2.5")
        loader = CSVLoader()
        with pytest.raises(CSVLoaderError, match="Invalid priority.*2.5"):
            loader.load_requests(csv_file)

    def test_non_numeric_string_raises_error(self, tmp_path: Path) -> None:
        """Test non-numeric string raises error."""
        csv_file = self._create_request_csv(tmp_path, "high")
        loader = CSVLoader()
        with pytest.raises(CSVLoaderError, match="Invalid priority.*high"):
            loader.load_requests(csv_file)

    def test_negative_raises_error(self, tmp_path: Path) -> None:
        """Test negative priority raises error."""
        csv_file = self._create_request_csv(tmp_path, "-1")
        loader = CSVLoader()
        with pytest.raises(CSVLoaderError, match="priority must be positive.*-1"):
            loader.load_requests(csv_file)

    def test_zero_raises_error(self, tmp_path: Path) -> None:
        """Test zero priority raises error."""
        csv_file = self._create_request_csv(tmp_path, "0")
        loader = CSVLoader()
        with pytest.raises(CSVLoaderError, match="priority must be positive.*0"):
            loader.load_requests(csv_file)

    def test_whitespace_trimmed(self, tmp_path: Path) -> None:
        """Test whitespace around priority is trimmed."""
        csv_file = self._create_request_csv(tmp_path, " 2 ")
        loader = CSVLoader()
        requests = loader.load_requests(csv_file)
        assert requests[0].priority == 2

    def test_large_valid_priority(self, tmp_path: Path) -> None:
        """Test very large priority values are accepted."""
        csv_file = self._create_request_csv(tmp_path, "999999")
        loader = CSVLoader()
        requests = loader.load_requests(csv_file)
        assert requests[0].priority == 999999


class TestPriorityCoercionExcel:
    """Tests for priority coercion in Excel loader."""

    def _create_request_excel(self, tmp_path: Path, priority_value) -> Path:
        """Helper to create a request Excel file with a specific priority value."""
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Requests"
        ws.append(
            ["worker_id", "start_date", "end_date", "request_type", "shift_type_id", "priority"]
        )
        ws.append(["W001", date(2026, 1, 10), date(2026, 1, 10), "positive", "day", priority_value])
        excel_file = tmp_path / "requests.xlsx"
        wb.save(excel_file)
        return excel_file

    def test_valid_integer(self, tmp_path: Path) -> None:
        """Test valid integer priority."""
        excel_file = self._create_request_excel(tmp_path, 2)
        loader = ExcelLoader()
        requests = loader.load_requests(excel_file)
        assert requests[0].priority == 2

    def test_none_defaults_to_one(self, tmp_path: Path) -> None:
        """Test None returns default priority 1."""
        excel_file = self._create_request_excel(tmp_path, None)
        loader = ExcelLoader()
        requests = loader.load_requests(excel_file)
        assert requests[0].priority == 1

    def test_empty_string_defaults_to_one(self, tmp_path: Path) -> None:
        """Test empty string returns default priority 1."""
        excel_file = self._create_request_excel(tmp_path, "")
        loader = ExcelLoader()
        requests = loader.load_requests(excel_file)
        assert requests[0].priority == 1

    def test_float_value_raises_error(self, tmp_path: Path) -> None:
        """Test float value raises error (should not silently truncate)."""
        excel_file = self._create_request_excel(tmp_path, 2.5)
        loader = ExcelLoader()
        with pytest.raises(ExcelHandlerError, match="Invalid priority.*2.5"):
            loader.load_requests(excel_file)

    def test_float_string_raises_error(self, tmp_path: Path) -> None:
        """Test float string raises error."""
        excel_file = self._create_request_excel(tmp_path, "2.5")
        loader = ExcelLoader()
        with pytest.raises(ExcelHandlerError, match="Invalid priority.*2.5"):
            loader.load_requests(excel_file)

    def test_non_numeric_string_raises_error(self, tmp_path: Path) -> None:
        """Test non-numeric string raises error."""
        excel_file = self._create_request_excel(tmp_path, "high")
        loader = ExcelLoader()
        with pytest.raises(ExcelHandlerError, match="Invalid priority.*high"):
            loader.load_requests(excel_file)

    def test_negative_raises_error(self, tmp_path: Path) -> None:
        """Test negative priority raises error."""
        excel_file = self._create_request_excel(tmp_path, -1)
        loader = ExcelLoader()
        with pytest.raises(ExcelHandlerError, match="priority must be positive.*-1"):
            loader.load_requests(excel_file)

    def test_zero_raises_error(self, tmp_path: Path) -> None:
        """Test zero priority raises error."""
        excel_file = self._create_request_excel(tmp_path, 0)
        loader = ExcelLoader()
        with pytest.raises(ExcelHandlerError, match="priority must be positive.*0"):
            loader.load_requests(excel_file)

    def test_large_valid_priority(self, tmp_path: Path) -> None:
        """Test very large priority values are accepted."""
        excel_file = self._create_request_excel(tmp_path, 999999)
        loader = ExcelLoader()
        requests = loader.load_requests(excel_file)
        assert requests[0].priority == 999999


class TestPriorityConsistencyBetweenLoaders:
    """Tests that CSV and Excel loaders behave identically for priority handling."""

    @pytest.fixture
    def csv_loader(self) -> CSVLoader:
        return CSVLoader()

    @pytest.fixture
    def excel_loader(self) -> ExcelLoader:
        return ExcelLoader()

    def _create_csv_request(self, tmp_path: Path, priority: str) -> Path:
        """Create CSV request file."""
        csv_file = tmp_path / "requests.csv"
        csv_file.write_text(
            "worker_id,start_date,end_date,request_type,shift_type_id,priority\n"
            f"W001,2026-01-10,2026-01-10,positive,day,{priority}\n"
        )
        return csv_file

    def _create_excel_request(self, tmp_path: Path, priority) -> Path:
        """Create Excel request file."""
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Requests"
        ws.append(
            ["worker_id", "start_date", "end_date", "request_type", "shift_type_id", "priority"]
        )
        ws.append(["W001", date(2026, 1, 10), date(2026, 1, 10), "positive", "day", priority])
        excel_file = tmp_path / "requests.xlsx"
        wb.save(excel_file)
        return excel_file

    def test_valid_integer_consistency(
        self, tmp_path: Path, csv_loader: CSVLoader, excel_loader: ExcelLoader
    ) -> None:
        """Both loaders should accept valid integer priorities."""
        csv_file = self._create_csv_request(tmp_path, "3")
        excel_file = self._create_excel_request(tmp_path, 3)

        csv_result = csv_loader.load_requests(csv_file)[0].priority
        excel_result = excel_loader.load_requests(excel_file)[0].priority

        assert csv_result == excel_result == 3

    def test_default_priority_consistency(
        self, tmp_path: Path, csv_loader: CSVLoader, excel_loader: ExcelLoader
    ) -> None:
        """Both loaders should default to priority 1 for empty/None."""
        csv_file = self._create_csv_request(tmp_path, "")
        excel_file = self._create_excel_request(tmp_path, None)

        csv_result = csv_loader.load_requests(csv_file)[0].priority
        excel_result = excel_loader.load_requests(excel_file)[0].priority

        assert csv_result == excel_result == 1

    def test_negative_rejection_consistency(
        self, tmp_path: Path, csv_loader: CSVLoader, excel_loader: ExcelLoader
    ) -> None:
        """Both loaders should reject negative priorities."""
        csv_file = self._create_csv_request(tmp_path, "-1")
        excel_file = self._create_excel_request(tmp_path, -1)

        with pytest.raises(CSVLoaderError):
            csv_loader.load_requests(csv_file)

        with pytest.raises(ExcelHandlerError):
            excel_loader.load_requests(excel_file)

    def test_zero_rejection_consistency(
        self, tmp_path: Path, csv_loader: CSVLoader, excel_loader: ExcelLoader
    ) -> None:
        """Both loaders should reject zero priority."""
        csv_file = self._create_csv_request(tmp_path, "0")
        excel_file = self._create_excel_request(tmp_path, 0)

        with pytest.raises(CSVLoaderError):
            csv_loader.load_requests(csv_file)

        with pytest.raises(ExcelHandlerError):
            excel_loader.load_requests(excel_file)

    def test_non_numeric_rejection_consistency(
        self, tmp_path: Path, csv_loader: CSVLoader, excel_loader: ExcelLoader
    ) -> None:
        """Both loaders should reject non-numeric priority strings."""
        csv_file = self._create_csv_request(tmp_path, "high")
        excel_file = self._create_excel_request(tmp_path, "high")

        with pytest.raises(CSVLoaderError):
            csv_loader.load_requests(csv_file)

        with pytest.raises(ExcelHandlerError):
            excel_loader.load_requests(excel_file)
