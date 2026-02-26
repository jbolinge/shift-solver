"""Conversion layer between Django ORM models and domain dataclasses."""

from datetime import timedelta
from typing import Any

from core import models as orm
from shift_solver.constraints.base import ConstraintConfig as DomainConstraintConfig
from shift_solver.models import ShiftType as DomainShiftType
from shift_solver.models import Worker as DomainWorker
from shift_solver.models.schedule import Schedule


def orm_worker_to_domain(orm_worker: orm.Worker) -> DomainWorker:
    """Convert Django Worker ORM instance to domain Worker dataclass."""
    return DomainWorker(
        id=str(orm_worker.worker_id),
        name=str(orm_worker.name),
        worker_type=str(orm_worker.worker_type) if orm_worker.worker_type else None,
        restricted_shifts=frozenset(orm_worker.restricted_shifts or []),
        preferred_shifts=frozenset(orm_worker.preferred_shifts or []),
        attributes=dict(orm_worker.attributes or {}),
    )


def domain_worker_to_orm(domain_worker: DomainWorker) -> orm.Worker:
    """Convert domain Worker dataclass to unsaved Django Worker ORM instance."""
    return orm.Worker(
        worker_id=domain_worker.id,
        name=domain_worker.name,
        worker_type=domain_worker.worker_type or "",
        restricted_shifts=sorted(domain_worker.restricted_shifts),
        preferred_shifts=sorted(domain_worker.preferred_shifts),
        attributes=domain_worker.attributes,
    )


def orm_shift_type_to_domain(orm_shift: orm.ShiftType) -> DomainShiftType:
    """Convert Django ShiftType ORM instance to domain ShiftType dataclass."""
    # Compute end_time from start_time + duration
    start = orm_shift.start_time
    start_minutes = start.hour * 60 + start.minute
    end_minutes = start_minutes + int(float(str(orm_shift.duration_hours)) * 60)
    end_hour = (end_minutes // 60) % 24
    end_min = end_minutes % 60
    from datetime import time

    end_time = time(end_hour, end_min)

    applicable_days = None
    if orm_shift.applicable_days is not None:
        applicable_days = frozenset(orm_shift.applicable_days)

    return DomainShiftType(
        id=str(orm_shift.shift_type_id),
        name=str(orm_shift.name),
        category=str(orm_shift.category) or "default",
        start_time=orm_shift.start_time,
        end_time=end_time,
        duration_hours=float(str(orm_shift.duration_hours)),
        is_undesirable=bool(orm_shift.is_undesirable),
        workers_required=int(str(orm_shift.workers_required)),
        required_attributes=dict(orm_shift.required_attributes or {}),
        applicable_days=applicable_days,
    )


def domain_shift_type_to_orm(domain_shift: DomainShiftType) -> orm.ShiftType:
    """Convert domain ShiftType dataclass to unsaved Django ShiftType ORM instance."""
    applicable_days = None
    if domain_shift.applicable_days is not None:
        applicable_days = sorted(domain_shift.applicable_days)

    return orm.ShiftType(
        shift_type_id=domain_shift.id,
        name=domain_shift.name,
        category=domain_shift.category,
        start_time=domain_shift.start_time,
        duration_hours=domain_shift.duration_hours,
        is_undesirable=domain_shift.is_undesirable,
        workers_required=domain_shift.workers_required,
        required_attributes=domain_shift.required_attributes,
        applicable_days=applicable_days,
    )


def orm_constraint_to_domain(
    orm_constraint: orm.ConstraintConfig,
) -> DomainConstraintConfig:
    """Convert Django ConstraintConfig to domain ConstraintConfig."""
    return DomainConstraintConfig(
        enabled=bool(orm_constraint.enabled),
        is_hard=bool(orm_constraint.is_hard),
        weight=int(str(orm_constraint.weight)),
        parameters=dict(orm_constraint.parameters or {}),
    )


def build_schedule_input(
    schedule_request: orm.ScheduleRequest,
) -> dict[str, Any]:
    """Build solver input dict from a ScheduleRequest and its related data.

    Returns a dict with keys: workers, shift_types, period_dates,
    constraint_configs, availabilities, schedule_id.
    """
    # Get workers: use request's M2M selection, or all active if empty
    if schedule_request.workers.exists():
        orm_workers = list(schedule_request.workers.filter(is_active=True))
    else:
        orm_workers = list(orm.Worker.objects.filter(is_active=True))

    # Get shift types: use request's M2M selection, or all active if empty
    if schedule_request.shift_types.exists():
        orm_shifts = list(schedule_request.shift_types.filter(is_active=True))
    else:
        orm_shifts = list(orm.ShiftType.objects.filter(is_active=True))

    # Convert to domain objects
    workers = [orm_worker_to_domain(w) for w in orm_workers]
    shift_types = [orm_shift_type_to_domain(s) for s in orm_shifts]

    # Build period dates from request date range
    period_length = int(str(schedule_request.period_length_days))
    period_dates = []
    current = schedule_request.start_date
    while current < schedule_request.end_date:
        period_end = min(
            current + timedelta(days=period_length - 1),
            schedule_request.end_date,
        )
        period_dates.append((current, period_end))
        current = period_end + timedelta(days=1)

    # Get enabled constraint configs
    constraint_configs = {}
    for orm_config in orm.ConstraintConfig.objects.filter(enabled=True):
        constraint_configs[str(orm_config.constraint_type)] = orm_constraint_to_domain(
            orm_config
        )

    return {
        "workers": workers,
        "shift_types": shift_types,
        "period_dates": period_dates,
        "constraint_configs": constraint_configs,
        "schedule_id": f"web-{schedule_request.pk}",
    }


def solver_result_to_assignments(
    solver_run: orm.SolverRun,
    schedule: Schedule,
) -> list[orm.Assignment]:
    """Convert solver Schedule result to Django Assignment ORM instances.

    Returns unsaved Assignment instances (caller should bulk_create them).
    """
    # Build lookup maps for ORM instances
    worker_map = {
        str(w.worker_id): w for w in orm.Worker.objects.all()
    }
    shift_map = {
        str(s.shift_type_id): s for s in orm.ShiftType.objects.all()
    }

    assignments = []
    for period in schedule.periods:
        for worker_id, shift_instances in period.assignments.items():
            orm_worker = worker_map.get(worker_id)
            if orm_worker is None:
                continue
            for shift_instance in shift_instances:
                orm_shift = shift_map.get(shift_instance.shift_type_id)
                if orm_shift is None:
                    continue
                assignments.append(
                    orm.Assignment(
                        solver_run=solver_run,
                        worker=orm_worker,
                        shift_type=orm_shift,
                        date=shift_instance.date,
                    )
                )

    return assignments
