---
id: scheduler-113
title: "Base templates, Tailwind CSS, HTMX setup"
type: task
status: closed
priority: 1
created: 2026-02-21
updated: 2026-02-21
parent: scheduler-109
depends-on: scheduler-110
labels: [web, django, templates, tailwind, htmx]
---

# Base templates, Tailwind CSS, HTMX setup

Set up the base HTML template structure with Tailwind CSS for styling and HTMX for dynamic interactions.

## Description

Create the base template hierarchy with a responsive layout, navigation sidebar, and content area. Integrate Tailwind CSS (via CDN for simplicity) and HTMX. Set up the template patterns that all subsequent views will extend.

## Files to Create

- `web/templates/base.html` - Master template with Tailwind + HTMX
- `web/templates/partials/_navbar.html` - Top navigation bar partial
- `web/templates/partials/_sidebar.html` - Left sidebar navigation partial
- `web/templates/partials/_messages.html` - Flash messages partial
- `web/templates/home.html` - Landing/dashboard page
- `web/core/views.py` - Home view
- `web/static/css/custom.css` - Minimal custom styles
- `tests/test_web/test_templates.py` - Template tests

## Files to Modify

- `web/config/urls.py` - Add home URL route

## Implementation

### Base Template Structure

```html
<!-- web/templates/base.html -->
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Shift Solver{% endblock %}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/htmx.org@2.0.0"></script>
    {% block extra_head %}{% endblock %}
</head>
<body class="bg-gray-50 min-h-screen">
    {% include "partials/_navbar.html" %}
    <div class="flex">
        {% include "partials/_sidebar.html" %}
        <main class="flex-1 p-6">
            {% include "partials/_messages.html" %}
            {% block content %}{% endblock %}
        </main>
    </div>
    {% block extra_js %}{% endblock %}
</body>
</html>
```

### Sidebar Navigation

Links to main sections:
- Dashboard (home)
- Workers
- Shift Types
- Availability
- Constraints
- Solver
- Schedule

### HTMX Patterns

- `hx-target="#content"` for main content area swaps
- `hx-swap="innerHTML"` as default swap strategy
- `hx-indicator` for loading spinners
- `hx-push-url="true"` for URL updates on navigation

### Home View

Simple dashboard showing counts: workers, shift types, active schedules.

## Tests (write first)

```python
class TestBaseTemplates:
    def test_home_page_returns_200(self, client):
        """Home page returns HTTP 200."""

    def test_home_page_contains_tailwind(self, client):
        """Base template includes Tailwind CSS CDN."""

    def test_home_page_contains_htmx(self, client):
        """Base template includes HTMX script."""

    def test_home_page_has_sidebar_navigation(self, client):
        """Home page includes sidebar with navigation links."""

    def test_home_page_has_navbar(self, client):
        """Home page includes top navigation bar."""

    def test_base_template_has_content_block(self):
        """Base template defines a 'content' block."""
```

## Acceptance Criteria

- [ ] Tests written before implementation
- [ ] Base template loads Tailwind CSS and HTMX
- [ ] Responsive sidebar layout works at desktop and mobile widths
- [ ] Navigation links present for all main sections
- [ ] Home page renders with dashboard content
- [ ] Flash messages display correctly
- [ ] All 6 tests pass
- [ ] ruff and mypy clean
- [ ] Frequent, focused commits
