---
id: scheduler-112
title: "Domain dataclass conversion layer"
type: task
status: open
priority: 1
created: 2026-02-21
updated: 2026-02-21
parent: scheduler-109
depends-on: scheduler-111
labels: [web, django, models, integration]
---

# Domain dataclass conversion layer

Create a bidirectional conversion layer between Django ORM models and the existing domain dataclasses used by the solver.

## Description

The solver engine operates on domain dataclasses (`Worker`, `ShiftType`, `Schedule`, etc.) defined in `src/shift_solver/models/`. The web UI uses Django ORM models. This conversion layer translates between the two, enabling the web UI to feed data into the solver and display results.

## Files to Create

- `web/core/converters.py` - Conversion functions
- `tests/test_web/test_converters.py` - Conversion tests

## Implementation

### Converter Functions

```python
# web/core/converters.py

def orm_worker_to_domain(orm_worker: core_models.Worker) -> domain_models.Worker:
    """Convert Django Worker ORM instance to domain Worker dataclass."""

def domain_worker_to_orm(domain_worker: domain_models.Worker) -> core_models.Worker:
    """Convert domain Worker dataclass to Django Worker ORM instance."""

def orm_shift_type_to_domain(orm_shift: core_models.ShiftType) -> domain_models.ShiftType:
    """Convert Django ShiftType ORM instance to domain ShiftType dataclass."""

def domain_shift_type_to_orm(domain_shift: domain_models.ShiftType) -> core_models.ShiftType:
    """Convert domain ShiftType dataclass to Django ShiftType ORM instance."""

def orm_availability_to_domain(orm_avail: core_models.Availability) -> domain_models.Availability:
    """Convert Django Availability ORM instance to domain Availability."""

def orm_constraint_to_domain(orm_constraint: core_models.ConstraintConfig) -> dict:
    """Convert Django ConstraintConfig to constraint configuration dict."""

def build_schedule_input(schedule_request: core_models.ScheduleRequest) -> domain_models.ScheduleInput:
    """Build a complete ScheduleInput from a ScheduleRequest and its related data."""

def solver_result_to_assignments(
    solver_run: core_models.SolverRun,
    schedule: domain_models.Schedule,
) -> list[core_models.Assignment]:
    """Convert solver Schedule result back to Django Assignment ORM instances."""
```

### Key Design Decisions

- Functions are stateless: they take an ORM instance, return a dataclass (or vice versa)
- `build_schedule_input` is the main entry point for feeding web data to the solver
- `solver_result_to_assignments` is the main entry point for storing solver results
- Field mapping is explicit, not auto-generated, for clarity and maintainability

## Tests (write first)

```python
class TestWorkerConversion:
    def test_orm_worker_to_domain_fields(self):
        """All worker fields are correctly mapped to domain dataclass."""

    def test_domain_worker_to_orm_fields(self):
        """All worker fields are correctly mapped to ORM model."""

    def test_worker_round_trip(self):
        """ORM -> domain -> ORM preserves all fields."""

class TestShiftTypeConversion:
    def test_orm_shift_type_to_domain_fields(self):
        """All shift type fields are correctly mapped."""

    def test_shift_type_round_trip(self):
        """ORM -> domain -> ORM preserves all fields."""

class TestAvailabilityConversion:
    def test_orm_availability_to_domain(self):
        """Availability fields correctly mapped."""

class TestConstraintConversion:
    def test_orm_constraint_to_domain_dict(self):
        """ConstraintConfig becomes a valid constraint configuration dict."""

class TestBuildScheduleInput:
    def test_build_schedule_input_includes_workers(self):
        """ScheduleInput includes all active workers from the request."""

    def test_build_schedule_input_includes_shift_types(self):
        """ScheduleInput includes all active shift types."""

    def test_build_schedule_input_includes_constraints(self):
        """ScheduleInput includes enabled constraints."""

class TestSolverResultConversion:
    def test_solver_result_creates_assignments(self):
        """Schedule result is converted to Assignment ORM instances."""

    def test_solver_result_links_to_solver_run(self):
        """All assignments reference the correct SolverRun."""
```

## Acceptance Criteria

- [ ] Tests written before implementation
- [ ] Bidirectional conversion for Worker, ShiftType, Availability
- [ ] `build_schedule_input` produces valid ScheduleInput from ORM data
- [ ] `solver_result_to_assignments` correctly stores results
- [ ] Round-trip conversions preserve all fields
- [ ] All 12 tests pass
- [ ] ruff and mypy clean
- [ ] Frequent, focused commits
