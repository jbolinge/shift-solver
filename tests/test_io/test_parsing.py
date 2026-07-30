"""Tests for shift_solver.io.parsing: shared cell parsers and loader dispatch."""

from pathlib import Path

import pytest

from shift_solver.io.csv_loader import CSVLoader, CSVLoaderError
from shift_solver.io.excel_handler import ExcelLoader
from shift_solver.io.parsing import (
    is_excel_path,
    make_loader,
    parse_attributes,
    parse_is_hard,
)


class ExampleError(Exception):
    """Test exception class."""

    pass


class TestParseIsHard:
    """Tests for the shared parse_is_hard helper."""

    @pytest.mark.parametrize("value", ["true", "True", "TRUE", "yes", "Yes", "1"])
    def test_truthy_values(self, value: str) -> None:
        assert parse_is_hard(value, 1, ExampleError) is True

    @pytest.mark.parametrize("value", ["false", "False", "FALSE", "no", "No", "0"])
    def test_falsy_values(self, value: str) -> None:
        assert parse_is_hard(value, 1, ExampleError) is False

    @pytest.mark.parametrize("value", [None, "", "  "])
    def test_empty_is_none(self, value: str | None) -> None:
        assert parse_is_hard(value, 1, ExampleError) is None

    def test_invalid_value_raises(self) -> None:
        with pytest.raises(ExampleError, match="Invalid is_hard value"):
            parse_is_hard("maybe", 5, ExampleError)

    def test_non_string_bool_from_excel_cell(self) -> None:
        """Excel cells can carry native bools, not just strings."""
        assert parse_is_hard(True, 1, ExampleError) is True
        assert parse_is_hard(False, 1, ExampleError) is False


class TestParseAttributes:
    """Tests for the shared parse_attributes helper."""

    def test_single_pair(self) -> None:
        assert parse_attributes("certification=icu", 1, ExampleError) == {
            "certification": "icu"
        }

    def test_multiple_pairs(self) -> None:
        result = parse_attributes("certification=icu;seniority=senior", 1, ExampleError)
        assert result == {"certification": "icu", "seniority": "senior"}

    def test_whitespace_stripped(self) -> None:
        result = parse_attributes(
            " certification = icu ; seniority = senior ", 1, ExampleError
        )
        assert result == {"certification": "icu", "seniority": "senior"}

    @pytest.mark.parametrize("value", [None, "", "   "])
    def test_empty_yields_empty_dict(self, value: str | None) -> None:
        assert parse_attributes(value, 1, ExampleError) == {}

    def test_missing_equals_raises(self) -> None:
        with pytest.raises(ExampleError, match="Invalid attributes entry"):
            parse_attributes("not-a-pair", 1, ExampleError)

    def test_empty_key_raises(self) -> None:
        with pytest.raises(ExampleError, match="empty key"):
            parse_attributes("=icu", 1, ExampleError)


class TestIsExcelPath:
    """Tests for the suffix-based Excel detection."""

    @pytest.mark.parametrize("suffix", [".xlsx", ".xls", ".XLSX", ".Xls"])
    def test_excel_suffixes(self, suffix: str) -> None:
        assert is_excel_path(Path(f"data{suffix}")) is True

    @pytest.mark.parametrize("suffix", [".csv", ".CSV", ".txt", ""])
    def test_non_excel_suffixes(self, suffix: str) -> None:
        assert is_excel_path(Path(f"data{suffix}")) is False


class TestMakeLoader:
    """Tests for the suffix-based loader dispatch."""

    def test_xlsx_dispatches_to_excel_loader(self, tmp_path: Path) -> None:
        loader = make_loader(tmp_path / "workers.xlsx")
        assert isinstance(loader, ExcelLoader)

    def test_xls_dispatches_to_excel_loader(self, tmp_path: Path) -> None:
        loader = make_loader(tmp_path / "workers.xls")
        assert isinstance(loader, ExcelLoader)

    def test_legacy_xls_rejected_with_actionable_error(
        self, tmp_path: Path
    ) -> None:
        """openpyxl can't read binary .xls: fail with 'save as .xlsx', not
        openpyxl's own xlrd recommendation (a library the project doesn't
        ship) or an uncaught traceback."""
        from shift_solver.io.excel_handler.exceptions import ExcelHandlerError

        xls_path = tmp_path / "workers.xls"
        xls_path.write_bytes(b"\xd0\xcf\x11\xe0legacy-biff-junk")

        loader = make_loader(xls_path)
        with pytest.raises(ExcelHandlerError, match="save it as .xlsx"):
            loader.load_workers(xls_path)
        with pytest.raises(ExcelHandlerError, match="save it as .xlsx"):
            loader.load_all(xls_path)

    def test_csv_dispatches_to_csv_loader(self, tmp_path: Path) -> None:
        loader = make_loader(tmp_path / "workers.csv")
        assert isinstance(loader, CSVLoader)

    def test_unknown_suffix_dispatches_to_csv_loader(self, tmp_path: Path) -> None:
        """Everything that isn't Excel is treated as CSV (matches prior default)."""
        loader = make_loader(tmp_path / "workers.txt")
        assert isinstance(loader, CSVLoader)

    def test_date_format_forwarded(self, tmp_path: Path) -> None:
        csv_loader = make_loader(tmp_path / "a.csv", date_format="eu")
        excel_loader = make_loader(tmp_path / "a.xlsx", date_format="eu")
        assert csv_loader._date_format == "eu"
        assert excel_loader._date_format == "eu"

    def test_xlsx_loader_actually_reads_excel(self, tmp_path: Path) -> None:
        """Sanity check: dispatching on a real .xlsx file loads without a
        CSVLoaderError (previously .xlsx paths given to CSVLoader would fail
        since it isn't a CSV file)."""
        import openpyxl

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Workers"
        ws.append(["id", "name"])
        ws.append(["worker_1", "Worker One"])
        excel_file = tmp_path / "workers.xlsx"
        wb.save(excel_file)

        loader = make_loader(excel_file)
        workers = loader.load_workers(excel_file)
        assert workers[0].id == "worker_1"

    def test_csv_path_with_xlsx_dispatch_would_fail_as_csv(
        self, tmp_path: Path
    ) -> None:
        """Sanity check the opposite failure mode doesn't regress: a genuine
        CSV routed through make_loader is read as CSV, not Excel."""
        csv_file = tmp_path / "workers.csv"
        csv_file.write_text("id,name\nworker_1,Worker One\n")

        loader = make_loader(csv_file)
        workers = loader.load_workers(csv_file)
        assert workers[0].id == "worker_1"

    def test_bad_csv_via_dispatch_raises_csv_error(self, tmp_path: Path) -> None:
        csv_file = tmp_path / "workers.csv"
        csv_file.write_text("id\nworker_1\n")  # missing required 'name'

        loader = make_loader(csv_file)
        with pytest.raises(CSVLoaderError):
            loader.load_workers(csv_file)
