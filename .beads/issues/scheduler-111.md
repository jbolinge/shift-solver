---
id: scheduler-111
title: "Django ORM models (migrate from SQLAlchemy)"
type: task
status: open
priority: 1
created: 2026-02-21
updated: 2026-02-21
parent: scheduler-109
depends-on: scheduler-110
labels: [web, django, models, database]
---

# Django ORM models (migrate from SQLAlchemy)

Create Django ORM models that mirror the existing SQLAlchemy models, covering workers, shift types, constraints, schedules, and assignments.

## Description

Translate the existing SQLAlchemy models in `src/shift_solver/db/` into Django ORM models under `web/core/models.py`. The Django models serve as the persistence layer for the web UI while the existing SQLAlchemy models continue to serve the CLI. Both map to the same domain concepts.

## Files to Create

- `web/core/models.py` - All Django ORM models
- `web/core/migrations/0001_initial.py` - Auto-generated initial migration
- `tests/test_web/test_models.py` - Model tests

## Files to Modify

- `web/config/settings.py` - Ensure `core` is in INSTALLED_APPS

## Implementation

### Models

```python
class Worker(models.Model):
    """A schedulable resource (employee, contractor, etc.)."""
    worker_id = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=200)
    email = models.EmailField(blank=True)
    group = models.CharField(max_length=100, blank=True)
    fte = models.FloatField(default=1.0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class ShiftType(models.Model):
    """A type of shift with time, duration, and requirements."""
    shift_type_id = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=200)
    category = models.CharField(max_length=100, blank=True)
    start_time = models.TimeField()
    duration_hours = models.FloatField()
    min_workers = models.IntegerField(default=1)
    max_workers = models.IntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

class Availability(models.Model):
    """Worker availability for a specific date/shift."""
    worker = models.ForeignKey(Worker, on_delete=models.CASCADE, related_name="availabilities")
    date = models.DateField()
    shift_type = models.ForeignKey(ShiftType, on_delete=models.CASCADE, null=True, blank=True)
    is_available = models.BooleanField(default=True)
    preference = models.IntegerField(default=0)  # -1=avoid, 0=neutral, 1=prefer

class ConstraintConfig(models.Model):
    """Configuration for a scheduling constraint."""
    constraint_type = models.CharField(max_length=100)
    enabled = models.BooleanField(default=True)
    is_hard = models.BooleanField(default=True)
    weight = models.IntegerField(default=1)
    parameters = models.JSONField(default=dict)

class ScheduleRequest(models.Model):
    """A request to generate a schedule for a date range."""
    name = models.CharField(max_length=200)
    start_date = models.DateField()
    end_date = models.DateField()
    period_length_days = models.IntegerField(default=7)
    status = models.CharField(max_length=20, default="draft")  # draft, running, completed, failed
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class SolverRun(models.Model):
    """Tracks a solver execution."""
    schedule_request = models.ForeignKey(ScheduleRequest, on_delete=models.CASCADE, related_name="solver_runs")
    status = models.CharField(max_length=20, default="pending")  # pending, running, completed, failed
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    result_json = models.JSONField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    progress_percent = models.IntegerField(default=0)

class Assignment(models.Model):
    """A worker assigned to a shift on a specific date."""
    solver_run = models.ForeignKey(SolverRun, on_delete=models.CASCADE, related_name="assignments")
    worker = models.ForeignKey(Worker, on_delete=models.CASCADE)
    shift_type = models.ForeignKey(ShiftType, on_delete=models.CASCADE)
    date = models.DateField()
```

### Key Design Decisions

- Use `CharField` for IDs that mirror domain dataclass string identifiers
- `JSONField` for constraint parameters (flexible schema)
- `SolverRun` separate from `ScheduleRequest` to support multiple solve attempts
- `Assignment` links to `SolverRun` not `ScheduleRequest` for result tracking

## Tests (write first)

```python
class TestWorkerModel:
    def test_create_worker(self):
        """Can create a Worker with required fields."""

    def test_worker_str_representation(self):
        """Worker __str__ returns name."""

    def test_worker_unique_worker_id(self):
        """worker_id must be unique."""

class TestShiftTypeModel:
    def test_create_shift_type(self):
        """Can create a ShiftType with required fields."""

    def test_shift_type_optional_max_workers(self):
        """max_workers can be null."""

class TestAvailabilityModel:
    def test_create_availability(self):
        """Can create an Availability entry."""

    def test_availability_worker_cascade_delete(self):
        """Deleting a worker deletes their availabilities."""

class TestScheduleRequestModel:
    def test_create_schedule_request(self):
        """Can create a ScheduleRequest with date range."""

    def test_schedule_request_default_status(self):
        """Default status is 'draft'."""

class TestSolverRunModel:
    def test_create_solver_run(self):
        """Can create a SolverRun linked to a ScheduleRequest."""

    def test_solver_run_progress_default(self):
        """Default progress_percent is 0."""

class TestAssignmentModel:
    def test_create_assignment(self):
        """Can create an Assignment linking worker, shift, and date."""
```

## Acceptance Criteria

- [ ] Tests written before implementation
- [ ] All 7 models created with correct fields and relationships
- [ ] `makemigrations` generates clean initial migration
- [ ] `migrate` runs without error
- [ ] Foreign key cascades work correctly
- [ ] All 11 tests pass
- [ ] ruff and mypy clean
- [ ] Frequent, focused commits
