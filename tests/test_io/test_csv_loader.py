"""Tests for CSV loader."""

from datetime import date
from pathlib import Path

import pytest

from shift_solver.io.csv_loader import CSVLoader, CSVLoaderError


class TestCSVLoaderWorkers:
    """Tests for loading workers from CSV."""

    def test_load_workers_basic(self, tmp_path: Path) -> None:
        """Test loading basic worker data."""
        csv_file = tmp_path / "workers.csv"
        csv_file.write_text(
            "id,name,worker_type\n"
            "W001,Alice Smith,full_time\n"
            "W002,Bob Jones,part_time\n"
        )

        loader = CSVLoader()
        workers = loader.load_workers(csv_file)

        assert len(workers) == 2
        assert workers[0].id == "W001"
        assert workers[0].name == "Alice Smith"
        assert workers[0].worker_type == "full_time"
        assert workers[1].id == "W002"

    def test_load_workers_with_restrictions(self, tmp_path: Path) -> None:
        """Test loading workers with restricted shifts."""
        csv_file = tmp_path / "workers.csv"
        csv_file.write_text(
            "id,name,worker_type,restricted_shifts\n"
            'W001,Alice Smith,full_time,"night,weekend"\n'
            "W002,Bob Jones,part_time,\n"
        )

        loader = CSVLoader()
        workers = loader.load_workers(csv_file)

        assert len(workers) == 2
        assert workers[0].restricted_shifts == frozenset({"night", "weekend"})
        assert workers[1].restricted_shifts == frozenset()

    def test_load_workers_minimal_columns(self, tmp_path: Path) -> None:
        """Test loading with only required columns."""
        csv_file = tmp_path / "workers.csv"
        csv_file.write_text("id,name\nW001,Alice\n")

        loader = CSVLoader()
        workers = loader.load_workers(csv_file)

        assert len(workers) == 1
        assert workers[0].id == "W001"
        assert workers[0].name == "Alice"
        assert workers[0].worker_type is None

    def test_load_workers_missing_required_column(self, tmp_path: Path) -> None:
        """Test error when required column is missing."""
        csv_file = tmp_path / "workers.csv"
        csv_file.write_text("id\nW001\n")

        loader = CSVLoader()
        with pytest.raises(CSVLoaderError, match="Missing required column.*name"):
            loader.load_workers(csv_file)

    def test_load_workers_empty_file(self, tmp_path: Path) -> None:
        """Test loading empty file."""
        csv_file = tmp_path / "workers.csv"
        csv_file.write_text("id,name\n")

        loader = CSVLoader()
        workers = loader.load_workers(csv_file)

        assert len(workers) == 0

    def test_load_workers_file_not_found(self, tmp_path: Path) -> None:
        """Test error when file doesn't exist."""
        csv_file = tmp_path / "nonexistent.csv"

        loader = CSVLoader()
        with pytest.raises(CSVLoaderError, match="File not found"):
            loader.load_workers(csv_file)


