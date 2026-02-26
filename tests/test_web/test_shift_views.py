"""Tests for ShiftType CRUD views with HTMX support."""

import json

import pytest
from django.test import Client

from core.models import ShiftType

pytestmark = pytest.mark.django_db


class TestShiftListView:
    """Tests for the shift type list view."""

    def test_shift_list_returns_200(self, client: Client) -> None:
        """GET /shifts/ returns HTTP 200."""
        response = client.get("/shifts/")
        assert response.status_code == 200

    def test_shift_list_shows_all_types(self, client: Client) -> None:
        """Shift list displays all shift types in the database."""
        ShiftType.objects.create(
            shift_type_id="DAY",
            name="Day Shift",
            start_time="07:00",
            duration_hours=8.0,
        )
        ShiftType.objects.create(
            shift_type_id="EVE",
            name="Evening Shift",
            start_time="15:00",
            duration_hours=8.0,
        )
        ShiftType.objects.create(
            shift_type_id="NIGHT",
            name="Night Shift",
            start_time="23:00",
            duration_hours=8.0,
        )

        response = client.get("/shifts/")
        content = response.content.decode()

        assert "Day Shift" in content
        assert "Evening Shift" in content
        assert "Night Shift" in content

    def test_shift_list_shows_empty_state(self, client: Client) -> None:
        """Shift list shows an empty state message when no shift types exist."""
        response = client.get("/shifts/")
        content = response.content.decode()

        assert "No shift types found" in content


