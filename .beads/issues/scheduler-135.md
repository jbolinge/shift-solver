---
id: scheduler-135
title: "Dashboard Enhancement & HTMX Loading Indicator"
type: task
status: open
priority: 2
created: 2026-02-27
updated: 2026-02-27
parent: scheduler-127
labels: [web, django, htmx]
---

# Dashboard Enhancement & HTMX Loading Indicator

Enhance the dashboard with summary cards, quick actions, recent activity, and add a global HTMX loading indicator bar.

## Description

The current dashboard is sparse — it shows basic counts but lacks quick actions, recent activity, or a constraints summary. There's also no visual feedback during HTMX requests. This task:

1. Adds a 4th summary card (Constraints) to the dashboard
2. Adds a "Quick Actions" section with common task links
3. Adds "Recent Requests" and "Recent Solver Runs" sections
4. Replaces hardcoded URLs with `{% url %}` tags
5. Adds a global HTMX loading indicator bar to `base.html`

## Files to Modify

- `web/core/views/home.py` — Add constraint count, recent requests, recent runs to context
- `web/templates/home.html` — Add 4th card, quick actions, recent activity sections, use `{% url %}` tags
- `web/templates/base.html` — Add HTMX loading indicator

## Implementation

### home.py Context Additions

```python
from web.core.models import ConstraintConfig, SolverRun, ScheduleRequest

def home(request):
    context = {
        # ... existing counts ...
        "constraint_count": ConstraintConfig.objects.count(),
        "recent_requests": ScheduleRequest.objects.order_by("-created_at")[:5],
        "recent_runs": SolverRun.objects.order_by("-created_at")[:3],
    }
    return render(request, "home.html", context)
```

### home.html Template Changes

**4th Summary Card:**
```html
<div class="bg-white rounded-lg shadow p-6">
    <h3 class="text-sm font-medium text-gray-500">Constraints</h3>
    <p class="mt-2 text-3xl font-semibold text-gray-900">{{ constraint_count }}</p>
    <a href="{% url 'constraint-list' %}" class="mt-1 text-sm text-indigo-600 hover:text-indigo-500">
        Manage &rarr;
    </a>
</div>
```

**Quick Actions Section:**
```html
<div class="mt-8">
    <h2 class="text-lg font-medium text-gray-900 mb-4">Quick Actions</h2>
    <div class="flex flex-wrap gap-3">
        <a href="{% url 'worker-create' %}" class="inline-flex items-center px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50">
            Add Worker
        </a>
        <a href="{% url 'shift-create' %}" class="...">Add Shift Type</a>
        <a href="{% url 'request-create' %}" class="...">New Request</a>
    </div>
</div>
```

**Recent Requests Mini-Table:**
```html
<div class="mt-8">
    <h2 class="text-lg font-medium text-gray-900 mb-4">Recent Requests</h2>
    {% if recent_requests %}
    <div class="bg-white shadow rounded-lg overflow-hidden">
        <table class="min-w-full divide-y divide-gray-200">
            <thead class="bg-gray-50">
                <tr>
                    <th class="px-4 py-2 text-left text-xs font-medium text-gray-500">Name</th>
                    <th class="px-4 py-2 text-left text-xs font-medium text-gray-500">Status</th>
                    <th class="px-4 py-2 text-left text-xs font-medium text-gray-500">Created</th>
                </tr>
            </thead>
            <tbody class="divide-y divide-gray-200">
                {% for req in recent_requests %}
                <tr>
                    <td class="px-4 py-2 text-sm"><a href="{% url 'request-detail' req.pk %}">{{ req.name }}</a></td>
                    <td class="px-4 py-2 text-sm">{% status_badge req.status req.status_color %}</td>
                    <td class="px-4 py-2 text-sm text-gray-500">{{ req.created_at|date:"M d" }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
    {% else %}
        <p class="text-gray-500 text-sm">No requests yet.</p>
    {% endif %}
</div>
```

**Replace All Hardcoded URLs:**
- `href="/workers/"` → `href="{% url 'worker-list' %}"`
- `href="/shifts/"` → `href="{% url 'shift-list' %}"`
- `href="/requests/"` → `href="{% url 'request-list' %}"`
- etc.

