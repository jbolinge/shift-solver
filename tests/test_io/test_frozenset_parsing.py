"""Tests for frozenset parsing edge cases in CSV and Excel loaders.

These tests verify that restricted_shifts and preferred_shifts are parsed
correctly, especially for edge cases involving empty strings, whitespace,
and malformed comma-separated values.

Issue: scheduler-76
"""

from pathlib import Path

import openpyxl
import pytest

from shift_solver.io.csv_loader import CSVLoader
from shift_solver.io.excel_handler import ExcelLoader


class TestFrozensetParsingCSV:
    """Tests for frozenset parsing in CSV loader."""

    def _create_worker_csv(
        self, tmp_path: Path, restricted: str, preferred: str = ""
    ) -> Path:
        """Helper to create a worker CSV with specific shift values."""
        csv_file = tmp_path / "workers.csv"
        # Use quotes to handle commas in field values
        csv_file.write_text(
            f'id,name,restricted_shifts,preferred_shifts\n'
            f'W001,Alice,"{restricted}","{preferred}"\n'
        )
        return csv_file

    def test_empty_field_returns_empty_frozenset(self, tmp_path: Path) -> None:
        """Empty field should return empty frozenset."""
        csv_file = self._create_worker_csv(tmp_path, "")
        loader = CSVLoader()
        workers = loader.load_workers(csv_file)
        assert workers[0].restricted_shifts == frozenset()

    def test_whitespace_only_returns_empty_frozenset(self, tmp_path: Path) -> None:
        """Whitespace-only field should return empty frozenset."""
        csv_file = self._create_worker_csv(tmp_path, "   ")
        loader = CSVLoader()
        workers = loader.load_workers(csv_file)
        assert workers[0].restricted_shifts == frozenset()

    def test_single_value(self, tmp_path: Path) -> None:
        """Single value should be parsed correctly."""
        csv_file = self._create_worker_csv(tmp_path, "day")
        loader = CSVLoader()
        workers = loader.load_workers(csv_file)
        assert workers[0].restricted_shifts == frozenset({"day"})

    def test_multiple_values(self, tmp_path: Path) -> None:
        """Multiple comma-separated values should be parsed correctly."""
        csv_file = self._create_worker_csv(tmp_path, "day,night")
        loader = CSVLoader()
        workers = loader.load_workers(csv_file)
        assert workers[0].restricted_shifts == frozenset({"day", "night"})

    def test_trailing_comma_ignored(self, tmp_path: Path) -> None:
        """Trailing comma should not add empty string to frozenset."""
        csv_file = self._create_worker_csv(tmp_path, "day,")
        loader = CSVLoader()
        workers = loader.load_workers(csv_file)
        assert workers[0].restricted_shifts == frozenset({"day"})
        assert "" not in workers[0].restricted_shifts

    def test_leading_comma_ignored(self, tmp_path: Path) -> None:
        """Leading comma should not add empty string to frozenset."""
        csv_file = self._create_worker_csv(tmp_path, ",day")
        loader = CSVLoader()
        workers = loader.load_workers(csv_file)
        assert workers[0].restricted_shifts == frozenset({"day"})
        assert "" not in workers[0].restricted_shifts

    def test_multiple_commas_ignored(self, tmp_path: Path) -> None:
        """Multiple consecutive commas should not add empty strings."""
        csv_file = self._create_worker_csv(tmp_path, "day,,night")
        loader = CSVLoader()
        workers = loader.load_workers(csv_file)
        assert workers[0].restricted_shifts == frozenset({"day", "night"})
        assert "" not in workers[0].restricted_shifts

    def test_whitespace_around_values_trimmed(self, tmp_path: Path) -> None:
        """Whitespace around values should be trimmed."""
        csv_file = self._create_worker_csv(tmp_path, " day , night ")
        loader = CSVLoader()
        workers = loader.load_workers(csv_file)
        assert workers[0].restricted_shifts == frozenset({"day", "night"})
        assert " day " not in workers[0].restricted_shifts
        assert " night " not in workers[0].restricted_shifts

    def test_preferred_shifts_same_behavior(self, tmp_path: Path) -> None:
        """Preferred shifts should have same parsing behavior."""
        csv_file = self._create_worker_csv(tmp_path, "", " morning , evening ")
        loader = CSVLoader()
        workers = loader.load_workers(csv_file)
        assert workers[0].preferred_shifts == frozenset({"morning", "evening"})

    def test_both_restricted_and_preferred(self, tmp_path: Path) -> None:
        """Both fields should parse correctly together."""
        csv_file = self._create_worker_csv(tmp_path, "night,weekend", "day,morning")
        loader = CSVLoader()
        workers = loader.load_workers(csv_file)
        assert workers[0].restricted_shifts == frozenset({"night", "weekend"})
        assert workers[0].preferred_shifts == frozenset({"day", "morning"})

    def test_only_commas_returns_empty(self, tmp_path: Path) -> None:
        """Field with only commas should return empty frozenset."""
        csv_file = self._create_worker_csv(tmp_path, ",,,")
        loader = CSVLoader()
        workers = loader.load_workers(csv_file)
        assert workers[0].restricted_shifts == frozenset()

    def test_commas_and_whitespace_returns_empty(self, tmp_path: Path) -> None:
        """Field with only commas and whitespace should return empty frozenset."""
        csv_file = self._create_worker_csv(tmp_path, " , , , ")
        loader = CSVLoader()
        workers = loader.load_workers(csv_file)
        assert workers[0].restricted_shifts == frozenset()


