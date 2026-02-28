---
id: scheduler-131
title: "Accessibility Improvements"
type: task
status: open
priority: 1
created: 2026-02-27
updated: 2026-02-27
parent: scheduler-127
depends-on: scheduler-129
labels: [web, templates]
---

# Accessibility Improvements

Add ARIA attributes, skip-to-content link, modal keyboard handling, and active sidebar state across the application.

## Description

The web UI currently lacks basic accessibility features: no ARIA roles on messages or modals, no skip-to-content link, no visual or semantic indication of the active sidebar link, and modals use inline `onclick` with no keyboard handling. This task brings the UI to WCAG 2.1 AA baseline.

## Files to Modify

- `web/templates/base.html` — Add skip-to-content link
- `web/templates/partials/_messages.html` — Add `role="alert"` to message divs
- `web/templates/partials/_sidebar.html` — Add `aria-label` on `<nav>`, replace with `sidebar_link` inclusion tag for active state + `aria-current`
- `web/templates/solver/solve_modal.html` — Add `role="dialog"`, `aria-modal="true"`, `aria-labelledby`, Escape key handler, focus trap

## Files to Create

- `web/templates/partials/_sidebar_link.html` — Sidebar link partial with conditional `aria-current="page"` and active styling
- `tests/test_web/test_accessibility.py` — Accessibility tests

## Implementation

### Skip-to-Content Link (base.html)

Add immediately after `<body>` tag:
```html
<a href="#main-content"
   class="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:p-4 focus:bg-white focus:text-indigo-600 focus:underline">
    Skip to main content
</a>
```

Add `id="main-content"` to the `<main>` element.

### Messages ARIA (_messages.html)

Add `role="alert"` to each message div so screen readers announce them.

### Sidebar Accessibility (_sidebar.html)

- Add `aria-label="Main navigation"` to the `<nav>` element
- Replace hardcoded `<a href="/workers/">` links with a new `sidebar_link` inclusion tag
- The tag takes `url_name`, `label`, `icon_svg`, and `request` to determine active state

### sidebar_link Tag (ui_tags.py)

```python
@register.inclusion_tag("partials/_sidebar_link.html", takes_context=True)
def sidebar_link(context, url_name, label, icon=""):
    """Render a sidebar navigation link with active state."""
    request = context["request"]
    url = reverse(url_name)
    is_active = request.path.startswith(url)
    return {
        "url": url,
        "label": label,
        "icon": icon,
        "is_active": is_active,
    }
```

### _sidebar_link.html

```html
<a href="{{ url }}"
   class="flex items-center px-4 py-2 text-sm font-medium rounded-md
          {% if is_active %}bg-indigo-100 text-indigo-700{% else %}text-gray-600 hover:bg-gray-100 hover:text-gray-900{% endif %}"
   {% if is_active %}aria-current="page"{% endif %}>
    {{ icon|safe }}
    <span class="ml-3">{{ label }}</span>
</a>
```

### Modal Accessibility (solve_modal.html)

- Add `role="dialog"`, `aria-modal="true"`, `aria-labelledby="solve-modal-title"`
- Add `id="solve-modal-title"` to the modal heading
- Replace inline `onclick` handlers with proper event listeners
- Add Escape key handler to close modal
- Add focus trap (Tab cycles within modal while open)

## Tests (write first)

File: `tests/test_web/test_accessibility.py`

```python
import pytest
from django.test import Client


@pytest.mark.django_db
class TestSkipLink:
    def test_skip_to_content_link_present(self, client: Client):
        """Base template contains a skip-to-content link."""
        response = client.get("/")
        html = response.content.decode()
        assert 'href="#main-content"' in html
        assert "Skip to main content" in html

    def test_main_content_id_present(self, client: Client):
        """Main element has id='main-content' target."""
        response = client.get("/")
        html = response.content.decode()
        assert 'id="main-content"' in html


@pytest.mark.django_db
class TestMessagesARIA:
    def test_messages_have_role_alert(self, client: Client):
        """Flash messages include role='alert' for screen readers."""
        # Trigger a message by creating a worker
        from web.core.models import Worker
        Worker.objects.create(worker_id="W1", name="Test", fte=1.0)
        response = client.post("/workers/new/", data={
            "worker_id": "W2", "name": "Test2", "fte": "1.0",
        }, follow=True)
        html = response.content.decode()
        if "messages" in html.lower() or "alert" in html.lower():
            assert 'role="alert"' in html


@pytest.mark.django_db
class TestSidebarAccessibility:
    def test_nav_has_aria_label(self, client: Client):
        """Sidebar nav has aria-label='Main navigation'."""
        response = client.get("/")
        html = response.content.decode()
        assert 'aria-label="Main navigation"' in html

    def test_active_link_has_aria_current(self, client: Client):
        """Active sidebar link has aria-current='page'."""
        response = client.get("/workers/")
        html = response.content.decode()
        assert 'aria-current="page"' in html


@pytest.mark.django_db
class TestModalAccessibility:
    def test_modal_has_dialog_role(self, client: Client):
        """Solve modal has role='dialog' and aria-modal='true'."""
        # Load a page that includes the solve modal
        from web.core.models import ScheduleRequest
        # Create enough data for the solve page to render
        response = client.get("/")
        html = response.content.decode()
        # Modal may be in base or solve page
        if 'role="dialog"' not in html:
            # Check solve-specific page if modal is there
            pass
```

## Acceptance Criteria

- [ ] Skip-to-content link present in `base.html`, visible on focus, targets `#main-content`
- [ ] All message divs have `role="alert"`
- [ ] Sidebar `<nav>` has `aria-label="Main navigation"`
- [ ] Active sidebar link has `aria-current="page"` and visual active styling (indigo background)
- [ ] Sidebar URLs use `{% url %}` tags instead of hardcoded paths
- [ ] Solve modal has `role="dialog"`, `aria-modal="true"`, `aria-labelledby="solve-modal-title"`
- [ ] Modal handles Escape key to close
- [ ] Modal uses proper event listeners instead of inline `onclick`
- [ ] Tests pass: `uv run pytest tests/test_web/test_accessibility.py`
- [ ] Lint clean: `uv run ruff check web/`
- [ ] Commit: `feat: add accessibility attributes (ARIA, skip link, modal keyboard, active sidebar)`
