---
id: scheduler-133
title: "Responsive Sidebar with Mobile Hamburger"
type: task
status: open
priority: 2
created: 2026-02-27
updated: 2026-02-27
parent: scheduler-127
depends-on: scheduler-131
labels: [web, templates, tailwind]
---

# Responsive Sidebar with Mobile Hamburger

Make the sidebar responsive — hidden on mobile with a hamburger toggle button, always visible on desktop.

## Description

The current sidebar is always visible regardless of viewport size, which wastes screen space on mobile and makes the app unusable on small screens. This task adds:

1. A hamburger button in the navbar (visible only on mobile)
2. Responsive sidebar that hides on mobile, shows on desktop
3. Toggle behavior with proper ARIA state management

## Files to Modify

- `web/templates/partials/_navbar.html` — Add hamburger toggle button
- `web/templates/partials/_sidebar.html` — Add responsive classes and `id="sidebar"`
- `web/templates/base.html` — Add toggle script

## Implementation

### _navbar.html Changes

Add hamburger button (visible only on mobile `md:hidden`):

```html
<button id="sidebar-toggle"
        type="button"
        class="md:hidden inline-flex items-center justify-center p-2 rounded-md text-gray-400 hover:text-gray-500 hover:bg-gray-100"
        aria-expanded="false"
        aria-controls="sidebar"
        aria-label="Toggle navigation">
    <!-- Hamburger SVG icon -->
    <svg class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" />
    </svg>
</button>
```

Wrap app title in a link to home:
```html
<a href="{% url 'home' %}" class="text-lg font-semibold text-gray-900">
    Shift Solver
</a>
```

### _sidebar.html Changes

Add `id="sidebar"` and responsive hiding:
```html
<aside id="sidebar"
       class="hidden md:block fixed inset-y-0 left-0 z-40 w-64 bg-white border-r border-gray-200 pt-16 overflow-y-auto">
```

On mobile, when toggled visible, the sidebar appears as a fixed overlay.

### base.html Script

Add before `</body>`:
```html
<script>
(function() {
    const toggle = document.getElementById('sidebar-toggle');
    const sidebar = document.getElementById('sidebar');
    if (toggle && sidebar) {
        toggle.addEventListener('click', function() {
            sidebar.classList.toggle('hidden');
            const expanded = !sidebar.classList.contains('hidden');
            toggle.setAttribute('aria-expanded', String(expanded));
        });
    }
})();
</script>
```

## Tests (write first)

File: `tests/test_web/test_responsive_sidebar.py`

```python
import pytest
from django.test import Client


@pytest.mark.django_db
class TestHamburgerButton:
    def test_sidebar_toggle_button_present(self, client: Client):
        """Navbar contains a sidebar toggle button."""
        response = client.get("/")
        html = response.content.decode()
        assert 'id="sidebar-toggle"' in html

    def test_toggle_button_has_aria_expanded(self, client: Client):
        """Toggle button has aria-expanded attribute."""
        response = client.get("/")
        html = response.content.decode()
        assert 'aria-expanded=' in html

    def test_toggle_button_has_aria_label(self, client: Client):
        """Toggle button has descriptive aria-label."""
        response = client.get("/")
        html = response.content.decode()
        assert 'aria-label="Toggle navigation"' in html


@pytest.mark.django_db
class TestResponsiveSidebar:
    def test_sidebar_has_id(self, client: Client):
        """Sidebar has id='sidebar' for toggle targeting."""
        response = client.get("/")
        html = response.content.decode()
        assert 'id="sidebar"' in html

    def test_sidebar_has_responsive_classes(self, client: Client):
        """Sidebar uses 'hidden md:block' for responsive behavior."""
        response = client.get("/")
        html = response.content.decode()
        # Check that sidebar has responsive hiding
        assert "md:block" in html

    def test_app_title_links_to_home(self, client: Client):
        """App title in navbar is a link to the home page."""
        response = client.get("/")
        html = response.content.decode()
        assert "Shift Solver" in html
        # Title should be wrapped in a link
```

## Acceptance Criteria

- [ ] Sidebar has `id="sidebar"` and classes `hidden md:block`
- [ ] Hamburger button with `id="sidebar-toggle"` visible on mobile (`md:hidden`)
- [ ] Clicking hamburger toggles sidebar visibility
- [ ] Button updates `aria-expanded` when toggled
- [ ] Sidebar uses fixed positioning as overlay on mobile
- [ ] App title wrapped in link to home (`{% url 'home' %}`)
- [ ] On desktop (`md:` and above), sidebar always visible, hamburger hidden
- [ ] Tests pass: `uv run pytest tests/test_web/test_responsive_sidebar.py`
- [ ] Lint clean: `uv run ruff check web/`
- [ ] Commit: `feat: add responsive sidebar with mobile hamburger toggle`
