---
id: scheduler-126
title: "E2E tests for web UI workflows"
type: task
status: open
priority: 2
created: 2026-02-21
updated: 2026-02-21
parent: scheduler-109
depends-on: scheduler-125
labels: [web, django, testing, e2e]
---

# E2E tests for web UI workflows

Create end-to-end integration tests that exercise complete user workflows through the web UI.

## Description

Build comprehensive E2E tests that simulate real user workflows: creating workers and shifts, setting up availability, configuring constraints, launching a solver run, and viewing results. Tests use Django's test client to exercise the full stack including HTMX interactions, database operations, and solver execution.

## Files to Create

- `tests/test_e2e/test_web_ui_workflows.py` - E2E workflow tests
- `tests/test_e2e/conftest.py` - Shared fixtures for E2E tests (if not existing)

## Implementation

### Test Workflows

**Workflow 1: Complete scheduling cycle**
1. Create workers via CRUD views
2. Create shift types via CRUD views
3. Set availability via calendar endpoint
4. Configure constraints
5. Create a scheduling request
6. Launch solver run
7. Wait for completion
8. View schedule on FullCalendar
9. Export results

**Workflow 2: Data import to schedule**
1. Upload worker CSV
2. Upload shift type CSV
3. Create request with imported data
4. Solve and verify results

**Workflow 3: Modify and re-solve**
1. Use completed schedule from workflow 1
2. Edit a worker (change FTE)
3. Add a new constraint
4. Create new request
5. Solve again
6. Compare results

### Test Infrastructure

- Use `pytest-django` with `@pytest.mark.django_db`
- Use `@pytest.mark.e2e` marker for CI filtering
- Create realistic fixture data (5+ workers, 3+ shift types, 14-day range)
- Use `threading.Event` or polling to wait for background solver completion in tests

### HTMX Testing

For HTMX interactions, tests include the `HX-Request: true` header:
```python
response = client.post(url, data, HTTP_HX_REQUEST="true")
```

Verify partial responses vs full page responses based on HTMX header presence.

## Tests

```python
@pytest.mark.e2e
@pytest.mark.django_db
class TestCompleteSchedulingWorkflow:
    def test_create_workers_and_shifts(self, client):
        """Create workers and shift types via CRUD views."""

    def test_set_availability(self, client, workers, shift_types):
        """Set worker availability via calendar endpoint."""

    def test_configure_constraints(self, client):
        """Configure constraints via constraint UI."""

    def test_create_and_launch_schedule(self, client, workers, shift_types):
        """Create request, launch solver, wait for completion."""

    def test_view_schedule_calendar(self, client, completed_solver_run):
        """View schedule via FullCalendar events endpoint."""

    def test_export_schedule_results(self, client, completed_solver_run):
        """Export schedule results to Excel and JSON."""

@pytest.mark.e2e
@pytest.mark.django_db
class TestDataImportWorkflow:
    def test_import_csv_and_schedule(self, client, tmp_path):
        """Upload CSV data, create request, solve, and verify results."""

@pytest.mark.e2e
@pytest.mark.django_db
class TestHTMXInteractions:
    def test_htmx_create_returns_partial(self, client):
        """HTMX requests return partial HTML, not full pages."""

    def test_htmx_delete_removes_element(self, client, worker):
        """HTMX delete returns empty response for DOM removal."""

    def test_non_htmx_returns_full_page(self, client):
        """Non-HTMX requests return full HTML pages."""
```

## Acceptance Criteria

- [ ] Tests written before implementation
- [ ] Complete scheduling workflow tested end-to-end
- [ ] Data import to schedule workflow tested
- [ ] HTMX partial vs full page responses verified
- [ ] Tests marked with `@pytest.mark.e2e`
- [ ] Background solver completion handled in tests
- [ ] All 10 tests pass
- [ ] ruff and mypy clean
- [ ] Frequent, focused commits
