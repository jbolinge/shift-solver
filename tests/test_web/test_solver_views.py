"""Tests for solver execution views (scheduler-122)."""

import datetime
from typing import Any

import pytest
from django.test import Client

from core.models import (
    Assignment,
    ScheduleRequest,
    ShiftType,
    SolverRun,
    SolverSettings,
    Worker,
)

pytestmark = pytest.mark.django_db


def _make_request(**kwargs: Any) -> ScheduleRequest:
    """Create a ScheduleRequest with sensible defaults."""
    defaults: dict[str, Any] = {
        "name": "Test Schedule",
        "start_date": datetime.date(2026, 3, 1),
        "end_date": datetime.date(2026, 3, 7),
    }
    defaults.update(kwargs)
    return ScheduleRequest.objects.create(**defaults)


def _make_worker(**kwargs: Any) -> Worker:
    """Create a Worker with sensible defaults."""
    defaults: dict[str, Any] = {
        "worker_id": "W1",
        "name": "Alice",
    }
    defaults.update(kwargs)
    return Worker.objects.create(**defaults)


def _make_shift_type(**kwargs: Any) -> ShiftType:
    """Create a ShiftType with sensible defaults."""
    defaults: dict[str, Any] = {
        "shift_type_id": "DAY",
        "name": "Day Shift",
        "start_time": datetime.time(7, 0),
        "duration_hours": 12.0,
    }
    defaults.update(kwargs)
    return ShiftType.objects.create(**defaults)


class TestSolveLaunchView:
    """Tests for the solve launch view."""

    @pytest.fixture(autouse=True)
    def _mock_solver_run(self, monkeypatch):
        """Prevent background thread from spawning during view tests."""
        monkeypatch.setattr(
            "core.solver_runner.SolverRunner.run", lambda _self: None
        )

    def test_launch_creates_solver_run(self, client: Client) -> None:
        """Launching a solve creates a SolverRun record."""
        req = _make_request()
        worker = _make_worker()
        shift = _make_shift_type()
        req.workers.add(worker)
        req.shift_types.add(shift)
        SolverSettings.objects.create(schedule_request=req)

        client.post(f"/requests/{req.pk}/solve/")

        assert SolverRun.objects.filter(schedule_request=req).exists()

    def test_launch_redirects_to_progress(self, client: Client) -> None:
        """Launch redirects to the progress tracking page."""
        req = _make_request()
        worker = _make_worker()
        shift = _make_shift_type()
        req.workers.add(worker)
        req.shift_types.add(shift)
        SolverSettings.objects.create(schedule_request=req)

        response = client.post(f"/requests/{req.pk}/solve/")

        solver_run = SolverRun.objects.get(schedule_request=req)
        assert response.status_code == 302
        assert f"/solver-runs/{solver_run.pk}/progress/" in response["Location"]

    def test_launch_validates_request_has_workers(self, client: Client) -> None:
        """Launch rejects request with no workers available."""
        req = _make_request()
        shift = _make_shift_type()
        req.shift_types.add(shift)
        SolverSettings.objects.create(schedule_request=req)

        response = client.post(f"/requests/{req.pk}/solve/")

        assert not SolverRun.objects.filter(schedule_request=req).exists()
        assert response.status_code == 200
        content = response.content.decode()
        assert "worker" in content.lower()

    def test_launch_get_shows_confirmation(self, client: Client) -> None:
        """GET on launch page shows confirmation with request details."""
        req = _make_request()
        worker = _make_worker()
        shift = _make_shift_type()
        req.workers.add(worker)
        req.shift_types.add(shift)

        response = client.get(f"/requests/{req.pk}/solve/")

        assert response.status_code == 200
        content = response.content.decode()
        assert req.name in content


