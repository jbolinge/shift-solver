"""Tests for Availability calendar views with FullCalendar + HTMX (scheduler-118)."""

import json

import pytest
from django.test import Client

from core.models import Availability, Worker

pytestmark = pytest.mark.django_db


class TestAvailabilityPage:
    """Tests for the availability calendar page."""

    def test_availability_page_returns_200(self, client: Client) -> None:
        """GET /availability/ returns HTTP 200."""
        response = client.get("/availability/")
        assert response.status_code == 200

    def test_availability_page_includes_fullcalendar(
        self, client: Client
    ) -> None:
        """Page includes the FullCalendar library reference."""
        response = client.get("/availability/")
        content = response.content.decode()
        assert "fullcalendar" in content.lower()

    def test_availability_page_has_worker_selector(
        self, client: Client
    ) -> None:
        """Page includes worker names in a selector dropdown."""
        Worker.objects.create(worker_id="W1", name="Alice Smith")
        Worker.objects.create(worker_id="W2", name="Bob Jones")

        response = client.get("/availability/")
        content = response.content.decode()

        assert "Alice Smith" in content
        assert "Bob Jones" in content
        assert "<select" in content


class TestAvailabilityEventsEndpoint:
    """Tests for the availability events JSON endpoint."""

    def test_events_returns_json(self, client: Client) -> None:
        """GET /availability/events/?worker_id=X returns a JSON array."""
        worker = Worker.objects.create(worker_id="W1", name="Alice Smith")
        Availability.objects.create(
            worker=worker, date="2026-03-01", is_available=False
        )

        response = client.get(
            "/availability/events/", {"worker_id": worker.pk}
        )
        assert response.status_code == 200
        assert response["Content-Type"] == "application/json"

        data = json.loads(response.content)
        assert isinstance(data, list)
        assert len(data) == 1

    def test_events_filtered_by_worker(self, client: Client) -> None:
        """Only returns unavailable events for the requested worker."""
        alice = Worker.objects.create(worker_id="W1", name="Alice Smith")
        bob = Worker.objects.create(worker_id="W2", name="Bob Jones")

        Availability.objects.create(
            worker=alice, date="2026-03-01", is_available=False
        )
        Availability.objects.create(
            worker=bob, date="2026-03-02", is_available=False
        )

        response = client.get(
            "/availability/events/", {"worker_id": alice.pk}
        )
        data = json.loads(response.content)

        assert len(data) == 1
        assert data[0]["start"] == "2026-03-01"

    def test_events_only_include_unavailable(self, client: Client) -> None:
        """Available entries are omitted; unavailable entries are red (#ef4444)."""
        worker = Worker.objects.create(worker_id="W1", name="Alice Smith")
        Availability.objects.create(
            worker=worker, date="2026-03-01", is_available=True
        )
        Availability.objects.create(
            worker=worker, date="2026-03-02", is_available=False
        )

        response = client.get(
            "/availability/events/", {"worker_id": worker.pk}
        )
        data = json.loads(response.content)

        events_by_date = {e["start"]: e for e in data}
        assert "2026-03-01" not in events_by_date
        assert events_by_date["2026-03-02"]["color"] == "#ef4444"


class TestAvailabilityUpdate:
    """Tests for the availability create/toggle endpoint."""

    def test_update_creates_availability(self, client: Client) -> None:
        """POST /availability/update/ creates a new availability record."""
        worker = Worker.objects.create(worker_id="W1", name="Alice Smith")

        response = client.post(
            "/availability/update/",
            {"worker_id": worker.pk, "date": "2026-03-01"},
        )
        assert response.status_code == 200

        avail = Availability.objects.get(worker=worker, date="2026-03-01")
        assert avail.is_available is True

    def test_update_toggles_existing(self, client: Client) -> None:
        """POST toggles is_available on an existing availability record."""
        worker = Worker.objects.create(worker_id="W1", name="Alice Smith")
        Availability.objects.create(
            worker=worker, date="2026-03-01", is_available=True
        )

        response = client.post(
            "/availability/update/",
            {"worker_id": worker.pk, "date": "2026-03-01"},
        )
        assert response.status_code == 200

        avail = Availability.objects.get(worker=worker, date="2026-03-01")
        assert avail.is_available is False

    def test_update_requires_worker_id(self, client: Client) -> None:
        """POST without worker_id returns 400."""
        response = client.post(
            "/availability/update/",
            {"date": "2026-03-01"},
        )
        assert response.status_code == 400
