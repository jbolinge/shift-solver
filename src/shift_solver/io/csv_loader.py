"""CSV loader for importing worker, availability, and request data."""

import csv
from pathlib import Path

from shift_solver.io.date_utils import parse_date
from shift_solver.models import Availability, SchedulingRequest, Worker
from shift_solver.models.data_models import AVAILABILITY_TYPES, REQUEST_TYPES


class CSVLoaderError(Exception):
    """Error during CSV loading."""

    pass


class CSVLoader:
    """
    Loads scheduling data from CSV files.

    Supports loading:
    - Workers (id, name, worker_type, restricted_shifts)
    - Availability (worker_id, start_date, end_date, availability_type, shift_type_id)
    - Requests (worker_id, start_date, end_date, request_type, shift_type_id, priority)

    Date formats supported:
    - YYYY-MM-DD (ISO format)
    - MM/DD/YYYY (US format)
    - DD/MM/YYYY (EU format, if day > 12)
    """

    def load_workers(self, file_path: Path) -> list[Worker]:
        """
        Load workers from a CSV file.

        Required columns: id, name
        Optional columns: worker_type, restricted_shifts, preferred_shifts

        Args:
            file_path: Path to CSV file

        Returns:
            List of Worker objects

        Raises:
            CSVLoaderError: If file is missing, malformed, or has invalid data
        """
        rows = self._read_csv(file_path)
        self._validate_required_columns(rows, ["id", "name"], file_path)

        workers = []
        for line_num, row in enumerate(rows, start=2):  # +2 for header + 1-indexed
            try:
                worker = self._parse_worker_row(row, line_num)
                workers.append(worker)
            except Exception as e:
                raise CSVLoaderError(f"Error on line {line_num}: {e}") from e

        return workers

    def load_availability(self, file_path: Path) -> list[Availability]:
        """
        Load availability records from a CSV file.

        Required columns: worker_id, start_date, end_date, availability_type
        Optional columns: shift_type_id

        Args:
            file_path: Path to CSV file

        Returns:
            List of Availability objects

        Raises:
            CSVLoaderError: If file is missing, malformed, or has invalid data
        """
        rows = self._read_csv(file_path)
        required = ["worker_id", "start_date", "end_date", "availability_type"]
        self._validate_required_columns(rows, required, file_path)

        availabilities = []
        for line_num, row in enumerate(rows, start=2):
            try:
                avail = self._parse_availability_row(row, line_num)
                availabilities.append(avail)
            except Exception as e:
                raise CSVLoaderError(f"Error on line {line_num}: {e}") from e

        return availabilities

    def load_requests(self, file_path: Path) -> list[SchedulingRequest]:
        """
        Load scheduling requests from a CSV file.

        Required columns: worker_id, start_date, end_date, request_type, shift_type_id
        Optional columns: priority

        Args:
            file_path: Path to CSV file

        Returns:
            List of SchedulingRequest objects

        Raises:
            CSVLoaderError: If file is missing, malformed, or has invalid data
        """
        rows = self._read_csv(file_path)
        required = [
            "worker_id",
            "start_date",
            "end_date",
            "request_type",
            "shift_type_id",
        ]
        self._validate_required_columns(rows, required, file_path)

        requests = []
        for line_num, row in enumerate(rows, start=2):
            try:
                req = self._parse_request_row(row, line_num)
                requests.append(req)
            except Exception as e:
                raise CSVLoaderError(f"Error on line {line_num}: {e}") from e

        return requests

    def _read_csv(self, file_path: Path) -> list[dict[str, str]]:
        """Read CSV file and return list of row dicts."""
        if not file_path.exists():
            raise CSVLoaderError(f"File not found: {file_path}")

        try:
            with open(file_path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                return list(reader)
        except Exception as e:
            raise CSVLoaderError(f"Error reading CSV file {file_path}: {e}") from e

    def _validate_required_columns(
        self, rows: list[dict[str, str]], required: list[str], file_path: Path
    ) -> None:
        """Validate that required columns exist."""
        if not rows:
            return  # Empty file is valid

        columns = set(rows[0].keys())
        for col in required:
            if col not in columns:
                raise CSVLoaderError(
                    f"Missing required column '{col}' in {file_path}. "
                    f"Found columns: {sorted(columns)}"
                )

    def _parse_worker_row(self, row: dict[str, str], line_num: int) -> Worker:
        """Parse a single worker row."""
        worker_id = row.get("id", "").strip()
        name = row.get("name", "").strip()

        if not worker_id:
            raise CSVLoaderError(f"empty 'id' on line {line_num}")
        if not name:
            raise CSVLoaderError(f"empty 'name' on line {line_num}")

        worker_type = row.get("worker_type", "").strip() or None

        # Parse restricted_shifts (comma-separated)
        restricted_str = row.get("restricted_shifts", "").strip()
        restricted_shifts = frozenset(
            s.strip() for s in restricted_str.split(",") if s.strip()
        )

        # Parse preferred_shifts (comma-separated)
        preferred_str = row.get("preferred_shifts", "").strip()
        preferred_shifts = frozenset(
            s.strip() for s in preferred_str.split(",") if s.strip()
        )

        return Worker(
            id=worker_id,
            name=name,
            worker_type=worker_type,
            restricted_shifts=restricted_shifts,
            preferred_shifts=preferred_shifts,
        )

    def _parse_availability_row(
        self, row: dict[str, str], line_num: int
    ) -> Availability:
        """Parse a single availability row."""
        worker_id = row.get("worker_id", "").strip()
        if not worker_id:
            raise CSVLoaderError(f"empty 'worker_id' on line {line_num}")

        start_date = parse_date(
            row.get("start_date", ""), "start_date", line_num, CSVLoaderError
        )
        end_date = parse_date(
            row.get("end_date", ""), "end_date", line_num, CSVLoaderError
        )

        availability_type = row.get("availability_type", "").strip()
        if availability_type not in AVAILABILITY_TYPES:
            raise CSVLoaderError(
                f"Invalid availability_type '{availability_type}' on line {line_num}. "
                f"Must be one of: {AVAILABILITY_TYPES}"
            )

        shift_type_id = row.get("shift_type_id", "").strip() or None

        return Availability(
            worker_id=worker_id,
            start_date=start_date,
            end_date=end_date,
            availability_type=availability_type,  # type: ignore
            shift_type_id=shift_type_id,
        )

    def _parse_request_row(
        self, row: dict[str, str], line_num: int
    ) -> SchedulingRequest:
        """Parse a single request row."""
        worker_id = row.get("worker_id", "").strip()
        if not worker_id:
            raise CSVLoaderError(f"empty 'worker_id' on line {line_num}")

        start_date = parse_date(
            row.get("start_date", ""), "start_date", line_num, CSVLoaderError
        )
        end_date = parse_date(
            row.get("end_date", ""), "end_date", line_num, CSVLoaderError
        )

        request_type = row.get("request_type", "").strip()
        if request_type not in REQUEST_TYPES:
            raise CSVLoaderError(
                f"Invalid request_type '{request_type}' on line {line_num}. "
                f"Must be one of: {REQUEST_TYPES}"
            )

        shift_type_id = row.get("shift_type_id", "").strip()
        if not shift_type_id:
            raise CSVLoaderError(f"empty 'shift_type_id' on line {line_num}")

        priority_str = row.get("priority", "").strip()
        priority = int(priority_str) if priority_str else 1

        return SchedulingRequest(
            worker_id=worker_id,
            start_date=start_date,
            end_date=end_date,
            request_type=request_type,  # type: ignore
            shift_type_id=shift_type_id,
            priority=priority,
        )
