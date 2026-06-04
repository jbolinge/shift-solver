"""Tests for data import views (scheduler-125)."""

import datetime
import io

import pytest
from django.test import Client

from core.models import (
    ScheduleRequest,
    ShiftType,
    Worker,
    WorkerRequest,
)

pytestmark = pytest.mark.django_db


class TestImportPage:
    """Tests for the import page."""

    def test_import_page_returns_200(self, client: Client) -> None:
        """Import page returns HTTP 200."""
        response = client.get("/import/")
        assert response.status_code == 200

    def test_import_page_has_file_upload(self, client: Client) -> None:
        """Import page includes file upload form."""
        response = client.get("/import/")
        content = response.content.decode()
        assert 'type="file"' in content or "upload" in content.lower()


class TestImportUpload:
    """Tests for CSV/Excel file upload."""

    def test_upload_csv_workers(self, client: Client) -> None:
        """Uploading a CSV file with worker data parses correctly."""
        csv_content = "id,name,worker_type\nW1,Alice,full_time\nW2,Bob,part_time\n"
        csv_file = io.BytesIO(csv_content.encode("utf-8"))
        csv_file.name = "workers.csv"

        response = client.post(
            "/import/upload/",
            {"file": csv_file, "data_type": "workers"},
            format="multipart",
        )
        assert response.status_code == 200
        content = response.content.decode()
        assert "Alice" in content
        assert "Bob" in content

    def test_upload_invalid_file_type(self, client: Client) -> None:
        """Uploading unsupported file type returns error."""
        txt_file = io.BytesIO(b"not a csv or excel file")
        txt_file.name = "data.txt"

        response = client.post(
            "/import/upload/",
            {"file": txt_file, "data_type": "workers"},
            format="multipart",
        )
        assert response.status_code == 200
        content = response.content.decode()
        assert "error" in content.lower() or "unsupported" in content.lower()

    def test_upload_preview_shows_parsed_rows(self, client: Client) -> None:
        """Upload preview displays parsed data for confirmation."""
        csv_content = "id,name\nW1,Alice\nW2,Bob\n"
        csv_file = io.BytesIO(csv_content.encode("utf-8"))
        csv_file.name = "workers.csv"

        response = client.post(
            "/import/upload/",
            {"file": csv_file, "data_type": "workers"},
            format="multipart",
        )
        content = response.content.decode()
        # Should show parsed rows in a preview table
        assert "W1" in content
        assert "W2" in content


class TestImportConfirm:
    """Tests for import confirmation."""

    def test_confirm_import_creates_workers(self, client: Client) -> None:
        """Confirming import creates worker records in database."""
        # First upload to get preview
        csv_content = "id,name,worker_type\nW10,TestAlice,full_time\nW11,TestBob,part_time\n"
        csv_file = io.BytesIO(csv_content.encode("utf-8"))
        csv_file.name = "workers.csv"

        client.post(
            "/import/upload/",
            {"file": csv_file, "data_type": "workers"},
            format="multipart",
        )

        # Now confirm
        client.post(
            "/import/confirm/",
            {"data_type": "workers"},
        )

        assert Worker.objects.filter(worker_id="W10").exists()
        assert Worker.objects.filter(worker_id="W11").exists()

    def test_confirm_import_skips_invalid_rows(self, client: Client) -> None:
        """Invalid rows are skipped during import - duplicate IDs."""
        # Create an existing worker
        Worker.objects.create(worker_id="EXIST", name="Existing")

        csv_content = "id,name\nEXIST,Duplicate\nW20,NewWorker\n"
        csv_file = io.BytesIO(csv_content.encode("utf-8"))
        csv_file.name = "workers.csv"

        client.post(
            "/import/upload/",
            {"file": csv_file, "data_type": "workers"},
            format="multipart",
        )

        client.post(
            "/import/confirm/",
            {"data_type": "workers"},
        )

        # New worker created, existing not duplicated
        assert Worker.objects.filter(worker_id="W20").exists()
        assert Worker.objects.filter(worker_id="EXIST").count() == 1


class TestImportRequestsTarget:
    """Worker-request import routes into the selected ScheduleRequest."""

    def _setup(self) -> tuple[ScheduleRequest, ScheduleRequest]:
        Worker.objects.create(worker_id="W1", name="Alice")
        ShiftType.objects.create(
            shift_type_id="DAY",
            name="Day",
            start_time=datetime.time(7, 0),
            duration_hours=8.0,
        )
        older = ScheduleRequest.objects.create(
            name="Older",
            start_date=datetime.date(2026, 3, 1),
            end_date=datetime.date(2026, 3, 7),
        )
        newer = ScheduleRequest.objects.create(
            name="Newer",
            start_date=datetime.date(2026, 4, 1),
            end_date=datetime.date(2026, 4, 7),
        )
        return older, newer

    def _upload_requests(self, client: Client) -> None:
        csv_content = (
            "worker_id,start_date,end_date,request_type,shift_type_id,priority\n"
            "W1,2026-03-02,2026-03-02,negative,DAY,2\n"
        )
        csv_file = io.BytesIO(csv_content.encode("utf-8"))
        csv_file.name = "requests.csv"
        client.post(
            "/import/upload/",
            {"file": csv_file, "data_type": "requests"},
            format="multipart",
        )

    def test_preview_lists_target_requests(self, client: Client) -> None:
        """The preview offers a selector listing existing schedule requests."""
        self._setup()
        self._upload_requests(client)
        # Re-upload returns the preview response directly.
        csv_content = (
            "worker_id,start_date,end_date,request_type,shift_type_id,priority\n"
            "W1,2026-03-02,2026-03-02,negative,DAY,2\n"
        )
        csv_file = io.BytesIO(csv_content.encode("utf-8"))
        csv_file.name = "requests.csv"
        response = client.post(
            "/import/upload/",
            {"file": csv_file, "data_type": "requests"},
            format="multipart",
        )
        content = response.content.decode()
        assert "target_request_id" in content
        assert "Older" in content and "Newer" in content

    def test_confirm_imports_into_selected_request(self, client: Client) -> None:
        """The chosen request receives the rows, not the most recent one."""
        older, _newer = self._setup()
        self._upload_requests(client)
        client.post(
            "/import/confirm/",
            {"data_type": "requests", "target_request_id": str(older.pk)},
        )
        assert WorkerRequest.objects.filter(schedule_request=older).count() == 1
        assert WorkerRequest.objects.filter(schedule_request=_newer).count() == 0

    def test_confirm_falls_back_to_latest_when_unspecified(
        self, client: Client
    ) -> None:
        """With no target chosen, the most recent request is used."""
        _older, newer = self._setup()
        self._upload_requests(client)
        client.post("/import/confirm/", {"data_type": "requests"})
        assert WorkerRequest.objects.filter(schedule_request=newer).count() == 1