class TestShiftCreateView:
    """Tests for the shift type create view."""

    def test_create_shift_get_returns_form(self, client: Client) -> None:
        """GET /shifts/create/ returns a form."""
        response = client.get("/shifts/create/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "<form" in content

    def test_create_shift_post_valid_data(self, client: Client) -> None:
        """POST /shifts/create/ with valid data creates a shift type."""
        data = {
            "shift_type_id": "DAY",
            "name": "Day Shift",
            "category": "Regular",
            "start_time": "07:00",
            "duration_hours": "8.0",
            "min_workers": "1",
            "max_workers": "5",
            "workers_required": "2",
            "is_active": "on",
        }
        response = client.post("/shifts/create/", data)

        assert ShiftType.objects.count() == 1
        shift = ShiftType.objects.first()
        assert shift is not None
        assert shift.name == "Day Shift"
        assert shift.category == "Regular"
        assert shift.duration_hours == 8.0
        assert shift.workers_required == 2
        # Non-HTMX should redirect to list
        assert response.status_code == 302

    def test_create_shift_post_invalid_data(self, client: Client) -> None:
        """POST /shifts/create/ with invalid data returns form with errors."""
        data = {
            "shift_type_id": "",  # required field
            "name": "",  # required field
        }
        response = client.post("/shifts/create/", data)

        assert response.status_code == 200
        assert ShiftType.objects.count() == 0
        content = response.content.decode()
        # Form should be re-rendered with errors
        assert "<form" in content

    def test_htmx_create_post_returns_partial(self, client: Client) -> None:
        """HTMX POST /shifts/create/ returns a partial row, not a full page."""
        data = {
            "shift_type_id": "DAY",
            "name": "Day Shift",
            "start_time": "07:00",
            "duration_hours": "8.0",
            "min_workers": "1",
            "workers_required": "1",
            "is_active": "on",
        }
        response = client.post(
            "/shifts/create/",
            data,
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code == 200
        content = response.content.decode()
        # Should return a table row partial, not a full HTML page
        assert "<tr" in content
        assert "<!DOCTYPE" not in content
        assert "Day Shift" in content


class TestShiftUpdateView:
    """Tests for the shift type update view."""

    def test_update_shift_get_returns_prefilled_form(
        self, client: Client
    ) -> None:
        """GET /shifts/<pk>/edit/ returns a form pre-filled with shift data."""
        shift = ShiftType.objects.create(
            shift_type_id="DAY",
            name="Day Shift",
            start_time="07:00",
            duration_hours=8.0,
        )
        response = client.get(f"/shifts/{shift.pk}/edit/")
        assert response.status_code == 200
        content = response.content.decode()
        assert "<form" in content
        assert "Day Shift" in content

    def test_update_shift_post_updates_shift(self, client: Client) -> None:
        """POST /shifts/<pk>/edit/ updates the shift type's data."""
        shift = ShiftType.objects.create(
            shift_type_id="DAY",
            name="Day Shift",
            start_time="07:00",
            duration_hours=8.0,
            min_workers=1,
            workers_required=1,
            is_active=True,
        )
        data = {
            "shift_type_id": "DAY",
            "name": "Morning Shift",
            "start_time": "06:00",
            "duration_hours": "10.0",
            "min_workers": "2",
            "workers_required": "3",
            "is_active": "on",
        }
        response = client.post(f"/shifts/{shift.pk}/edit/", data)

        shift.refresh_from_db()
        assert shift.name == "Morning Shift"
        assert shift.duration_hours == 10.0
        assert shift.workers_required == 3
        assert response.status_code == 302


class TestShiftDeleteView:
    """Tests for the shift type delete view."""

    def test_delete_shift_removes_from_db(self, client: Client) -> None:
        """POST /shifts/<pk>/delete/ removes the shift type from the database."""
        shift = ShiftType.objects.create(
            shift_type_id="DAY",
            name="Day Shift",
            start_time="07:00",
            duration_hours=8.0,
        )
        response = client.post(f"/shifts/{shift.pk}/delete/")

        assert ShiftType.objects.count() == 0
        assert response.status_code == 302

    def test_htmx_delete_returns_empty_response(self, client: Client) -> None:
        """HTMX DELETE returns empty content for row removal."""
        shift = ShiftType.objects.create(
            shift_type_id="DAY",
            name="Day Shift",
            start_time="07:00",
            duration_hours=8.0,
        )
        response = client.post(
            f"/shifts/{shift.pk}/delete/",
            HTTP_HX_REQUEST="true",
        )

        assert ShiftType.objects.count() == 0
        assert response.status_code == 200
        assert response.content == b""


class TestShiftTypeFormNewFields:
    """Tests for applicable_days and required_attributes fields."""

    def test_create_shift_with_applicable_days(self, client: Client) -> None:
        """Mon-Fri checkboxes save as [0,1,2,3,4]."""
        data = {
            "shift_type_id": "DAY",
            "name": "Day Shift",
            "start_time": "07:00",
            "duration_hours": "8.0",
            "min_workers": "1",
            "workers_required": "1",
            "is_active": "on",
            "applicable_days": ["0", "1", "2", "3", "4"],
            "required_attributes": "{}",
        }
        response = client.post("/shifts/create/", data)
        assert response.status_code == 302
        shift = ShiftType.objects.get(shift_type_id="DAY")
        assert shift.applicable_days == [0, 1, 2, 3, 4]

    def test_create_shift_with_required_attributes(self, client: Client) -> None:
        """JSON dict of required_attributes saves correctly."""
        data = {
            "shift_type_id": "SPEC",
            "name": "Specialist Shift",
            "start_time": "07:00",
            "duration_hours": "8.0",
            "min_workers": "1",
            "workers_required": "1",
            "is_active": "on",
            "required_attributes": '{"specialty": "cardiology"}',
        }
        response = client.post("/shifts/create/", data)
        assert response.status_code == 302
        shift = ShiftType.objects.get(shift_type_id="SPEC")
        assert shift.required_attributes == {"specialty": "cardiology"}

    def test_applicable_days_empty_saves_null(self, client: Client) -> None:
        """No day selection saves as None (all days)."""
        data = {
            "shift_type_id": "DAY",
            "name": "Day Shift",
            "start_time": "07:00",
            "duration_hours": "8.0",
            "min_workers": "1",
            "workers_required": "1",
            "is_active": "on",
            "required_attributes": "{}",
        }
        response = client.post("/shifts/create/", data)
        assert response.status_code == 302
        shift = ShiftType.objects.get(shift_type_id="DAY")
        assert shift.applicable_days is None

    def test_required_attributes_rejects_non_dict(self, client: Client) -> None:
        """Form error when required_attributes is a list instead of dict."""
        data = {
            "shift_type_id": "DAY",
            "name": "Day Shift",
            "start_time": "07:00",
            "duration_hours": "8.0",
            "min_workers": "1",
            "workers_required": "1",
            "is_active": "on",
            "required_attributes": '["not", "a dict"]',
        }
        response = client.post("/shifts/create/", data)
        assert response.status_code == 200  # re-rendered form with errors
        assert ShiftType.objects.count() == 0

    def test_update_preserves_applicable_days(self, client: Client) -> None:
        """Checkboxes are pre-checked on edit for existing applicable_days."""
        shift = ShiftType.objects.create(
            shift_type_id="DAY",
            name="Day Shift",
            start_time="07:00",
            duration_hours=8.0,
            min_workers=1,
            workers_required=1,
            is_active=True,
            applicable_days=[0, 1, 2, 3, 4],
            required_attributes={"specialty": "ER"},
        )
        response = client.get(f"/shifts/{shift.pk}/edit/")
        content = response.content.decode()
        # Verify checkboxes are pre-checked (checked attribute present)
        assert "checked" in content
        # Verify required_attributes JSON is present
        assert "specialty" in content
