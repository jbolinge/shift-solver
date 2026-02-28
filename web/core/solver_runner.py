"""Background solver runner for executing CP-SAT solver in a separate thread."""

import contextlib
import logging
import threading

from django.utils import timezone

from core.converters import build_schedule_input, solver_result_to_assignments
from core.models import Assignment, SolverRun, SolverSettings

logger = logging.getLogger(__name__)


class SolverRunner:
    """Runs the CP-SAT solver in a background thread.

    Usage:
        runner = SolverRunner(solver_run_id=run.id)
        runner.run()  # Non-blocking, starts background thread

    For testing, call _execute() directly (synchronous).
    """

    _active_runs: dict[int, threading.Event] = {}
    _lock = threading.Lock()

    def __init__(self, solver_run_id: int) -> None:
        self.solver_run_id = solver_run_id

    def run(self) -> None:
        """Start solver in background thread."""
        cancel_event = threading.Event()
        with self._lock:
            self._active_runs[self.solver_run_id] = cancel_event
        thread = threading.Thread(
            target=self._execute, args=(cancel_event,), daemon=True
        )
        thread.start()

    @classmethod
    def cancel(cls, solver_run_id: int) -> bool:
        """Request cancellation of a running solve.

        Returns True if the run was found and signalled, False otherwise.
        """
        with cls._lock:
            event = cls._active_runs.get(solver_run_id)
        if event is not None:
            event.set()
            return True
        return False

    @classmethod
    def _unregister(cls, solver_run_id: int) -> None:
        """Remove a run from the active registry."""
        with cls._lock:
            cls._active_runs.pop(solver_run_id, None)

    def _execute(self, cancel_event: threading.Event | None = None) -> None:
        """Main solver execution - can be called directly for testing."""
        from django.db import connection

        # Close old connection to get fresh one for this thread
        connection.close()

        solver_run = SolverRun.objects.get(id=self.solver_run_id)
        try:
            solver_run.status = "running"
            solver_run.started_at = timezone.now()
            solver_run.progress_json = {"phase": "preparing"}
            solver_run.save()

            # Get solver settings
            try:
                settings = solver_run.schedule_request.solver_settings
                time_limit = settings.time_limit_seconds
            except SolverSettings.DoesNotExist:
                time_limit = 60

            # Build solver input from ORM data
            schedule_input = build_schedule_input(solver_run.schedule_request)

            # Import and create solver
            from shift_solver.solver.shift_solver import ShiftSolver

            solver = ShiftSolver(
                workers=schedule_input["workers"],
                shift_types=schedule_input["shift_types"],
                period_dates=schedule_input["period_dates"],
                schedule_id=schedule_input["schedule_id"],
                constraint_configs=schedule_input["constraint_configs"],
                requests=schedule_input.get("requests"),
                availabilities=schedule_input.get("availabilities"),
            )

            # Read all solver settings with defaults
            try:
                settings = solver_run.schedule_request.solver_settings
                num_workers = settings.num_search_workers
                optimality_tolerance = settings.optimality_tolerance
                log_search = settings.log_search_progress
            except SolverSettings.DoesNotExist:
                num_workers = None
                optimality_tolerance = None
                log_search = None

            # Create progress callback
            from shift_solver.solver.progress_callback import SolverProgressCallback

            run_id = self.solver_run_id

            def _on_progress(data: dict) -> None:
                with contextlib.suppress(Exception):
                    SolverRun.objects.filter(id=run_id).update(progress_json=data)

            callback = SolverProgressCallback(
                cancel_event=cancel_event,
                on_progress=_on_progress,
            )

            # Update phase to solving
            SolverRun.objects.filter(id=self.solver_run_id).update(
                progress_json={"phase": "solving"}
            )

            result = solver.solve(
                time_limit_seconds=time_limit,
                num_workers=num_workers,
                relative_gap_limit=optimality_tolerance,
                log_search_progress=log_search,
                solution_callback=callback,
            )

            # Check if cancelled
            if cancel_event is not None and cancel_event.is_set():
                if result.success and result.schedule:
                    # Save partial results
                    SolverRun.objects.filter(id=self.solver_run_id).update(
                        progress_json={"phase": "extracting"}
                    )
                    assignments = solver_result_to_assignments(
                        solver_run, result.schedule
                    )
                    Assignment.objects.bulk_create(assignments)
                    solver_run.status = "cancelled"
                    solver_run.result_json = {
                        "status": "CANCELLED_WITH_SOLUTION",
                        "objective_value": result.objective_value,
                        "solve_time_seconds": result.solve_time_seconds,
                        "assignment_count": len(assignments),
                        "solutions_found": callback.solutions_found,
                    }
                else:
                    solver_run.status = "cancelled"
                    solver_run.result_json = {
                        "status": "CANCELLED",
                        "solve_time_seconds": result.solve_time_seconds,
                        "solutions_found": callback.solutions_found,
                    }
            elif result.success and result.schedule:
                SolverRun.objects.filter(id=self.solver_run_id).update(
                    progress_json={"phase": "extracting"}
                )
                assignments = solver_result_to_assignments(
                    solver_run, result.schedule
                )
                Assignment.objects.bulk_create(assignments)
                solver_run.status = "completed"
                solver_run.result_json = {
                    "status": result.status_name,
                    "objective_value": result.objective_value,
                    "solve_time_seconds": result.solve_time_seconds,
                    "assignment_count": len(assignments),
                }
            else:
                solver_run.status = "failed"
                solver_run.error_message = f"Solver status: {result.status_name}"

            solver_run.progress_percent = 100
            solver_run.completed_at = timezone.now()
            solver_run.progress_json = {"phase": "done"}
            solver_run.save()

        except Exception as e:
            logger.exception("Solver run %s failed", self.solver_run_id)
            solver_run.status = "failed"
            solver_run.error_message = str(e)
            solver_run.completed_at = timezone.now()
            solver_run.save()
        finally:
            self._unregister(self.solver_run_id)
