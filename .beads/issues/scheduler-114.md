---
id: scheduler-114
title: "Django admin with django-unfold"
type: task
status: open
priority: 2
created: 2026-02-21
updated: 2026-02-21
parent: scheduler-109
depends-on: scheduler-111
labels: [web, django, admin]
---

# Django admin with django-unfold

Configure the Django admin interface with django-unfold for a polished admin experience, registering all models.

## Description

Set up django-unfold as the admin theme and register all core models (Worker, ShiftType, Availability, ConstraintConfig, ScheduleRequest, SolverRun, Assignment) with appropriate list displays, filters, and search fields.

## Files to Create

- `web/core/admin.py` - Model admin registrations
- `tests/test_web/test_admin.py` - Admin tests

## Files to Modify

- `web/config/settings.py` - Add `unfold` to INSTALLED_APPS (before `django.contrib.admin`)

## Implementation

### Admin Registrations

```python
from unfold.admin import ModelAdmin

@admin.register(Worker)
class WorkerAdmin(ModelAdmin):
    list_display = ["worker_id", "name", "group", "fte", "is_active"]
    list_filter = ["is_active", "group"]
    search_fields = ["name", "worker_id"]

@admin.register(ShiftType)
class ShiftTypeAdmin(ModelAdmin):
    list_display = ["shift_type_id", "name", "category", "start_time", "duration_hours"]
    list_filter = ["category", "is_active"]
    search_fields = ["name", "shift_type_id"]

@admin.register(ConstraintConfig)
class ConstraintConfigAdmin(ModelAdmin):
    list_display = ["constraint_type", "enabled", "is_hard", "weight"]
    list_filter = ["enabled", "is_hard"]

@admin.register(ScheduleRequest)
class ScheduleRequestAdmin(ModelAdmin):
    list_display = ["name", "start_date", "end_date", "status", "created_at"]
    list_filter = ["status"]
    search_fields = ["name"]

@admin.register(SolverRun)
class SolverRunAdmin(ModelAdmin):
    list_display = ["id", "schedule_request", "status", "progress_percent", "started_at"]
    list_filter = ["status"]

@admin.register(Assignment)
class AssignmentAdmin(ModelAdmin):
    list_display = ["id", "solver_run", "worker", "shift_type", "date"]
    list_filter = ["date", "shift_type"]
    search_fields = ["worker__name"]
```

## Tests (write first)

```python
class TestDjangoAdmin:
    def test_admin_login_page_loads(self, client):
        """Admin login page returns HTTP 200."""

    def test_worker_admin_registered(self):
        """Worker model is registered with admin site."""

    def test_shift_type_admin_registered(self):
        """ShiftType model is registered with admin site."""

    def test_constraint_config_admin_registered(self):
        """ConstraintConfig model is registered with admin site."""

    def test_schedule_request_admin_registered(self):
        """ScheduleRequest model is registered with admin site."""

    def test_admin_uses_unfold_theme(self, admin_client):
        """Admin pages use django-unfold styling."""
```

## Acceptance Criteria

- [ ] Tests written before implementation
- [ ] django-unfold configured and rendering admin pages
- [ ] All 6 core models registered in admin
- [ ] List views have appropriate display columns, filters, and search
- [ ] Admin login page accessible at `/admin/`
- [ ] All 6 tests pass
- [ ] ruff and mypy clean
- [ ] Frequent, focused commits
