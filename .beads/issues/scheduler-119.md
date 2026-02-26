---
id: scheduler-119
title: "Constraint configuration UI"
type: feature
status: closed
priority: 1
created: 2026-02-21
updated: 2026-02-21
parent: scheduler-109
depends-on: scheduler-116
labels: [web, django, htmx, constraints, configuration]
---

# Constraint configuration UI

Build a web interface for viewing, enabling/disabling, and configuring scheduling constraints with their parameters.

## Description

Create a constraint configuration page where users manage which constraints are active, whether they're hard or soft, their weights, and constraint-specific parameters. The page lists all available constraint types (from the constraint library) and allows per-constraint configuration via inline forms.

## Files to Create

- `web/core/forms.py` - Add ConstraintConfigForm (or modify existing)
- `web/core/views/constraint_views.py` - Constraint configuration views
- `web/templates/constraints/constraint_list.html` - Constraint list page
- `web/templates/constraints/constraint_form.html` - Inline edit form partial
- `web/templates/constraints/constraint_row.html` - Single constraint row partial
- `tests/test_web/test_constraint_views.py` - Constraint view tests

## Files to Modify

- `web/core/urls.py` - Add constraint URL patterns

## Implementation

### URL Patterns

```python
urlpatterns += [
    path("constraints/", ConstraintListView.as_view(), name="constraint-list"),
    path("constraints/<int:pk>/edit/", ConstraintUpdateView.as_view(), name="constraint-edit"),
    path("constraints/seed/", ConstraintSeedView.as_view(), name="constraint-seed"),
]
```

### Constraint List Display

Table columns:
- Constraint type name (human-readable)
- Enabled toggle (checkbox via HTMX)
- Hard/Soft toggle
- Weight (editable field, only visible when soft)
- Parameters (expandable section)
- Description of what the constraint does

### Seed Endpoint

Populates default constraint configurations from the constraint library:
```python
def seed_constraints():
    """Create ConstraintConfig entries for all registered constraint types."""
    for constraint_type in get_registered_constraints():
        ConstraintConfig.objects.get_or_create(
            constraint_type=constraint_type.name,
            defaults={...}
        )
```

### HTMX Interactions

- Toggle enabled/disabled via checkbox click (no form submit)
- Toggle hard/soft via radio or toggle switch
- Weight slider or input field, auto-saves on change
- Parameters section expands inline with JSON or structured form

### Parameter Editing

For constraints with parameters, show either:
- Structured form fields for known parameter types
- JSON textarea for advanced/custom parameters

## Tests (write first)

```python
class TestConstraintListView:
    def test_constraint_list_returns_200(self, client):
        """Constraint list page returns HTTP 200."""

    def test_constraint_list_shows_all_constraints(self, client, constraints):
        """All configured constraints are displayed."""

    def test_constraint_list_shows_enabled_status(self, client, constraints):
        """Each constraint shows whether it is enabled."""

class TestConstraintUpdateView:
    def test_toggle_constraint_enabled(self, client, constraint):
        """Toggling enabled status updates the database."""

    def test_toggle_hard_soft(self, client, constraint):
        """Switching hard/soft mode updates the database."""

    def test_update_weight(self, client, constraint):
        """Changing weight value updates the database."""

    def test_update_parameters(self, client, constraint):
        """Updating parameters JSON saves correctly."""

class TestConstraintSeedView:
    def test_seed_creates_default_constraints(self, client):
        """Seed endpoint creates entries for all registered constraint types."""

    def test_seed_idempotent(self, client, constraints):
        """Seeding when constraints already exist does not duplicate."""
```

## Acceptance Criteria

- [ ] Tests written before implementation
- [ ] Constraint list page displays all configured constraints
- [ ] Enable/disable toggle works via HTMX
- [ ] Hard/soft toggle shows/hides weight field
- [ ] Weight and parameters are editable inline
- [ ] Seed endpoint populates defaults from constraint library
- [ ] All 9 tests pass
- [ ] ruff and mypy clean
- [ ] Frequent, focused commits
