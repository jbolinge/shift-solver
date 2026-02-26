---
id: scheduler-121
title: "Background solver runner with progress tracking"
type: task
status: closed
priority: 1
created: 2026-02-21
updated: 2026-02-21
parent: scheduler-109
depends-on: [scheduler-112, scheduler-120]
labels: [web, django, solver, async, background]
---

# Background solver runner with progress tracking

Implement a background solver execution mechanism using threading, with progress tracking via the SolverRun model.

## Description

Create a background solver runner that executes the CP-SAT solver in a separate thread, updating progress in the database. The runner converts Django ORM data to domain dataclasses (via the conversion layer), runs the solver, and stores results back as Assignment records. Progress is tracked via the SolverRun model's `progress_percent` and `status` fields.

## Files to Create

- `web/core/solver_runner.py` - Background solver runner
- `tests/test_web/test_solver_runner.py` - Solver runner tests

## Implementation

### SolverRunner Class

```python
class SolverRunner:
    """Runs the CP-SAT solver in a background thread with progress tracking."""

    def __init__(self, solver_run_id: int):
        self.solver_run_id = solver_run_id

    def run(self) -> None:
        """Execute solver in background thread."""
        thread = threading.Thread(target=self._execute, daemon=True)
        thread.start()

    def _execute(self) -> None:
        """Main solver execution logic."""
        solver_run = SolverRun.objects.get(id=self.solver_run_id)
        try:
            solver_run.status = "running"
            solver_run.started_at = timezone.now()
            solver_run.save()

            # Convert ORM data to domain objects
            schedule_input = build_schedule_input(solver_run.schedule_request)

            # Run solver with progress callback
            schedule = solve(schedule_input, callback=self._progress_callback)

            # Store results
            assignments = solver_result_to_assignments(solver_run, schedule)
            Assignment.objects.bulk_create(assignments)

            solver_run.status = "completed"
            solver_run.progress_percent = 100
            solver_run.completed_at = timezone.now()
            solver_run.result_json = schedule.to_dict()
            solver_run.save()

        except Exception as e:
            solver_run.status = "failed"
            solver_run.error_message = str(e)
            solver_run.completed_at = timezone.now()
            solver_run.save()

    def _progress_callback(self, percent: int) -> None:
        """Update progress in the database."""
        SolverRun.objects.filter(id=self.solver_run_id).update(
            progress_percent=percent
        )
```

### Key Design Decisions

- `threading.Thread` with `daemon=True` for simplicity (no Celery dependency)
- Progress updated via direct DB writes from the background thread
- Errors caught and stored in `error_message` field
- `result_json` stores the complete schedule for quick access
- `Assignment` records stored via `bulk_create` for performance

### Thread Safety

- Each thread operates on its own DB connection (Django handles per-thread connections)
- Progress updates use `.filter().update()` (atomic) instead of save (avoids race conditions)

## Tests (write first)

```python
class TestSolverRunner:
    def test_solver_run_status_transitions(self, solver_run):
        """Solver run transitions: pending -> running -> completed."""

    def test_solver_run_creates_assignments(self, solver_run, workers, shift_types):
        """Successful solve creates Assignment records in the database."""

    def test_solver_run_records_started_at(self, solver_run):
        """started_at timestamp is set when solver begins."""

    def test_solver_run_records_completed_at(self, solver_run):
        """completed_at timestamp is set when solver finishes."""

    def test_solver_run_failure_sets_error(self, solver_run_with_invalid_data):
        """Failed solve sets status='failed' and records error_message."""

    def test_solver_run_progress_updates(self, solver_run):
        """Progress percent is updated during solve."""

    def test_solver_run_stores_result_json(self, solver_run, workers, shift_types):
        """Successful solve stores result_json on the SolverRun."""

    def test_solver_runner_starts_background_thread(self, solver_run):
        """SolverRunner.run() starts execution in a background thread."""
```

## Acceptance Criteria

- [ ] Tests written before implementation
- [ ] Solver executes in background thread without blocking request
- [ ] SolverRun status transitions correctly (pending -> running -> completed/failed)
- [ ] Progress percentage updated during solve
- [ ] Assignments stored in database on success
- [ ] Error message stored on failure
- [ ] Timestamps recorded for start and completion
- [ ] All 8 tests pass
- [ ] ruff and mypy clean
- [ ] Frequent, focused commits
