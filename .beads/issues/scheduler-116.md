---
id: scheduler-116
title: "Shift type CRUD views with HTMX"
type: feature
status: closed
priority: 1
created: 2026-02-21
updated: 2026-02-21
parent: scheduler-109
depends-on: [scheduler-113, scheduler-112]
labels: [web, django, htmx, crud, shifts]
---

# Shift type CRUD views with HTMX

Build HTMX-powered CRUD views for managing shift types: list, create, edit, delete with inline forms.

## Description

Create a full CRUD interface for shift types following the same HTMX patterns established in the worker CRUD views. The shift type list shows all defined shifts with their time, duration, and coverage requirements. Users can add, edit, and remove shift types dynamically.

## Files to Create

- `web/core/forms.py` - Add ShiftTypeForm (ModelForm) (or modify if already created)
- `web/core/views/shift_views.py` - ShiftType CRUD views
- `web/templates/shifts/shift_list.html` - Shift type list page
- `web/templates/shifts/shift_form.html` - Create/edit form partial
- `web/templates/shifts/shift_row.html` - Single table row partial
- `web/templates/shifts/shift_confirm_delete.html` - Delete confirmation partial
- `tests/test_web/test_shift_views.py` - Shift type view tests

## Files to Modify

- `web/core/urls.py` - Add shift type URL patterns

## Implementation

### URL Patterns

```python
urlpatterns += [
    path("shifts/", ShiftTypeListView.as_view(), name="shift-list"),
    path("shifts/create/", ShiftTypeCreateView.as_view(), name="shift-create"),
    path("shifts/<int:pk>/edit/", ShiftTypeUpdateView.as_view(), name="shift-edit"),
    path("shifts/<int:pk>/delete/", ShiftTypeDeleteView.as_view(), name="shift-delete"),
]
```

### ShiftTypeForm

```python
class ShiftTypeForm(forms.ModelForm):
    class Meta:
        model = ShiftType
        fields = ["shift_type_id", "name", "category", "start_time",
                  "duration_hours", "min_workers", "max_workers", "is_active"]
```

### Table Display

Columns: ID, Name, Category, Start Time, Duration, Min/Max Workers, Active, Actions

### HTMX Patterns

Same patterns as worker CRUD: inline create/edit forms, HTMX partial swaps, delete confirmation.

## Tests (write first)

```python
class TestShiftTypeListView:
    def test_shift_list_returns_200(self, client):
        """Shift type list page returns HTTP 200."""

    def test_shift_list_shows_all_types(self, client, shift_types):
        """Shift type list displays all shift types."""

    def test_shift_list_empty_state(self, client):
        """Shift type list shows empty state when none exist."""

class TestShiftTypeCreateView:
    def test_create_shift_type_get_returns_form(self, client):
        """GET request returns the shift type creation form."""

    def test_create_shift_type_post_valid(self, client):
        """POST with valid data creates a new shift type."""

    def test_create_shift_type_post_invalid_duration(self, client):
        """POST with zero or negative duration returns error."""

    def test_create_shift_type_htmx_returns_partial(self, client):
        """HTMX POST returns a partial row, not full page."""

class TestShiftTypeUpdateView:
    def test_update_shift_type_post_valid(self, client, shift_type):
        """POST with valid data updates the shift type."""

class TestShiftTypeDeleteView:
    def test_delete_shift_type_removes_from_db(self, client, shift_type):
        """Confirming delete removes the shift type."""

    def test_delete_shift_type_htmx_removes_row(self, client, shift_type):
        """HTMX delete returns empty response to remove row."""
```

## Acceptance Criteria

- [ ] Tests written before implementation
- [ ] Shift type list page displays all shift types in a table
- [ ] Create shift type form validates and saves via HTMX
- [ ] Edit shift type inline form updates without page reload
- [ ] Delete shift type with confirmation
- [ ] Time and duration fields validated
- [ ] All 10 tests pass
- [ ] ruff and mypy clean
- [ ] Frequent, focused commits