class TestCSVLoaderAvailability:
    """Tests for loading availability from CSV."""

    def test_load_availability_basic(self, tmp_path: Path) -> None:
        """Test loading basic availability data."""
        csv_file = tmp_path / "availability.csv"
        csv_file.write_text(
            "worker_id,start_date,end_date,availability_type\n"
            "W001,2026-01-10,2026-01-15,unavailable\n"
            "W002,2026-02-01,2026-02-07,preferred\n"
        )

        loader = CSVLoader()
        avails = loader.load_availability(csv_file)

        assert len(avails) == 2
        assert avails[0].worker_id == "W001"
        assert avails[0].start_date == date(2026, 1, 10)
        assert avails[0].end_date == date(2026, 1, 15)
        assert avails[0].availability_type == "unavailable"

    def test_load_availability_with_shift_type(self, tmp_path: Path) -> None:
        """Test loading availability with specific shift type."""
        csv_file = tmp_path / "availability.csv"
        csv_file.write_text(
            "worker_id,start_date,end_date,availability_type,shift_type_id\n"
            "W001,2026-01-10,2026-01-15,unavailable,night\n"
        )

        loader = CSVLoader()
        avails = loader.load_availability(csv_file)

        assert len(avails) == 1
        assert avails[0].shift_type_id == "night"

    def test_load_availability_alternate_date_formats(self, tmp_path: Path) -> None:
        """Test loading with different date formats."""
        csv_file = tmp_path / "availability.csv"
        csv_file.write_text(
            "worker_id,start_date,end_date,availability_type\n"
            "W001,01/10/2026,01/15/2026,unavailable\n"
        )

        loader = CSVLoader()
        avails = loader.load_availability(csv_file)

        assert len(avails) == 1
        assert avails[0].start_date == date(2026, 1, 10)

    def test_load_availability_invalid_date(self, tmp_path: Path) -> None:
        """Test error on invalid date."""
        csv_file = tmp_path / "availability.csv"
        csv_file.write_text(
            "worker_id,start_date,end_date,availability_type\n"
            "W001,not-a-date,2026-01-15,unavailable\n"
        )

        loader = CSVLoader()
        with pytest.raises(CSVLoaderError, match="Invalid date"):
            loader.load_availability(csv_file)


class TestCSVLoaderRequests:
    """Tests for loading scheduling requests from CSV."""

    def test_load_requests_basic(self, tmp_path: Path) -> None:
        """Test loading basic request data."""
        csv_file = tmp_path / "requests.csv"
        csv_file.write_text(
            "worker_id,start_date,end_date,request_type,shift_type_id\n"
            "W001,2026-01-10,2026-01-10,positive,day\n"
            "W002,2026-01-15,2026-01-15,negative,night\n"
        )

        loader = CSVLoader()
        requests = loader.load_requests(csv_file)

        assert len(requests) == 2
        assert requests[0].worker_id == "W001"
        assert requests[0].request_type == "positive"
        assert requests[0].shift_type_id == "day"
        assert requests[1].request_type == "negative"

    def test_load_requests_with_priority(self, tmp_path: Path) -> None:
        """Test loading requests with priority."""
        csv_file = tmp_path / "requests.csv"
        csv_file.write_text(
            "worker_id,start_date,end_date,request_type,shift_type_id,priority\n"
            "W001,2026-01-10,2026-01-10,positive,day,3\n"
        )

        loader = CSVLoader()
        requests = loader.load_requests(csv_file)

        assert len(requests) == 1
        assert requests[0].priority == 3

    def test_load_requests_default_priority(self, tmp_path: Path) -> None:
        """Test default priority when not specified."""
        csv_file = tmp_path / "requests.csv"
        csv_file.write_text(
            "worker_id,start_date,end_date,request_type,shift_type_id\n"
            "W001,2026-01-10,2026-01-10,positive,day\n"
        )

        loader = CSVLoader()
        requests = loader.load_requests(csv_file)

        assert requests[0].priority == 1