class TestFrozensetParsingExcel:
    """Tests for frozenset parsing in Excel loader."""

    def _create_worker_excel(
        self, tmp_path: Path, restricted, preferred=""
    ) -> Path:
        """Helper to create a worker Excel file with specific shift values."""
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Workers"
        ws.append(["id", "name", "restricted_shifts", "preferred_shifts"])
        ws.append(["W001", "Alice", restricted, preferred])
        excel_file = tmp_path / "workers.xlsx"
        wb.save(excel_file)
        return excel_file

    def test_empty_field_returns_empty_frozenset(self, tmp_path: Path) -> None:
        """Empty field should return empty frozenset."""
        excel_file = self._create_worker_excel(tmp_path, "")
        loader = ExcelLoader()
        workers = loader.load_workers(excel_file)
        assert workers[0].restricted_shifts == frozenset()

    def test_none_returns_empty_frozenset(self, tmp_path: Path) -> None:
        """None value should return empty frozenset."""
        excel_file = self._create_worker_excel(tmp_path, None)
        loader = ExcelLoader()
        workers = loader.load_workers(excel_file)
        assert workers[0].restricted_shifts == frozenset()

    def test_whitespace_only_returns_empty_frozenset(self, tmp_path: Path) -> None:
        """Whitespace-only field should return empty frozenset."""
        excel_file = self._create_worker_excel(tmp_path, "   ")
        loader = ExcelLoader()
        workers = loader.load_workers(excel_file)
        assert workers[0].restricted_shifts == frozenset()

    def test_single_value(self, tmp_path: Path) -> None:
        """Single value should be parsed correctly."""
        excel_file = self._create_worker_excel(tmp_path, "day")
        loader = ExcelLoader()
        workers = loader.load_workers(excel_file)
        assert workers[0].restricted_shifts == frozenset({"day"})

    def test_multiple_values(self, tmp_path: Path) -> None:
        """Multiple comma-separated values should be parsed correctly."""
        excel_file = self._create_worker_excel(tmp_path, "day,night")
        loader = ExcelLoader()
        workers = loader.load_workers(excel_file)
        assert workers[0].restricted_shifts == frozenset({"day", "night"})

    def test_trailing_comma_ignored(self, tmp_path: Path) -> None:
        """Trailing comma should not add empty string to frozenset."""
        excel_file = self._create_worker_excel(tmp_path, "day,")
        loader = ExcelLoader()
        workers = loader.load_workers(excel_file)
        assert workers[0].restricted_shifts == frozenset({"day"})
        assert "" not in workers[0].restricted_shifts

    def test_leading_comma_ignored(self, tmp_path: Path) -> None:
        """Leading comma should not add empty string to frozenset."""
        excel_file = self._create_worker_excel(tmp_path, ",day")
        loader = ExcelLoader()
        workers = loader.load_workers(excel_file)
        assert workers[0].restricted_shifts == frozenset({"day"})
        assert "" not in workers[0].restricted_shifts

    def test_multiple_commas_ignored(self, tmp_path: Path) -> None:
        """Multiple consecutive commas should not add empty strings."""
        excel_file = self._create_worker_excel(tmp_path, "day,,night")
        loader = ExcelLoader()
        workers = loader.load_workers(excel_file)
        assert workers[0].restricted_shifts == frozenset({"day", "night"})
        assert "" not in workers[0].restricted_shifts

    def test_whitespace_around_values_trimmed(self, tmp_path: Path) -> None:
        """Whitespace around values should be trimmed."""
        excel_file = self._create_worker_excel(tmp_path, " day , night ")
        loader = ExcelLoader()
        workers = loader.load_workers(excel_file)
        assert workers[0].restricted_shifts == frozenset({"day", "night"})

    def test_preferred_shifts_same_behavior(self, tmp_path: Path) -> None:
        """Preferred shifts should have same parsing behavior."""
        excel_file = self._create_worker_excel(tmp_path, "", " morning , evening ")
        loader = ExcelLoader()
        workers = loader.load_workers(excel_file)
        assert workers[0].preferred_shifts == frozenset({"morning", "evening"})