### base.html — HTMX Loading Indicator

Add immediately after `<body>` (after skip link if present):
```html
<div id="global-loading"
     class="htmx-indicator fixed top-0 left-0 right-0 h-1 bg-indigo-500 z-50"
     style="transition: opacity 0.2s; opacity: 0;">
</div>
```

Add to `<body>` tag:
```html
<body hx-indicator="#global-loading">
```

The `htmx-indicator` class is built into HTMX — it automatically shows/hides elements with this class during requests.

## Tests (write first)

File: `tests/test_web/test_dashboard.py`

```python
import pytest
from django.test import Client


@pytest.mark.django_db
class TestDashboardCards:
    def test_constraint_count_displayed(self, client: Client):
        """Dashboard shows constraint count card."""
        response = client.get("/")
        html = response.content.decode()
        assert "Constraints" in html

    def test_all_four_cards_present(self, client: Client):
        """Dashboard has 4 summary cards: Workers, Shifts, Requests, Constraints."""
        response = client.get("/")
        html = response.content.decode()
        assert "Workers" in html
        assert "Shift" in html
        assert "Request" in html
        assert "Constraint" in html


@pytest.mark.django_db
class TestQuickActions:
    def test_quick_actions_section_present(self, client: Client):
        """Dashboard has a Quick Actions section."""
        response = client.get("/")
        html = response.content.decode()
        assert "Quick Actions" in html

    def test_quick_action_links(self, client: Client):
        """Quick actions include Add Worker, Add Shift, New Request."""
        response = client.get("/")
        html = response.content.decode()
        assert "Add Worker" in html
        assert "Add Shift" in html or "Shift Type" in html


@pytest.mark.django_db
class TestRecentActivity:
    def test_recent_requests_section(self, client: Client):
        """Dashboard has a Recent Requests section."""
        response = client.get("/")
        html = response.content.decode()
        assert "Recent Requests" in html

    def test_recent_requests_with_data(self, client: Client, schedule_request):
        """Recent requests section shows existing requests."""
        response = client.get("/")
        html = response.content.decode()
        assert schedule_request.name in html


@pytest.mark.django_db
class TestDashboardURLs:
    def test_no_hardcoded_urls(self, client: Client):
        """Dashboard does not contain hardcoded URL paths."""
        from pathlib import Path
        template = Path("web/templates/home.html").read_text()
        # Should not have href="/workers/" style hardcoded URLs
        import re
        hardcoded = re.findall(r'href="/(workers|shifts|requests|constraints)/"', template)
        assert len(hardcoded) == 0, f"Found hardcoded URLs: {hardcoded}"


@pytest.mark.django_db
class TestHTMXLoadingIndicator:
    def test_global_loading_indicator_present(self, client: Client):
        """base.html includes a global HTMX loading indicator."""
        response = client.get("/")
        html = response.content.decode()
        assert 'id="global-loading"' in html

    def test_body_has_hx_indicator(self, client: Client):
        """Body tag has hx-indicator attribute pointing to global loading."""
        response = client.get("/")
        html = response.content.decode()
        assert 'hx-indicator' in html
```

## Acceptance Criteria

- [ ] Dashboard shows 4 summary cards (Workers, Shifts, Requests, Constraints)
- [ ] All dashboard links use `{% url %}` tags, no hardcoded paths
- [ ] "Quick Actions" section present with Add Worker, Add Shift, New Request links
- [ ] "Recent Requests" mini-table shows last 5 requests with status badges
- [ ] "Recent Solver Runs" section shows last 3 runs
- [ ] Home view context includes `constraint_count`, `recent_requests`, `recent_runs`
- [ ] Global HTMX loading indicator bar at top of `base.html` with `id="global-loading"`
- [ ] `<body>` has `hx-indicator="#global-loading"` attribute
- [ ] Tests pass: `uv run pytest tests/test_web/test_dashboard.py`
- [ ] Lint clean: `uv run ruff check web/`
- [ ] Commit: `feat: enhance dashboard with quick actions and HTMX loading indicator`
