---
id: scheduler-130
title: "Adopt Template Tags Across Templates"
type: task
status: open
priority: 1
created: 2026-02-27
updated: 2026-02-27
parent: scheduler-127
depends-on: scheduler-129
labels: [web, templates]
---

# Adopt Template Tags Across Templates

Replace duplicated badge HTML and form field loops with the new `{% status_badge %}` and `{% render_field %}` template tags across all templates.

## Description

With the template tag library from scheduler-129 in place, this task replaces all copy-pasted badge HTML and manual form field rendering loops across ~11 templates. This also enables help text to appear on all forms for the first time.

## Files to Modify

### Form templates (replace field loops with `{% render_field %}`):
- `web/templates/workers/worker_form.html`
- `web/templates/shifts/shift_form.html`
- `web/templates/requests/request_form.html`
- `web/templates/worker_requests/worker_request_form.html`
- `web/templates/constraints/constraint_form.html`
- `web/templates/settings/settings_form.html`

### Row/detail templates (replace badge HTML with `{% status_badge %}`):
- `web/templates/workers/worker_row.html`
- `web/templates/shifts/shift_row.html`
- `web/templates/constraints/constraint_row.html`
- `web/templates/requests/request_row.html`
- `web/templates/requests/request_detail.html` (status + worker request type/enforcement badges)
- `web/templates/worker_requests/worker_request_row.html`
- `web/templates/solver/solve_results.html`
- `web/templates/solver/solve_validation.html`

## Implementation

### Form Templates Pattern

Before:
```html
{% for field in form %}
<div class="mb-4">
    <label for="{{ field.id_for_label }}" class="block text-sm font-medium text-gray-700 mb-1">
        {{ field.label }}
    </label>
    {{ field }}
    {% for error in field.errors %}
        <p class="mt-1 text-sm text-red-600">{{ error }}</p>
    {% endfor %}
</div>
{% endfor %}
```

After:
```html
{% load ui_tags %}
{% for field in form %}
    {% render_field field %}
{% endfor %}
```

### Badge Templates Pattern

Before:
```html
<span class="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium bg-green-100 text-green-800">
    Active
</span>
```

After:
```html
{% load ui_tags %}
{% status_badge "Active" "green" %}
```

### Color Mapping for Existing Badges

Map existing badge colors to the `status_badge` color parameter:
- Active/Enabled/Feasible → `"green"`
- Inactive/Disabled/Infeasible → `"red"`
- Pending/Draft → `"yellow"`
- Running/In Progress → `"blue"`
- Hard constraint → `"indigo"`
- Soft constraint → `"purple"`
- Default/Other → `"gray"`

## Tests (write first)

File: `tests/test_web/test_ui_rendering.py`

```python
import pytest
from django.test import Client


@pytest.mark.django_db
class TestFormRendering:
    def test_worker_form_shows_help_text(self, client: Client):
        """Worker form page renders help text for fields that define it."""
        response = client.get("/workers/new/")
        html = response.content.decode()
        assert "text-gray-500" in html  # Help text styling

    def test_shift_form_shows_help_text(self, client: Client):
        """Shift form page renders help text."""
        response = client.get("/shifts/new/")
        html = response.content.decode()
        assert "text-gray-500" in html

    def test_form_errors_render_in_red(self, client: Client):
        """Form validation errors appear with red styling."""
        response = client.post("/workers/new/", data={})
        html = response.content.decode()
        assert "text-red-600" in html


@pytest.mark.django_db
class TestBadgeRendering:
    def test_worker_row_uses_badge_tag(self, client: Client, worker):
        """Worker list renders status badges with correct colors."""
        response = client.get("/workers/")
        html = response.content.decode()
        assert "rounded-full" in html  # Badge styling
        assert "bg-green-100" in html or "bg-red-100" in html

    def test_constraint_row_uses_badge_tag(self, client: Client, constraint):
        """Constraint list renders type badges (hard/soft)."""
        response = client.get("/constraints/")
        html = response.content.decode()
        assert "rounded-full" in html
```

## Acceptance Criteria

- [ ] All form templates use `{% render_field %}` instead of manual field rendering
- [ ] All badge HTML across 8+ row/detail templates replaced with `{% status_badge %}`
- [ ] Help text now visibly appears on all form pages
- [ ] No visual regressions — pages render identically (with the addition of help text)
- [ ] `{% load ui_tags %}` present at top of every modified template
- [ ] Tests pass: `uv run pytest tests/test_web/test_ui_rendering.py`
- [ ] Lint clean: `uv run ruff check web/`
- [ ] Commit: `refactor: adopt template tags for badges and form fields across all templates`