class TestFrozensetConsistencyBetweenLoaders:
    """Tests that CSV and Excel loaders parse frozensets identically."""

    @pytest.fixture
    def csv_loader(self) -> CSVLoader:
        return CSVLoader()

    @pytest.fixture
    def excel_loader(self) -> ExcelLoader:
        return ExcelLoader()

    def _create_csv_worker(self, tmp_path: Path, restricted: str) -> Path:
        """Create CSV worker file."""
        csv_file = tmp_path / "workers.csv"
        csv_file.write_text(
            f'id,name,restricted_shifts\n'
            f'W001,Alice,"{restricted}"\n'
        )
        return csv_file

    def _create_excel_worker(self, tmp_path: Path, restricted: str) -> Path:
        """Create Excel worker file."""
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Workers"
        ws.append(["id", "name", "restricted_shifts"])
        ws.append(["W001", "Alice", restricted])
        excel_file = tmp_path / "workers.xlsx"
        wb.save(excel_file)
        return excel_file

    @pytest.mark.parametrize(
        "input_value,expected",
        [
            ("", frozenset()),
            ("   ", frozenset()),
            ("day", frozenset({"day"})),
            ("day,night", frozenset({"day", "night"})),
            ("day,", frozenset({"day"})),
            (",day", frozenset({"day"})),
            ("day,,night", frozenset({"day", "night"})),
            (" day , night ", frozenset({"day", "night"})),
            (",,,", frozenset()),
            (" , , ", frozenset()),
        ],
    )
    def test_consistent_parsing(
        self,
        tmp_path: Path,
        csv_loader: CSVLoader,
        excel_loader: ExcelLoader,
        input_value: str,
        expected: frozenset,
    ) -> None:
        """Both loaders should produce identical results for the same input."""
        csv_file = self._create_csv_worker(tmp_path, input_value)
        excel_file = self._create_excel_worker(tmp_path, input_value)

        csv_result = csv_loader.load_workers(csv_file)[0].restricted_shifts
        excel_result = excel_loader.load_workers(excel_file)[0].restricted_shifts

        assert csv_result == expected, f"CSV: {csv_result} != {expected}"
        assert excel_result == expected, f"Excel: {excel_result} != {expected}"
        assert csv_result == excel_result, f"CSV ({csv_result}) != Excel ({excel_result})"