class TestSolveLaunchModalView:
    """Tests for the solve launch modal view."""

    def test_modal_returns_200(self, client: Client) -> None:
        """Modal endpoint returns HTTP 200."""
        req = _make_request()
        worker = _make_worker()
        shift = _make_shift_type()
        req.workers.add(worker)
        req.shift_types.add(shift)

        response = client.get(f"/requests/{req.pk}/solve/modal/")

        assert response.status_code == 200

    def test_modal_contains_request_info(self, client: Client) -> None:
        """Modal shows request date range."""
        req = _make_request()
        worker = _make_worker()
        shift = _make_shift_type()
        req.workers.add(worker)
        req.shift_types.add(shift)

        response = client.get(f"/requests/{req.pk}/solve/modal/")

        content = response.content.decode()
        assert "solve-modal" in content
        assert "Solve Schedule" in content

    def test_modal_shows_errors_when_no_workers(self, client: Client) -> None:
        """Modal shows validation errors when no workers exist."""
        req = _make_request()
        shift = _make_shift_type()
        req.shift_types.add(shift)

        response = client.get(f"/requests/{req.pk}/solve/modal/")

        content = response.content.decode()
        assert "worker" in content.lower()

    def test_modal_shows_errors_when_no_shifts(self, client: Client) -> None:
        """Modal shows validation errors when no shift types assigned."""
        req = _make_request()
        worker = _make_worker()
        req.workers.add(worker)

        response = client.get(f"/requests/{req.pk}/solve/modal/")

        content = response.content.decode()
        assert "shift type" in content.lower()


class TestSolveProgressView:
    """Tests for the solve progress view."""

    def test_progress_page_returns_200(self, client: Client) -> None:
        """Progress page returns HTTP 200."""
        req = _make_request()
        run = SolverRun.objects.create(
            schedule_request=req, status="running", progress_percent=50
        )

        response = client.get(f"/solver-runs/{run.pk}/progress/")

        assert response.status_code == 200

    def test_progress_bar_returns_partial(self, client: Client) -> None:
        """Progress bar endpoint returns HTML partial."""
        req = _make_request()
        run = SolverRun.objects.create(
            schedule_request=req, status="running", progress_percent=42
        )

        response = client.get(f"/solver-runs/{run.pk}/progress-bar/")

        assert response.status_code == 200

    def test_completed_run_redirects_to_results(self, client: Client) -> None:
        """Progress bar for completed run includes HX-Redirect to results."""
        req = _make_request()
        run = SolverRun.objects.create(
            schedule_request=req, status="completed", progress_percent=100
        )

        response = client.get(f"/solver-runs/{run.pk}/progress-bar/")

        assert response.has_header("HX-Redirect")
        assert f"/solver-runs/{run.pk}/results/" in response["HX-Redirect"]

    def test_cancelled_run_redirects_to_results(self, client: Client) -> None:
        """Progress bar for cancelled run includes HX-Redirect to results."""
        req = _make_request()
        run = SolverRun.objects.create(
            schedule_request=req, status="cancelled", progress_percent=100
        )

        response = client.get(f"/solver-runs/{run.pk}/progress-bar/")

        assert response.has_header("HX-Redirect")
        assert f"/solver-runs/{run.pk}/results/" in response["HX-Redirect"]

    def test_progress_page_shows_cancel_button(self, client: Client) -> None:
        """Progress page shows cancel button for running solve."""
        req = _make_request()
        run = SolverRun.objects.create(
            schedule_request=req, status="running"
        )

        response = client.get(f"/solver-runs/{run.pk}/progress/")

        content = response.content.decode()
        assert "Cancel Solve" in content


