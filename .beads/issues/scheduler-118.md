---
id: scheduler-118
title: "Scheduling request management"
type: feature
status: closed
priority: 1
created: 2026-02-21
updated: 2026-02-21
parent: scheduler-109
depends-on: scheduler-117
labels: [web, django, htmx, requests]
---

# Scheduling request management

Build views for creating and managing scheduling requests that define the date range, period configuration, and worker/shift selections for a solver run.

## Description

Create a scheduling request management interface where users define what to schedule: date range, period length, which workers to include, which shift types, and any per-request overrides. A request groups together all the inputs needed to launch a solver run.

## Files to Create

- `web/core/forms.py` - Add ScheduleRequestForm (or modify existing)
- `web/core/views/request_views.py` - ScheduleRequest CRUD views
- `web/templates/requests/request_list.html` - Request list page
- `web/templates/requests/request_detail.html` - Request detail with worker/shift selections
- `web/templates/requests/request_form.html` - Create/edit form
- `web/templates/requests/request_row.html` - Table row partial
- `tests/test_web/test_request_views.py` - Request view tests

## Files to Modify

- `web/core/urls.py` - Add request URL patterns
- `web/core/models.py` - Add ManyToMany fields for worker/shift selections if needed

## Implementation

### URL Patterns

```python
urlpatterns += [
    path("requests/", RequestListView.as_view(), name="request-list"),
    path("requests/create/", RequestCreateView.as_view(), name="request-create"),
    path("requests/<int:pk>/", RequestDetailView.as_view(), name="request-detail"),
    path("requests/<int:pk>/edit/", RequestUpdateView.as_view(), name="request-edit"),
    path("requests/<int:pk>/delete/", RequestDeleteView.as_view(), name="request-delete"),
]
```

### ScheduleRequest Enhancements

May add ManyToMany fields:
```python
workers = models.ManyToManyField(Worker, blank=True, help_text="Workers to include (all if empty)")
shift_types = models.ManyToManyField(ShiftType, blank=True, help_text="Shift types to include (all if empty)")
```

### Detail Page

Shows request summary with:
- Date range and period configuration
- Selected workers (or "All active workers")
- Selected shift types (or "All active shift types")
- Status badge (draft, running, completed, failed)
- Link to launch solver (Phase 4)
- Link to view results (Phase 5)

### HTMX Patterns

- List page with status badges
- Create/edit forms with date pickers
- Worker and shift type selection via checkboxes with "Select All"
- Status updates via HTMX polling (for solver integration later)

## Tests (write first)

```python
class TestRequestListView:
    def test_request_list_returns_200(self, client):
        """Request list page returns HTTP 200."""

    def test_request_list_shows_all_requests(self, client, requests):
        """Request list displays all schedule requests."""

    def test_request_list_shows_status_badges(self, client, requests):
        """Each request shows its status badge."""

class TestRequestCreateView:
    def test_create_request_post_valid(self, client):
        """POST with valid dates creates a new request."""

    def test_create_request_invalid_date_range(self, client):
        """POST with end_date before start_date returns error."""

    def test_create_request_default_status_draft(self, client):
        """New request has default status 'draft'."""

class TestRequestDetailView:
    def test_detail_returns_200(self, client, schedule_request):
        """Request detail page returns HTTP 200."""

    def test_detail_shows_date_range(self, client, schedule_request):
        """Detail page shows start and end dates."""

    def test_detail_shows_selected_workers(self, client, schedule_request):
        """Detail page shows which workers are included."""

class TestRequestDeleteView:
    def test_delete_request_removes_from_db(self, client, schedule_request):
        """Confirming delete removes the request."""
```

## Acceptance Criteria

- [ ] Tests written before implementation
- [ ] Request list page shows all scheduling requests with status
- [ ] Create request form with date range and period length
- [ ] Worker and shift type selection on request
- [ ] Detail page shows complete request summary
- [ ] Date validation (end >= start)
- [ ] All 10 tests pass
- [ ] ruff and mypy clean
- [ ] Frequent, focused commits
