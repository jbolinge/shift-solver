"""Tests for Worker CRUD views with HTMX support (scheduler-115)."""

import json

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


class TestWorkerFormJsonFields:
    """Tests for restricted_shifts, preferred_shifts, attributes JSON fields."""

    def test_create_worker_with_restricted_shifts(self, client: Client) -> None:
        """JSON list of restricted shifts saves correctly."""
        data = {
            "worker_id": "W1",
            "name": "Alice",
            "fte": "1.0",
            "is_active": "on",
            "restricted_shifts": '["night", "weekend"]',
            "preferred_shifts": "[]",
            "attributes": "{}",
        }
        client.post("/workers/create/", data)
        worker = Worker.objects.get(worker_id="W1")
        assert worker.restricted_shifts == ["night", "weekend"]

    def test_create_worker_with_preferred_shifts(self, client: Client) -> None:
        """JSON list of preferred shifts saves correctly."""
        data = {
            "worker_id": "W1",
            "name": "Alice",
            "fte": "1.0",
            "is_active": "on",
            "restricted_shifts": "[]",
            "preferred_shifts": '["day", "morning"]',
            "attributes": "{}",
        }
        client.post("/workers/create/", data)
        worker = Worker.objects.get(worker_id="W1")
        assert worker.preferred_shifts == ["day", "morning"]

    def test_create_worker_with_attributes(self, client: Client) -> None:
        """JSON dict of attributes saves correctly."""
        data = {
            "worker_id": "W1",
            "name": "Alice",
            "fte": "1.0",
            "is_active": "on",
            "restricted_shifts": "[]",
            "preferred_shifts": "[]",
            "attributes": '{"specialty": "cardiology"}',
        }
        client.post("/workers/create/", data)
        worker = Worker.objects.get(worker_id="W1")
        assert worker.attributes == {"specialty": "cardiology"}

    def test_restricted_shifts_rejects_invalid_json(self, client: Client) -> None:
        """Form error on bad JSON for restricted_shifts."""
        data = {
            "worker_id": "W1",
            "name": "Alice",
            "fte": "1.0",
            "is_active": "on",
            "restricted_shifts": "not json",
            "preferred_shifts": "[]",
            "attributes": "{}",
        }
        response = client.post("/workers/create/", data)
        assert response.status_code == 200  # re-rendered form
        assert Worker.objects.count() == 0

    def test_restricted_shifts_rejects_non_list(self, client: Client) -> None:
        """Form error when restricted_shifts is a dict instead of list."""
        data = {
            "worker_id": "W1",
            "name": "Alice",
            "fte": "1.0",
            "is_active": "on",
            "restricted_shifts": '{"not": "a list"}',
            "preferred_shifts": "[]",
            "attributes": "{}",
        }
        response = client.post("/workers/create/", data)
        assert response.status_code == 200
        assert Worker.objects.count() == 0

    def test_attributes_rejects_non_dict(self, client: Client) -> None:
        """Form error when attributes is a list instead of dict."""
        data = {
            "worker_id": "W1",
            "name": "Alice",
            "fte": "1.0",
            "is_active": "on",
            "restricted_shifts": "[]",
            "preferred_shifts": "[]",
            "attributes": '["not", "a dict"]',
        }
        response = client.post("/workers/create/", data)
        assert response.status_code == 200
        assert Worker.objects.count() == 0

    def test_empty_json_fields_default_gracefully(self, client: Client) -> None:
        """Empty JSON fields default to [] or {}."""
        data = {
            "worker_id": "W1",
            "name": "Alice",
            "fte": "1.0",
            "is_active": "on",
            "restricted_shifts": "",
            "preferred_shifts": "",
            "attributes": "",
        }
        client.post("/workers/create/", data)
        worker = Worker.objects.get(worker_id="W1")
        assert worker.restricted_shifts == []
        assert worker.preferred_shifts == []
        assert worker.attributes == {}

    def test_update_preserves_json_fields(self, client: Client) -> None:
        """JSON fields are pre-populated on edit form."""
        worker = Worker.objects.create(
            worker_id="W1",
            name="Alice",
            fte=1.0,
            is_active=True,
            restricted_shifts=["night"],
            preferred_shifts=["day"],
            attributes={"level": "senior"},
        )
        response = client.get(f"/workers/{worker.pk}/edit/")
        content = response.content.decode()
        assert "night" in content
        assert "day" in content
        assert "senior" in content
