"""Admin configuration for core models with django-unfold."""

from django.contrib import admin
from unfold.admin import ModelAdmin

from core.models import (
    Assignment,
    Availability,
    ConstraintConfig,
    ScheduleRequest,
    ShiftType,
    SolverRun,
    Worker,
    WorkerRequest,
)


@admin.register(Worker)
class WorkerAdmin(ModelAdmin):  # type: ignore[type-arg]
    list_display = ["worker_id", "name", "group", "fte", "is_active"]
    list_filter = ["is_active", "group"]
    search_fields = ["name", "worker_id"]


@admin.register(ShiftType)
class ShiftTypeAdmin(ModelAdmin):  # type: ignore[type-arg]
    list_display = [
        "shift_type_id", "name", "category", "start_time",
        "duration_hours", "workers_required",
    ]
    list_filter = ["category", "is_active"]
    search_fields = ["name", "shift_type_id"]


@admin.register(Availability)
class AvailabilityAdmin(ModelAdmin):  # type: ignore[type-arg]
    list_display = ["worker", "date", "shift_type", "is_available", "preference"]
    list_filter = ["is_available", "date"]
    search_fields = ["worker__name"]


@admin.register(ConstraintConfig)
class ConstraintConfigAdmin(ModelAdmin):  # type: ignore[type-arg]
    list_display = ["constraint_type", "enabled", "is_hard", "weight"]
    list_filter = ["enabled", "is_hard"]


@admin.register(ScheduleRequest)
class ScheduleRequestAdmin(ModelAdmin):  # type: ignore[type-arg]
    list_display = ["name", "start_date", "end_date", "status", "created_at"]
    list_filter = ["status"]
    search_fields = ["name"]


@admin.register(SolverRun)
class SolverRunAdmin(ModelAdmin):  # type: ignore[type-arg]
    list_display = ["id", "schedule_request", "status", "progress_percent", "started_at"]
    list_filter = ["status"]


@admin.register(WorkerRequest)
class WorkerRequestAdmin(ModelAdmin):  # type: ignore[type-arg]
    list_display = [
        "id", "schedule_request", "worker", "shift_type",
        "request_type", "priority", "is_hard", "start_date", "end_date",
    ]
    list_filter = ["request_type", "is_hard"]
    search_fields = ["worker__name", "shift_type__name"]


@admin.register(Assignment)
class AssignmentAdmin(ModelAdmin):  # type: ignore[type-arg]
    list_display = ["id", "solver_run", "worker", "shift_type", "date"]
    list_filter = ["date", "shift_type"]
    search_fields = ["worker__name"]
