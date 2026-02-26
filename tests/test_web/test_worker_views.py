"""Tests for Worker CRUD views with HTMX support (scheduler-115)."""

import pytest
from django.test import Client

from core.models import Worker

pytestmark = pytest.mark.django_db


class TestWorkerListView:
    """Tests for the worker list view."""

    def test_worker_list_returns_200(self, client: Client) -> None:
        """GET /workers/ returns HTTP 200."""
        response = client.get("/workers/")
        assert response.status_code == 200

    def test_worker_list_shows_all_workers(self, client: Client) -> None:
        """Worker list displays all workers in the database."""
        Worker.objects.create(worker_id="W1", name="Alice Smith")
        Worker.objects.create(worker_id="W2", name="Bob Jones")
        Worker.objects.create(worker_id="W3", name="Carol White")

        response = client.get("/workers/")
        content = response.content.decode()

        assert "Alice Smith" in content
        assert "Bob Jones" in content
        assert "Carol White" in content

    def test_worker_list_shows_empty_state(self, client: Client) -> None:
        """Worker list shows an empty state message when no workers exist."""
        response = client.get("/workers/")
        content = response.content.decode()

        assert "No workers found" in content


class TestWorkerCreateView:
    """Tests for the worker create view."""

    def test_create_worker_get_returns_form(self, client: Client) -> None:
        """GET /workers/create/ returns a form."""
        response = client.get("/workers/create/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "<form" in content

    def test_create_worker_post_valid_data(self, client: Client) -> None:
        """POST /workers/create/ with valid data creates a worker."""
        data = {
            "worker_id": "W1",
            "name": "Alice Smith",
            "email": "alice@example.com",
            "group": "Team A",
            "worker_type": "full_time",
            "fte": "1.0",
            "is_active": "on",
        }
        response = client.post("/workers/create/", data)

        assert Worker.objects.count() == 1
        worker = Worker.objects.first()
        assert worker is not None
        assert worker.name == "Alice Smith"
        assert worker.email == "alice@example.com"
        assert worker.group == "Team A"
        # Non-HTMX should redirect to list
        assert response.status_code == 302

    def test_create_worker_post_invalid_data(self, client: Client) -> None:
        """POST /workers/create/ with invalid data returns form with errors."""
        data = {
            "worker_id": "",  # required field
            "name": "",  # required field
        }
        response = client.post("/workers/create/", data)

        assert response.status_code == 200
        assert Worker.objects.count() == 0
        content = response.content.decode()
        # Form should be re-rendered with errors
        assert "<form" in content

    def test_htmx_create_post_returns_partial(self, client: Client) -> None:
        """HTMX POST /workers/create/ returns a partial row, not a full page."""
        data = {
            "worker_id": "W1",
            "name": "Alice Smith",
            "email": "alice@example.com",
            "fte": "1.0",
            "is_active": "on",
        }
        response = client.post(
            "/workers/create/",
            data,
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code == 200
        content = response.content.decode()
        # Should return a table row partial, not a full HTML page
        assert "<tr" in content
        assert "<!DOCTYPE" not in content
        assert "Alice Smith" in content


class TestWorkerUpdateView:
    """Tests for the worker update view."""

    def test_update_worker_get_returns_prefilled_form(
        self, client: Client
    ) -> None:
        """GET /workers/<pk>/edit/ returns a form pre-filled with worker data."""
        worker = Worker.objects.create(
            worker_id="W1",
            name="Alice Smith",
            email="alice@example.com",
            group="Team A",
        )
        response = client.get(f"/workers/{worker.pk}/edit/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "<form" in content
        assert "Alice Smith" in content
        assert "alice@example.com" in content

    def test_update_worker_post_updates_worker(self, client: Client) -> None:
        """POST /workers/<pk>/edit/ updates the worker's data."""
        worker = Worker.objects.create(
            worker_id="W1",
            name="Alice Smith",
            email="alice@example.com",
            fte=1.0,
            is_active=True,
        )
        data = {
            "worker_id": "W1",
            "name": "Alice Johnson",
            "email": "alice.j@example.com",
            "fte": "0.8",
            "is_active": "on",
        }
        response = client.post(f"/workers/{worker.pk}/edit/", data)

        worker.refresh_from_db()
        assert worker.name == "Alice Johnson"
        assert worker.email == "alice.j@example.com"
        assert worker.fte == 0.8
        assert response.status_code == 302


class TestWorkerDeleteView:
    """Tests for the worker delete view."""

    def test_delete_worker_removes_from_db(self, client: Client) -> None:
        """POST /workers/<pk>/delete/ removes the worker from the database."""
        worker = Worker.objects.create(worker_id="W1", name="Alice Smith")
        response = client.post(f"/workers/{worker.pk}/delete/")

        assert Worker.objects.count() == 0
        assert response.status_code == 302

    def test_htmx_delete_returns_empty_response(self, client: Client) -> None:
        """HTMX DELETE returns empty content for row removal."""
        worker = Worker.objects.create(worker_id="W1", name="Alice Smith")
        response = client.post(
            f"/workers/{worker.pk}/delete/",
            HTTP_HX_REQUEST="true",
        )

        assert Worker.objects.count() == 0
        assert response.status_code == 200
        assert response.content == b""
