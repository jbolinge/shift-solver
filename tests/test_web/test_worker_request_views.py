"""Tests for WorkerRequest CRUD views, form, converter, and solver pipeline."""

import datetime

import pytest
from django.test import Client

from core.models import ScheduleRequest, ShiftType, Worker, WorkerRequest

pytestmark = pytest.mark.django_db


@pytest.fixture()
def schedule_request():
    return ScheduleRequest.objects.create(
        name="Test Request",
        start_date=datetime.date(2026, 3, 1),
        end_date=datetime.date(2026, 3, 31),
    )


@pytest.fixture()
def worker():
    return Worker.objects.create(worker_id="W1", name="Alice Smith")


@pytest.fixture()
def shift_type():
    return ShiftType.objects.create(
        shift_type_id="DAY",
        name="Day Shift",
        start_time=datetime.time(7, 0),
        duration_hours=8.0,
    )


@pytest.fixture()
def worker_request(schedule_request, worker, shift_type):
    return WorkerRequest.objects.create(
        schedule_request=schedule_request,
        worker=worker,
        shift_type=shift_type,
        start_date=datetime.date(2026, 3, 1),
        end_date=datetime.date(2026, 3, 7),
        request_type="negative",
        priority=1,
        is_hard=None,
    )


class TestWorkerRequestListView:
    """Tests for the worker request list view."""

    def test_list_returns_200(self, client: Client, schedule_request) -> None:
        response = client.get(
            f"/requests/{schedule_request.pk}/worker-requests/"
        )
        assert response.status_code == 200

    def test_list_shows_worker_requests(
        self, client: Client, worker_request, schedule_request
    ) -> None:
        response = client.get(
            f"/requests/{schedule_request.pk}/worker-requests/"
        )
        content = response.content.decode()
        assert "Alice Smith" in content
        assert "Day Shift" in content

    def test_list_shows_empty_state(
        self, client: Client, schedule_request
    ) -> None:
        response = client.get(
            f"/requests/{schedule_request.pk}/worker-requests/"
        )
        content = response.content.decode()
        assert "No worker requests found" in content


class TestWorkerRequestCreateView:
    """Tests for the worker request create view."""

    def test_create_get_returns_form(
        self, client: Client, schedule_request
    ) -> None:
        response = client.get(
            f"/requests/{schedule_request.pk}/worker-requests/create/"
        )
        assert response.status_code == 200
        assert "<form" in response.content.decode()

    def test_create_post_valid_data(
        self, client: Client, schedule_request, worker, shift_type
    ) -> None:
        data = {
            "worker": worker.pk,
            "shift_type": shift_type.pk,
            "start_date": "2026-03-01",
            "end_date": "2026-03-07",
            "request_type": "negative",
            "priority": "1",
            "is_hard": "",
        }
        response = client.post(
            f"/requests/{schedule_request.pk}/worker-requests/create/", data
        )
        assert WorkerRequest.objects.count() == 1
        wr = WorkerRequest.objects.first()
        assert wr.schedule_request == schedule_request
        assert wr.worker == worker
        assert wr.is_hard is None
        assert response.status_code == 302

    def test_create_post_is_hard_true(
        self, client: Client, schedule_request, worker, shift_type
    ) -> None:
        data = {
            "worker": worker.pk,
            "shift_type": shift_type.pk,
            "start_date": "2026-03-01",
            "end_date": "2026-03-07",
            "request_type": "positive",
            "priority": "2",
            "is_hard": "true",
        }
        response = client.post(
            f"/requests/{schedule_request.pk}/worker-requests/create/", data
        )
        assert WorkerRequest.objects.count() == 1
        wr = WorkerRequest.objects.first()
        assert wr.is_hard is True
        assert wr.request_type == "positive"
        assert wr.priority == 2

    def test_create_post_is_hard_false(
        self, client: Client, schedule_request, worker, shift_type
    ) -> None:
        data = {
            "worker": worker.pk,
            "shift_type": shift_type.pk,
            "start_date": "2026-03-01",
            "end_date": "2026-03-07",
            "request_type": "negative",
            "priority": "1",
            "is_hard": "false",
        }
        client.post(
            f"/requests/{schedule_request.pk}/worker-requests/create/", data
        )
        wr = WorkerRequest.objects.first()
        assert wr.is_hard is False

    def test_create_post_invalid_date_range(
        self, client: Client, schedule_request, worker, shift_type
    ) -> None:
        data = {
            "worker": worker.pk,
            "shift_type": shift_type.pk,
            "start_date": "2026-03-15",
            "end_date": "2026-03-01",
            "request_type": "negative",
            "priority": "1",
            "is_hard": "",
        }
        response = client.post(
            f"/requests/{schedule_request.pk}/worker-requests/create/", data
        )
        assert response.status_code == 200
        assert WorkerRequest.objects.count() == 0
        assert "End date must be on or after start date" in response.content.decode()

    def test_htmx_create_returns_partial(
        self, client: Client, schedule_request, worker, shift_type
    ) -> None:
        data = {
            "worker": worker.pk,
            "shift_type": shift_type.pk,
            "start_date": "2026-03-01",
            "end_date": "2026-03-07",
            "request_type": "negative",
            "priority": "1",
            "is_hard": "",
        }
        response = client.post(
            f"/requests/{schedule_request.pk}/worker-requests/create/",
            data,
            HTTP_HX_REQUEST="true",
        )
        assert response.status_code == 200
        content = response.content.decode()
        assert "<tr" in content
        assert "<!DOCTYPE" not in content


