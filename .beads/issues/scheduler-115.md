---
id: scheduler-115
title: "Worker CRUD views with HTMX"
type: feature
status: closed
priority: 1
created: 2026-02-21
updated: 2026-02-21
parent: scheduler-109
depends-on: [scheduler-113, scheduler-112]
labels: [web, django, htmx, crud, workers]
---

# Worker CRUD views with HTMX

Build HTMX-powered CRUD views for managing workers: list, create, edit, delete with inline forms and partial page updates.

## Description

Create a full CRUD interface for workers using Django views and HTMX for seamless interactions. The worker list page shows all workers in a table with inline edit/delete. Creating and editing workers uses modal or inline forms submitted via HTMX without full page reloads.

## Files to Create

- `web/core/forms.py` - WorkerForm (ModelForm)
- `web/core/views/worker_views.py` - Worker CRUD views
- `web/core/urls.py` - Core app URL configuration
- `web/templates/workers/worker_list.html` - Worker list page
- `web/templates/workers/worker_form.html` - Create/edit form partial
- `web/templates/workers/worker_row.html` - Single table row partial (for HTMX swap)
- `web/templates/workers/worker_confirm_delete.html` - Delete confirmation partial
- `tests/test_web/test_worker_views.py` - Worker view tests

## Files to Modify

- `web/config/urls.py` - Include core app URLs

## Implementation

### URL Patterns

```python
# web/core/urls.py
urlpatterns = [
    path("workers/", WorkerListView.as_view(), name="worker-list"),
    path("workers/create/", WorkerCreateView.as_view(), name="worker-create"),
    path("workers/<int:pk>/edit/", WorkerUpdateView.as_view(), name="worker-edit"),
    path("workers/<int:pk>/delete/", WorkerDeleteView.as_view(), name="worker-delete"),
]
```

### HTMX Interaction Patterns

1. **List page**: Full page with table of workers
2. **Create**: Click "Add Worker" button -> HTMX fetches form partial -> submit via HTMX -> new row swapped into table
3. **Edit**: Click edit icon -> HTMX swaps row with inline form -> submit -> updated row swapped back
4. **Delete**: Click delete icon -> confirmation partial -> confirm -> row removed from DOM

### Views

- Views detect HTMX requests via `request.headers.get("HX-Request")` and return partials vs full pages accordingly
- Form validation errors returned as HTMX partial with error styling
- Success responses use `HX-Trigger` header for toast notifications

## Tests (write first)

```python
class TestWorkerListView:
    def test_worker_list_returns_200(self, client):
        """Worker list page returns HTTP 200."""

    def test_worker_list_shows_all_workers(self, client, workers):
        """Worker list displays all workers in the database."""

    def test_worker_list_empty_state(self, client):
        """Worker list shows empty state message when no workers exist."""

class TestWorkerCreateView:
    def test_create_worker_get_returns_form(self, client):
        """GET request returns the worker creation form."""

    def test_create_worker_post_valid(self, client):
        """POST with valid data creates a new worker."""

    def test_create_worker_post_invalid(self, client):
        """POST with invalid data returns form with errors."""

    def test_create_worker_htmx_returns_partial(self, client):
        """HTMX POST returns a partial row, not full page."""

class TestWorkerUpdateView:
    def test_update_worker_get_returns_form(self, client, worker):
        """GET request returns pre-filled edit form."""

    def test_update_worker_post_valid(self, client, worker):
        """POST with valid data updates the worker."""

class TestWorkerDeleteView:
    def test_delete_worker_removes_from_db(self, client, worker):
        """Confirming delete removes the worker from the database."""

    def test_delete_worker_htmx_removes_row(self, client, worker):
        """HTMX delete returns empty response to remove row from DOM."""
```

## Acceptance Criteria

- [ ] Tests written before implementation
- [ ] Worker list page displays all workers in a table
- [ ] Create worker form validates and saves via HTMX
- [ ] Edit worker inline form updates without page reload
- [ ] Delete worker with confirmation removes from table
- [ ] Form validation errors display inline
- [ ] All 11 tests pass
- [ ] ruff and mypy clean
- [ ] Frequent, focused commits
