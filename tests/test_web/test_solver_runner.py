"""Tests for background solver runner (scheduler-119)."""

from datetime import date, time

import pytest

from core.models import (
    Assignment,
    ConstraintConfig,
    ScheduleRequest,
    ShiftType,
    SolverRun,
    SolverSettings,
    Worker,
)

pytestmark = pytest.mark.django_db


class TestSolverRunner:
    """Tests for the SolverRunner background execution."""

    @pytest.fixture
    def setup_solver_data(self):
        """Create minimal solvable data: 2 workers, 1 shift type, 1 week."""
        w1 = Worker.objects.create(worker_id="W001", name="Alice")
        w2 = Worker.objects.create(worker_id="W002", name="Bob")
        st = ShiftType.objects.create(
            shift_type_id="day",
            name="Day",
            category="day",
            start_time=time(7, 0),
            duration_hours=8.0,
            workers_required=1,
        )
        ConstraintConfig.objects.create(
            constraint_type="coverage",
            enabled=True,
            is_hard=True,
            weight=100,
        )
        request = ScheduleRequest.objects.create(
            name="Test",
            start_date=date(2026, 3, 2),
            end_date=date(2026, 3, 8),
        )
        request.workers.add(w1, w2)
        request.shift_types.add(st)
        SolverSettings.objects.create(
            schedule_request=request, time_limit_seconds=30
        )
        run = SolverRun.objects.create(schedule_request=request)
        return run

    def test_solver_run_status_transitions(self, setup_solver_data):
        """Solver run transitions: pending -> running -> completed."""
        from core.solver_runner import SolverRunner

        run = setup_solver_data
        assert run.status == "pending"

        runner = SolverRunner(solver_run_id=run.id)
        runner._execute()

        run.refresh_from_db()
        assert run.status == "completed"

    def test_solver_run_creates_assignments(self, setup_solver_data):
        """Successful solve creates Assignment records."""
        from core.solver_runner import SolverRunner

        run = setup_solver_data
        runner = SolverRunner(solver_run_id=run.id)
        runner._execute()

        run.refresh_from_db()
        assert run.status == "completed"
        assert Assignment.objects.filter(solver_run=run).count() > 0

    def test_solver_run_records_started_at(self, setup_solver_data):
        """started_at is set when solver begins."""
        from core.solver_runner import SolverRunner

        run = setup_solver_data
        assert run.started_at is None

        runner = SolverRunner(solver_run_id=run.id)
        runner._execute()

        run.refresh_from_db()
        assert run.started_at is not None

    def test_solver_run_records_completed_at(self, setup_solver_data):
        """completed_at is set when solver finishes."""
        from core.solver_runner import SolverRunner

        run = setup_solver_data
        assert run.completed_at is None

        runner = SolverRunner(solver_run_id=run.id)
        runner._execute()

        run.refresh_from_db()
        assert run.completed_at is not None
        assert run.completed_at >= run.started_at

    def test_solver_run_failure_sets_error(self):
        """Failed solve sets status='failed' and records error_message."""
        from core.solver_runner import SolverRunner

        # Create a request with no workers -- solver will raise ValueError
        request = ScheduleRequest.objects.create(
            name="Empty",
            start_date=date(2026, 3, 2),
            end_date=date(2026, 3, 8),
        )
        # No workers added, no shift types added
        run = SolverRun.objects.create(schedule_request=request)

        runner = SolverRunner(solver_run_id=run.id)
        runner._execute()

        run.refresh_from_db()
        assert run.status == "failed"
        assert run.error_message != ""

    def test_solver_run_progress_updates(self, setup_solver_data):
        """Progress percent is set to 100 on completion."""
        from core.solver_runner import SolverRunner

        run = setup_solver_data
        assert run.progress_percent == 0

        runner = SolverRunner(solver_run_id=run.id)
        runner._execute()

        run.refresh_from_db()
        assert run.progress_percent == 100

    def test_solver_run_stores_result_json(self, setup_solver_data):
        """Successful solve stores result data on the SolverRun."""
        from core.solver_runner import SolverRunner

        run = setup_solver_data
        runner = SolverRunner(solver_run_id=run.id)
        runner._execute()

        run.refresh_from_db()
        assert run.result_json is not None
        assert "status" in run.result_json
        assert "solve_time_seconds" in run.result_json
        assert "assignment_count" in run.result_json

    def test_solver_runner_starts_background_thread(self, setup_solver_data):
        """SolverRunner.run() starts execution in a background thread."""
        from unittest.mock import patch

        from core.solver_runner import SolverRunner

        run = setup_solver_data
        runner = SolverRunner(solver_run_id=run.id)

        with patch("threading.Thread") as mock_thread_cls:
            mock_thread = mock_thread_cls.return_value
            runner.run()

            mock_thread_cls.assert_called_once_with(
                target=runner._execute, daemon=True
            )
            mock_thread.start.assert_called_once()