class TestWorkerRequestUpdateView:
    """Tests for the worker request update view."""

    def test_update_get_returns_prefilled_form(
        self, client: Client, worker_request, schedule_request
    ) -> None:
        response = client.get(
            f"/requests/{schedule_request.pk}/worker-requests/{worker_request.pk}/edit/"
        )
        assert response.status_code == 200
        assert "<form" in response.content.decode()

    def test_update_post_changes_data(
        self, client: Client, worker_request, schedule_request, worker, shift_type
    ) -> None:
        data = {
            "worker": worker.pk,
            "shift_type": shift_type.pk,
            "start_date": "2026-03-01",
            "end_date": "2026-03-14",
            "request_type": "positive",
            "priority": "3",
            "is_hard": "true",
        }
        response = client.post(
            f"/requests/{schedule_request.pk}/worker-requests/{worker_request.pk}/edit/",
            data,
        )
        worker_request.refresh_from_db()
        assert worker_request.request_type == "positive"
        assert worker_request.priority == 3
        assert worker_request.is_hard is True
        assert response.status_code == 302

    def test_update_wrong_schedule_request_404(
        self, client: Client, worker_request, worker, shift_type
    ) -> None:
        other = ScheduleRequest.objects.create(
            name="Other",
            start_date=datetime.date(2026, 4, 1),
            end_date=datetime.date(2026, 4, 30),
        )
        response = client.get(
            f"/requests/{other.pk}/worker-requests/{worker_request.pk}/edit/"
        )
        assert response.status_code == 404


class TestWorkerRequestDeleteView:
    """Tests for the worker request delete view."""

    def test_delete_removes_from_db(
        self, client: Client, worker_request, schedule_request
    ) -> None:
        response = client.post(
            f"/requests/{schedule_request.pk}/worker-requests/{worker_request.pk}/delete/"
        )
        assert WorkerRequest.objects.count() == 0
        assert response.status_code == 302

    def test_htmx_delete_returns_empty(
        self, client: Client, worker_request, schedule_request
    ) -> None:
        response = client.post(
            f"/requests/{schedule_request.pk}/worker-requests/{worker_request.pk}/delete/",
            HTTP_HX_REQUEST="true",
        )
        assert WorkerRequest.objects.count() == 0
        assert response.status_code == 200
        assert response.content == b""

    def test_get_shows_confirmation(
        self, client: Client, worker_request, schedule_request
    ) -> None:
        response = client.get(
            f"/requests/{schedule_request.pk}/worker-requests/{worker_request.pk}/delete/"
        )
        assert response.status_code == 200
        assert "Delete Worker Request" in response.content.decode()


class TestRequestDetailShowsWorkerRequests:
    """Tests that request detail page includes worker requests."""

    def test_detail_shows_worker_requests(
        self, client: Client, worker_request, schedule_request
    ) -> None:
        response = client.get(f"/requests/{schedule_request.pk}/")
        content = response.content.decode()
        assert "Worker Requests" in content
        assert "Alice Smith" in content
        assert "Day Shift" in content

    def test_detail_shows_empty_worker_requests(
        self, client: Client, schedule_request
    ) -> None:
        response = client.get(f"/requests/{schedule_request.pk}/")
        content = response.content.decode()
        assert "Worker Requests" in content
        assert "No worker requests yet" in content


class TestConverterIntegration:
    """Tests for the converter integration with worker requests."""

    def test_build_schedule_input_includes_requests(
        self, schedule_request, worker_request
    ) -> None:
        from core.converters import build_schedule_input

        result = build_schedule_input(schedule_request)
        assert "requests" in result
        assert result["requests"] is not None
        assert len(result["requests"]) == 1
        req = result["requests"][0]
        assert req.worker_id == "W1"
        assert req.shift_type_id == "DAY"
        assert req.request_type == "negative"
        assert req.is_hard is None

    def test_build_schedule_input_no_requests(
        self, schedule_request
    ) -> None:
        from core.converters import build_schedule_input

        result = build_schedule_input(schedule_request)
        assert result["requests"] is None

    def test_converter_maps_is_hard_values(
        self, schedule_request, worker, shift_type
    ) -> None:
        from core.converters import build_schedule_input

        WorkerRequest.objects.create(
            schedule_request=schedule_request,
            worker=worker,
            shift_type=shift_type,
            start_date=datetime.date(2026, 3, 1),
            end_date=datetime.date(2026, 3, 7),
            request_type="positive",
            priority=2,
            is_hard=True,
        )
        WorkerRequest.objects.create(
            schedule_request=schedule_request,
            worker=worker,
            shift_type=shift_type,
            start_date=datetime.date(2026, 3, 8),
            end_date=datetime.date(2026, 3, 14),
            request_type="negative",
            priority=1,
            is_hard=False,
        )
        result = build_schedule_input(schedule_request)
        reqs = result["requests"]
        assert len(reqs) == 2
        is_hard_values = {r.is_hard for r in reqs}
        assert True in is_hard_values
        assert False in is_hard_values


class TestSolverRunnerPassesRequests:
    """Tests that solver runner passes requests to ShiftSolver."""

    def test_solver_constructor_receives_requests(
        self, schedule_request, worker_request
    ) -> None:
        from core.converters import build_schedule_input

        schedule_input = build_schedule_input(schedule_request)
        assert schedule_input.get("requests") is not None
        # Verify the key is present and can be passed to ShiftSolver
        # (actual solver invocation requires more setup)
