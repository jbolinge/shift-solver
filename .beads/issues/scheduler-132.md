---
id: scheduler-132
title: "Messages Auto-Dismiss & Global Toast System"
type: task
status: open
priority: 2
created: 2026-02-27
updated: 2026-02-27
parent: scheduler-127
depends-on: scheduler-131
labels: [web, templates, tailwind]
---

# Messages Auto-Dismiss & Global Toast System

Implement auto-dismissing flash messages and consolidate the toast notification system from the availability page into a global system available on all pages.

## Description

Flash messages currently persist until the user navigates away — there's no way to dismiss them. The availability page has its own inline toast system with `<style>` block and `#toast-container` that should be global. This task:

1. Adds a dismiss button and auto-dismiss timer to flash messages
2. Moves toast CSS animations to `custom.css`
3. Creates a global `#toast-container` in `base.html`
4. Removes the duplicate inline toast system from `availability_page.html`

## Files to Modify

- `web/static/css/custom.css` — Add toast animation keyframes and utility classes
- `web/templates/availability/availability_page.html` — Remove inline `<style>` block and `#toast-container` div
- `web/templates/base.html` — Add `<link>` to `custom.css`, add global `#toast-container`
- `web/templates/partials/_messages.html` — Add dismiss button, `data-auto-dismiss` attribute, auto-dismiss script

## Implementation

### custom.css Additions

```css
/* Toast animations */
@keyframes toast-in {
    from { transform: translateX(100%); opacity: 0; }
    to   { transform: translateX(0);    opacity: 1; }
}

@keyframes toast-out {
    from { transform: translateX(0);    opacity: 1; }
    to   { transform: translateX(100%); opacity: 0; }
}

.toast-enter {
    animation: toast-in 0.3s ease-out forwards;
}

.toast-exit {
    animation: toast-out 0.3s ease-in forwards;
}
```

### base.html Changes

Add in `<head>`:
```html
{% load static %}
<link rel="stylesheet" href="{% static 'css/custom.css' %}">
```

Add before `{% block extra_js %}`:
```html
<div id="toast-container"
     class="fixed top-4 right-4 z-50 flex flex-col gap-2"
     role="status"
     aria-live="polite">
</div>
```

### _messages.html Changes

Each message gets:
- A dismiss button (`×`) aligned to the right
- `data-auto-dismiss="5000"` attribute for 5-second auto-dismiss
- Small inline script at the bottom that finds all `[data-auto-dismiss]` elements and sets timeouts

```html
{% for message in messages %}
<div role="alert" data-auto-dismiss="5000"
     class="flex items-center justify-between rounded-md p-4 mb-2 ...">
    <span>{{ message }}</span>
    <button type="button" onclick="this.parentElement.remove()"
            class="ml-4 text-lg leading-none opacity-60 hover:opacity-100"
            aria-label="Dismiss">&times;</button>
</div>
{% endfor %}

<script>
document.querySelectorAll('[data-auto-dismiss]').forEach(el => {
    const ms = parseInt(el.dataset.autoDismiss, 10);
    setTimeout(() => {
        el.style.transition = 'opacity 0.3s';
        el.style.opacity = '0';
        setTimeout(() => el.remove(), 300);
    }, ms);
});
</script>
```

### availability_page.html Cleanup

Remove:
- The inline `<style>` block containing toast keyframe definitions
- The `<div id="toast-container">` element (now in base.html)
- Update JavaScript `showToast()` function to use the global container (it should already reference `#toast-container` by ID)

## Tests (write first)

File: `tests/test_web/test_messages.py`

```python
import pytest
from pathlib import Path


class TestToastCSS:
    def test_custom_css_contains_toast_keyframes(self):
        """custom.css defines toast-in and toast-out animations."""
        css_path = Path("web/static/css/custom.css")
        css = css_path.read_text()
        assert "toast-in" in css
        assert "toast-out" in css
        assert "@keyframes" in css

    def test_custom_css_contains_toast_classes(self):
        """custom.css defines .toast-enter and .toast-exit classes."""
        css_path = Path("web/static/css/custom.css")
        css = css_path.read_text()
        assert ".toast-enter" in css
        assert ".toast-exit" in css


@pytest.mark.django_db
class TestMessagesDismiss:
    def test_messages_have_dismiss_button(self, client):
        """Flash messages include a dismiss button."""
        # Create a worker to trigger a success message
        response = client.post("/workers/new/", data={
            "worker_id": "W1", "name": "Test", "fte": "1.0",
        }, follow=True)
        html = response.content.decode()
        if "alert" in html.lower() or "message" in html.lower():
            assert "Dismiss" in html or "&times;" in html or "×" in html

    def test_messages_have_auto_dismiss_attribute(self, client):
        """Flash messages include data-auto-dismiss attribute."""
        response = client.post("/workers/new/", data={
            "worker_id": "W2", "name": "Test2", "fte": "1.0",
        }, follow=True)
        html = response.content.decode()
        if "alert" in html.lower():
            assert "data-auto-dismiss" in html


@pytest.mark.django_db
class TestGlobalToastContainer:
    def test_base_has_toast_container(self, client):
        """base.html includes a global #toast-container."""
        response = client.get("/")
        html = response.content.decode()
        assert 'id="toast-container"' in html

    def test_toast_container_has_aria_live(self, client):
        """Global toast container has aria-live='polite'."""
        response = client.get("/")
        html = response.content.decode()
        assert 'aria-live="polite"' in html

    def test_availability_page_no_inline_toast_styles(self, client):
        """Availability page no longer has inline toast style block."""
        # Just check the template file directly
        template_path = Path("web/templates/availability/availability_page.html")
        if template_path.exists():
            content = template_path.read_text()
            assert "@keyframes toast-in" not in content
```

## Acceptance Criteria

- [ ] Flash messages auto-dismiss after 5 seconds (configurable via `data-auto-dismiss`)
- [ ] Each message has a manual dismiss button (×) with `aria-label="Dismiss"`
- [ ] Toast animations (`toast-in`, `toast-out`) defined in `custom.css`, not inline
- [ ] Global `#toast-container` exists in `base.html` with `role="status"` and `aria-live="polite"`
- [ ] Inline toast styles/container removed from `availability_page.html`
- [ ] `custom.css` loaded in `<head>` of `base.html` via `{% static %}`
- [ ] Tests pass: `uv run pytest tests/test_web/test_messages.py`
- [ ] Lint clean: `uv run ruff check web/`
- [ ] Commit: `feat: add message auto-dismiss, global toast CSS, and ARIA for messages`