class TestCSVLoaderRequestIsHard:
    """Tests for loading requests with is_hard column."""

    def test_load_requests_with_is_hard_true(self, tmp_path: Path) -> None:
        """Test loading request with is_hard=true."""
        csv_file = tmp_path / "requests.csv"
        csv_file.write_text(
            "worker_id,start_date,end_date,request_type,shift_type_id,priority,is_hard\n"
            "W001,2026-01-10,2026-01-10,positive,day,1,true\n"
        )

        loader = CSVLoader()
        requests = loader.load_requests(csv_file)

        assert len(requests) == 1
        assert requests[0].is_hard is True

    def test_load_requests_with_is_hard_false(self, tmp_path: Path) -> None:
        """Test loading request with is_hard=false."""
        csv_file = tmp_path / "requests.csv"
        csv_file.write_text(
            "worker_id,start_date,end_date,request_type,shift_type_id,priority,is_hard\n"
            "W001,2026-01-10,2026-01-10,positive,day,1,false\n"
        )

        loader = CSVLoader()
        requests = loader.load_requests(csv_file)

        assert len(requests) == 1
        assert requests[0].is_hard is False

    def test_load_requests_with_is_hard_empty(self, tmp_path: Path) -> None:
        """Test loading request with is_hard empty (defaults to None)."""
        csv_file = tmp_path / "requests.csv"
        csv_file.write_text(
            "worker_id,start_date,end_date,request_type,shift_type_id,priority,is_hard\n"
            "W001,2026-01-10,2026-01-10,positive,day,1,\n"
        )

        loader = CSVLoader()
        requests = loader.load_requests(csv_file)

        assert len(requests) == 1
        assert requests[0].is_hard is None

    def test_load_requests_without_is_hard_column(self, tmp_path: Path) -> None:
        """Test backward compat - no is_hard column defaults to None."""
        csv_file = tmp_path / "requests.csv"
        csv_file.write_text(
            "worker_id,start_date,end_date,request_type,shift_type_id,priority\n"
            "W001,2026-01-10,2026-01-10,positive,day,1\n"
        )

        loader = CSVLoader()
        requests = loader.load_requests(csv_file)

        assert len(requests) == 1
        assert requests[0].is_hard is None

    def test_load_requests_is_hard_case_insensitive(self, tmp_path: Path) -> None:
        """Test that is_hard parsing is case-insensitive."""
        csv_file = tmp_path / "requests.csv"
        csv_file.write_text(
            "worker_id,start_date,end_date,request_type,shift_type_id,priority,is_hard\n"
            "W001,2026-01-10,2026-01-10,positive,day,1,TRUE\n"
            "W002,2026-01-10,2026-01-10,positive,day,1,False\n"
        )

        loader = CSVLoader()
        requests = loader.load_requests(csv_file)

        assert requests[0].is_hard is True
        assert requests[1].is_hard is False

    def test_load_requests_is_hard_yes_no(self, tmp_path: Path) -> None:
        """Test is_hard with yes/no values."""
        csv_file = tmp_path / "requests.csv"
        csv_file.write_text(
            "worker_id,start_date,end_date,request_type,shift_type_id,priority,is_hard\n"
            "W001,2026-01-10,2026-01-10,positive,day,1,yes\n"
            "W002,2026-01-10,2026-01-10,positive,day,1,no\n"
        )

        loader = CSVLoader()
        requests = loader.load_requests(csv_file)

        assert requests[0].is_hard is True
        assert requests[1].is_hard is False

    def test_load_requests_is_hard_1_0(self, tmp_path: Path) -> None:
        """Test is_hard with 1/0 values."""
        csv_file = tmp_path / "requests.csv"
        csv_file.write_text(
            "worker_id,start_date,end_date,request_type,shift_type_id,priority,is_hard\n"
            "W001,2026-01-10,2026-01-10,positive,day,1,1\n"
            "W002,2026-01-10,2026-01-10,positive,day,1,0\n"
        )

        loader = CSVLoader()
        requests = loader.load_requests(csv_file)

        assert requests[0].is_hard is True
        assert requests[1].is_hard is False

    def test_load_requests_is_hard_invalid(self, tmp_path: Path) -> None:
        """Test error on invalid is_hard value."""
        csv_file = tmp_path / "requests.csv"
        csv_file.write_text(
            "worker_id,start_date,end_date,request_type,shift_type_id,priority,is_hard\n"
            "W001,2026-01-10,2026-01-10,positive,day,1,maybe\n"
        )

        loader = CSVLoader()
        with pytest.raises(CSVLoaderError, match="Invalid is_hard.*maybe.*line 2"):
            loader.load_requests(csv_file)

    def test_load_requests_mixed_is_hard(self, tmp_path: Path) -> None:
        """Test mixed is_hard values in same file."""
        csv_file = tmp_path / "requests.csv"
        csv_file.write_text(
            "worker_id,start_date,end_date,request_type,shift_type_id,priority,is_hard\n"
            "W001,2026-01-10,2026-01-10,negative,night,1,true\n"
            "W001,2026-01-15,2026-01-15,positive,day,2,false\n"
            "W002,2026-01-10,2026-01-10,positive,day,1,\n"
        )

        loader = CSVLoader()
        requests = loader.load_requests(csv_file)

        assert len(requests) == 3
        assert requests[0].is_hard is True
        assert requests[1].is_hard is False
        assert requests[2].is_hard is None


