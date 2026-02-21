---
id: scheduler-120
title: "Schedule parameters and solver settings UI"
type: feature
status: open
priority: 1
created: 2026-02-21
updated: 2026-02-21
parent: scheduler-109
depends-on: scheduler-119
labels: [web, django, htmx, solver, configuration]
---

# Schedule parameters and solver settings UI

Build a web interface for configuring solver parameters: time limits, optimality settings, and schedule-wide parameters.

## Description

Create a solver settings page where users configure CP-SAT solver parameters (time limit, number of workers, optimality gap) and schedule-wide parameters (period length, fairness tolerance). These settings are stored per scheduling request and passed to the solver at execution time.

## Files to Create

- `web/core/forms.py` - Add SolverSettingsForm (or modify existing)
- `web/core/views/settings_views.py` - Solver settings views
- `web/core/models.py` - Add SolverSettings model (or extend ScheduleRequest)
- `web/templates/settings/solver_settings.html` - Solver settings page
- `web/templates/settings/settings_form.html` - Settings form partial
- `tests/test_web/test_settings_views.py` - Settings view tests

## Files to Modify

- `web/core/urls.py` - Add settings URL patterns

## Implementation

### SolverSettings Model (or ScheduleRequest extension)

```python
class SolverSettings(models.Model):
    """Solver configuration for a scheduling request."""
    schedule_request = models.OneToOneField(ScheduleRequest, on_delete=models.CASCADE)
    time_limit_seconds = models.IntegerField(default=60)
    num_search_workers = models.IntegerField(default=8)
    optimality_tolerance = models.FloatField(default=0.0)
    log_search_progress = models.BooleanField(default=True)
```

### URL Patterns

```python
urlpatterns += [
    path("requests/<int:pk>/settings/", SolverSettingsView.as_view(), name="solver-settings"),
    path("requests/<int:pk>/settings/edit/", SolverSettingsEditView.as_view(), name="solver-settings-edit"),
]
```

### Settings Form

Groups settings into sections:
1. **Solver Parameters**: Time limit, search workers, optimality tolerance
2. **Schedule Parameters**: Period length, date range (from request)
3. **Output Options**: Log search progress, verbosity

### HTMX Patterns

- Form auto-saves on field change via HTMX
- Validation feedback shown inline
- Reset to defaults button

## Tests (write first)

```python
class TestSolverSettingsView:
    def test_settings_page_returns_200(self, client, schedule_request):
        """Solver settings page returns HTTP 200."""

    def test_settings_shows_current_values(self, client, schedule_request, solver_settings):
        """Settings page displays current solver configuration."""

    def test_settings_shows_defaults_for_new_request(self, client, schedule_request):
        """New request shows default solver settings."""

class TestSolverSettingsEditView:
    def test_update_time_limit(self, client, schedule_request, solver_settings):
        """Updating time limit saves to database."""

    def test_update_num_workers(self, client, schedule_request, solver_settings):
        """Updating search workers saves to database."""

    def test_invalid_time_limit_rejected(self, client, schedule_request, solver_settings):
        """Zero or negative time limit returns validation error."""

    def test_settings_auto_created_on_first_access(self, client, schedule_request):
        """Accessing settings for a request without settings creates defaults."""
```

## Acceptance Criteria

- [ ] Tests written before implementation
- [ ] Solver settings page displays all configurable parameters
- [ ] Settings can be edited and saved via HTMX
- [ ] Default values applied for new requests
- [ ] Validation prevents invalid values (negative time limits, etc.)
- [ ] Settings linked to scheduling request via OneToOne
- [ ] All 7 tests pass
- [ ] ruff and mypy clean
- [ ] Frequent, focused commits