class TestSolveCancelView:
    """Tests for the solve cancel view."""

    def test_cancel_requires_post(self, client: Client) -> None:
        """Cancel endpoint rejects GET requests."""
        req = _make_request()
        run = SolverRun.objects.create(
            schedule_request=req, status="running"
        )

        response = client.get(f"/solver-runs/{run.pk}/cancel/")

        assert response.status_code == 405

    def test_cancel_redirects_non_running(self, client: Client) -> None:
        """Cancel redirects to results for non-running run."""
        req = _make_request()
        run = SolverRun.objects.create(
            schedule_request=req, status="completed"
        )

        response = client.post(f"/solver-runs/{run.pk}/cancel/")

        assert response.status_code == 302
        assert f"/solver-runs/{run.pk}/results/" in response["Location"]

    def test_cancel_not_in_registry_marks_failed(self, client: Client) -> None:
        """Cancel marks run as failed when not found in registry."""
        req = _make_request()
        run = SolverRun.objects.create(
            schedule_request=req, status="running"
        )

        response = client.post(f"/solver-runs/{run.pk}/cancel/")

        assert response.status_code == 302
        run.refresh_from_db()
        assert run.status == "failed"
        assert "not found" in run.error_message.lower()


class TestSolveResultsView:
    """Tests for the solve results view."""

    def test_results_page_returns_200(self, client: Client) -> None:
        """Results page returns HTTP 200 for completed run."""
        req = _make_request()
        run = SolverRun.objects.create(
            schedule_request=req,
            status="completed",
            progress_percent=100,
            result_json={
                "status": "OPTIMAL",
                "objective_value": 0,
                "solve_time_seconds": 5.2,
                "assignment_count": 10,
            },
        )

        response = client.get(f"/solver-runs/{run.pk}/results/")

        assert response.status_code == 200

    def test_results_shows_assignment_count(self, client: Client) -> None:
        """Results page shows the number of assignments generated."""
        req = _make_request()
        worker = _make_worker()
        shift = _make_shift_type()
        run = SolverRun.objects.create(
            schedule_request=req,
            status="completed",
            progress_percent=100,
            result_json={"assignment_count": 42},
        )
        # Create some actual assignments
        for i in range(3):
            Assignment.objects.create(
                solver_run=run,
                worker=worker,
                shift_type=shift,
                date=datetime.date(2026, 3, 1 + i),
            )

        response = client.get(f"/solver-runs/{run.pk}/results/")

        content = response.content.decode()
        assert "3" in content  # actual assignment count

    def test_results_shows_duration(self, client: Client) -> None:
        """Results page shows solve duration."""
        req = _make_request()
        run = SolverRun.objects.create(
            schedule_request=req,
            status="completed",
            progress_percent=100,
            result_json={"solve_time_seconds": 12.5, "assignment_count": 0},
        )

        response = client.get(f"/solver-runs/{run.pk}/results/")

        content = response.content.decode()
        assert "12.5" in content

    def test_failed_run_shows_error(self, client: Client) -> None:
        """Results page for failed run shows error message."""
        req = _make_request()
        run = SolverRun.objects.create(
            schedule_request=req,
            status="failed",
            error_message="Solver infeasible: no valid assignments",
        )

        response = client.get(f"/solver-runs/{run.pk}/results/")

        assert response.status_code == 200
        content = response.content.decode()
        assert "Solver infeasible" in content

    def test_cancelled_run_shows_banner(self, client: Client) -> None:
        """Results page shows cancelled banner for cancelled run."""
        req = _make_request()
        run = SolverRun.objects.create(
            schedule_request=req,
            status="cancelled",
            result_json={
                "status": "CANCELLED",
                "solve_time_seconds": 3.0,
                "solutions_found": 0,
            },
        )

        response = client.get(f"/solver-runs/{run.pk}/results/")

        assert response.status_code == 200
        content = response.content.decode()
        assert "Cancelled" in content

    def test_cancelled_with_solution_shows_buttons(self, client: Client) -> None:
        """Cancelled run with solution shows View Schedule and Validate buttons."""
        req = _make_request()
        run = SolverRun.objects.create(
            schedule_request=req,
            status="cancelled",
            result_json={
                "status": "CANCELLED_WITH_SOLUTION",
                "objective_value": 42,
                "solve_time_seconds": 5.0,
                "assignment_count": 7,
                "solutions_found": 3,
            },
        )

        response = client.get(f"/solver-runs/{run.pk}/results/")

        assert response.status_code == 200
        content = response.content.decode()
        assert "View Schedule" in content
        assert "Validate" in content
