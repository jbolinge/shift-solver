"""Tests for background solver runner (scheduler-119)."""

import threading
from datetime import date, time
from unittest.mock import patch

import pytest

from core.models import (
    Assignment,
    Availability,
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
        from core.solver_runner import SolverRunner

        run = setup_solver_data
        runner = SolverRunner(solver_run_id=run.id)

        with patch("threading.Thread") as mock_thread_cls:
            mock_thread = mock_thread_cls.return_value
            runner.run()

            call_kwargs = mock_thread_cls.call_args.kwargs
            assert call_kwargs["target"] == runner._execute
            assert call_kwargs["daemon"] is True
            # args should contain the cancel event
            assert len(call_kwargs["args"]) == 1
            assert isinstance(call_kwargs["args"][0], threading.Event)
            mock_thread.start.assert_called_once()

    def test_solver_run_passes_availability(self, setup_solver_data):
        """Availability records are passed to the solver."""
        from core.solver_runner import SolverRunner

        run = setup_solver_data
        w = Worker.objects.get(worker_id="W001")
        Availability.objects.create(
            worker=w, date=date(2026, 3, 3), is_available=False,
        )

        with patch(
            "shift_solver.solver.shift_solver.ShiftSolver.__init__",
            return_value=None,
        ) as mock_init, patch(
            "shift_solver.solver.shift_solver.ShiftSolver.solve",
        ) as mock_solve:
            from shift_solver.solver.result import SolverResult

            mock_solve.return_value = SolverResult(
                success=False, schedule=None, status=3,
                status_name="INFEASIBLE", solve_time_seconds=0.1,
            )
            runner = SolverRunner(solver_run_id=run.id)
            runner._execute()

            call_kwargs = mock_init.call_args
            assert call_kwargs.kwargs.get("availabilities") is not None
            avail_list = call_kwargs.kwargs["availabilities"]
            assert len(avail_list) == 1
            assert avail_list[0].worker_id == "W001"

    def test_solver_runner_passes_all_settings(self, setup_solver_data):
        """All SolverSettings fields are forwarded to solver.solve()."""
        from core.solver_runner import SolverRunner

        run = setup_solver_data
        settings = SolverSettings.objects.get(schedule_request=run.schedule_request)
        settings.num_search_workers = 4
        settings.optimality_tolerance = 0.05
        settings.log_search_progress = False
        settings.save()

        with patch(
            "shift_solver.solver.shift_solver.ShiftSolver.__init__",
            return_value=None,
        ), patch(
            "shift_solver.solver.shift_solver.ShiftSolver.solve",
        ) as mock_solve:
            from shift_solver.solver.result import SolverResult

            mock_solve.return_value = SolverResult(
                success=False, schedule=None, status=3,
                status_name="INFEASIBLE", solve_time_seconds=0.1,
            )
            runner = SolverRunner(solver_run_id=run.id)
            runner._execute()

            call_kwargs = mock_solve.call_args
            assert call_kwargs.kwargs.get("num_workers") == 4
            assert call_kwargs.kwargs.get("relative_gap_limit") == 0.05
            assert call_kwargs.kwargs.get("log_search_progress") is False


class TestSolverRunnerCancel:
    """Tests for SolverRunner cancel registry."""

    def test_cancel_returns_false_for_unknown_id(self):
        """cancel() returns False when run ID is not in registry."""
        from core.solver_runner import SolverRunner

        assert SolverRunner.cancel(99999) is False

    def test_cancel_sets_event(self):
        """cancel() sets the threading event for registered runs."""
        from core.solver_runner import SolverRunner

        event = threading.Event()
        with SolverRunner._lock:
            SolverRunner._active_runs[12345] = event

        try:
            result = SolverRunner.cancel(12345)
            assert result is True
            assert event.is_set()
        finally:
            SolverRunner._unregister(12345)

    def test_unregister_removes_from_registry(self):
        """_unregister removes the run from _active_runs."""
        from core.solver_runner import SolverRunner

        event = threading.Event()
        with SolverRunner._lock:
            SolverRunner._active_runs[12345] = event

        SolverRunner._unregister(12345)
        assert 12345 not in SolverRunner._active_runs

    def test_run_registers_cancel_event(self):
        """run() registers a cancel event before starting thread."""
        from core.solver_runner import SolverRunner

        runner = SolverRunner(solver_run_id=77777)
        with patch("threading.Thread") as mock_thread_cls:
            mock_thread_cls.return_value.start = lambda: None
            runner.run()
            assert 77777 in SolverRunner._active_runs
            assert isinstance(SolverRunner._active_runs[77777], threading.Event)

        # Clean up
        SolverRunner._unregister(77777)

    def test_progress_json_set_during_execution(self, setup_solver_data_fixture):
        """progress_json is updated during solver execution."""
        from core.solver_runner import SolverRunner

        run = setup_solver_data_fixture
        runner = SolverRunner(solver_run_id=run.id)
        runner._execute()

        run.refresh_from_db()
        assert run.progress_json == {"phase": "done"}

    @pytest.fixture
    def setup_solver_data_fixture(self):
        """Create minimal solvable data."""
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
            name="Test Cancel",
            start_date=date(2026, 3, 2),
            end_date=date(2026, 3, 8),
        )
        request.workers.add(w1, w2)
        request.shift_types.add(st)
        SolverSettings.objects.create(
            schedule_request=request, time_limit_seconds=30
        )
        return SolverRun.objects.create(schedule_request=request)