class TestCSVLoaderValidation:
    """Tests for CSV validation and error handling."""

    def test_validates_worker_id_not_empty(self, tmp_path: Path) -> None:
        """Test that empty worker ID raises error."""
        csv_file = tmp_path / "workers.csv"
        csv_file.write_text("id,name\n,Empty Name\n")

        loader = CSVLoader()
        with pytest.raises(CSVLoaderError, match="empty.*id"):
            loader.load_workers(csv_file)

    def test_validates_availability_type(self, tmp_path: Path) -> None:
        """Test that invalid availability type raises error."""
        csv_file = tmp_path / "availability.csv"
        csv_file.write_text(
            "worker_id,start_date,end_date,availability_type\n"
            "W001,2026-01-10,2026-01-15,invalid_type\n"
        )

        loader = CSVLoader()
        with pytest.raises(CSVLoaderError, match="Invalid availability_type"):
            loader.load_availability(csv_file)

    def test_validates_request_type(self, tmp_path: Path) -> None:
        """Test that invalid request type raises error."""
        csv_file = tmp_path / "requests.csv"
        csv_file.write_text(
            "worker_id,start_date,end_date,request_type,shift_type_id\n"
            "W001,2026-01-10,2026-01-10,invalid,day\n"
        )

        loader = CSVLoader()
        with pytest.raises(CSVLoaderError, match="Invalid request_type"):
            loader.load_requests(csv_file)

    def test_reports_line_number_on_error(self, tmp_path: Path) -> None:
        """Test that errors include line number."""
        csv_file = tmp_path / "workers.csv"
        csv_file.write_text("id,name\nW001,Alice\n,Bob\n")

        loader = CSVLoader()
        with pytest.raises(CSVLoaderError, match="line 3"):
            loader.load_workers(csv_file)


class TestCSVLoaderTypeCoercion:
    """Tests for type coercion validation (scheduler-52)."""

    def test_malformed_priority_text(self, tmp_path: Path) -> None:
        """Test error on non-numeric priority value."""
        csv_file = tmp_path / "requests.csv"
        csv_file.write_text(
            "worker_id,start_date,end_date,request_type,shift_type_id,priority\n"
            "W001,2026-01-10,2026-01-10,positive,day,high\n"
        )

        loader = CSVLoader()
        with pytest.raises(CSVLoaderError, match="Invalid priority.*high.*line 2"):
            loader.load_requests(csv_file)

    def test_malformed_priority_float(self, tmp_path: Path) -> None:
        """Test error on float priority value."""
        csv_file = tmp_path / "requests.csv"
        csv_file.write_text(
            "worker_id,start_date,end_date,request_type,shift_type_id,priority\n"
            "W001,2026-01-10,2026-01-10,positive,day,1.5\n"
        )

        loader = CSVLoader()
        with pytest.raises(CSVLoaderError, match="Invalid priority.*1.5.*line 2"):
            loader.load_requests(csv_file)

    def test_malformed_priority_empty_with_comma(self, tmp_path: Path) -> None:
        """Test that empty priority defaults to 1 (valid case)."""
        csv_file = tmp_path / "requests.csv"
        csv_file.write_text(
            "worker_id,start_date,end_date,request_type,shift_type_id,priority\n"
            "W001,2026-01-10,2026-01-10,positive,day,\n"
        )

        loader = CSVLoader()
        requests = loader.load_requests(csv_file)
        assert requests[0].priority == 1

    def test_negative_priority(self, tmp_path: Path) -> None:
        """Test error on negative priority value."""
        csv_file = tmp_path / "requests.csv"
        csv_file.write_text(
            "worker_id,start_date,end_date,request_type,shift_type_id,priority\n"
            "W001,2026-01-10,2026-01-10,positive,day,-1\n"
        )

        loader = CSVLoader()
        with pytest.raises(CSVLoaderError, match="priority must be positive.*-1.*line 2"):
            loader.load_requests(csv_file)
