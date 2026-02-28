---
id: scheduler-134
title: "Replace alert() with Event Popover"
type: task
status: open
priority: 2
created: 2026-02-27
updated: 2026-02-27
parent: scheduler-127
labels: [web, fullcalendar]
---

# Replace alert() with Event Popover

Replace JavaScript `alert()` calls with accessible DOM popovers and toasts in the calendar views.

## Description

The schedule calendar uses `alert()` to display event details on click, which is a poor UX pattern — it blocks the UI thread, can't be styled, and is inaccessible. The availability calendar also uses `alert()` for the "Please select a worker first" warning. This task replaces both with modern DOM-based alternatives:

1. Schedule calendar: DOM popover positioned near the clicked event
2. Availability calendar: Toast notification via the global toast system (from scheduler-132)

## Files to Modify

- `web/static/js/schedule_calendar.js` — Replace `eventClick` `alert()` with DOM popover
- `web/static/js/availability_calendar.js` — Replace `alert()` with `showToast()` call

## Implementation

### schedule_calendar.js — Event Popover

Replace the `eventClick` handler's `alert()` call (approximately lines 94-103) with a popover:

```javascript
eventClick: function(info) {
    // Remove any existing popover
    const existing = document.getElementById('event-popover');
    if (existing) existing.remove();

    const event = info.event;
    const props = event.extendedProps;

    // Create popover element
    const popover = document.createElement('div');
    popover.id = 'event-popover';
    popover.setAttribute('role', 'tooltip');
    popover.className = 'absolute z-50 bg-white border border-gray-200 rounded-lg shadow-lg p-4 max-w-xs';

    popover.innerHTML = `
        <div class="flex justify-between items-start mb-2">
            <h3 class="font-semibold text-gray-900">${event.title}</h3>
            <button id="popover-close" class="text-gray-400 hover:text-gray-600 text-lg leading-none"
                    aria-label="Close">&times;</button>
        </div>
        <dl class="text-sm text-gray-600 space-y-1">
            <div><dt class="inline font-medium">Worker:</dt> <dd class="inline">${props.worker || 'N/A'}</dd></div>
            <div><dt class="inline font-medium">Shift:</dt> <dd class="inline">${props.shift_type || event.title}</dd></div>
            <div><dt class="inline font-medium">Time:</dt> <dd class="inline">${event.start.toLocaleTimeString()} - ${event.end ? event.end.toLocaleTimeString() : 'N/A'}</dd></div>
        </dl>
    `;

    // Position near the clicked element
    const rect = info.el.getBoundingClientRect();
    popover.style.top = (rect.bottom + window.scrollY + 4) + 'px';
    popover.style.left = (rect.left + window.scrollX) + 'px';
    document.body.appendChild(popover);

    // Close handlers
    document.getElementById('popover-close').addEventListener('click', () => popover.remove());

    // Outside click
    setTimeout(() => {
        document.addEventListener('click', function handler(e) {
            if (!popover.contains(e.target) && e.target !== info.el) {
                popover.remove();
                document.removeEventListener('click', handler);
            }
        });
    }, 0);

    // Escape key
    document.addEventListener('keydown', function handler(e) {
        if (e.key === 'Escape') {
            popover.remove();
            document.removeEventListener('keydown', handler);
        }
    });
}
```

### availability_calendar.js — Toast Instead of Alert

Replace:
```javascript
alert("Please select a worker first.");
```

With:
```javascript
showToast("Please select a worker first.", "error");
```

The `showToast()` function should already exist (it's used elsewhere in the availability page). If the global toast system from scheduler-132 is not yet in place, use a local `showToast()` that targets `#toast-container`.

## Tests (write first)

File: `tests/test_web/test_schedule_calendar.py`

```python
import pytest
from pathlib import Path


class TestScheduleCalendarNoAlert:
    def test_no_alert_in_schedule_calendar(self):
        """schedule_calendar.js does not contain alert() calls."""
        js_path = Path("web/static/js/schedule_calendar.js")
        content = js_path.read_text()
        # Should not have alert( — allow 'alert' in variable names but not function calls
        import re
        alert_calls = re.findall(r'\balert\s*\(', content)
        assert len(alert_calls) == 0, f"Found {len(alert_calls)} alert() calls"

    def test_popover_element_in_schedule_calendar(self):
        """schedule_calendar.js creates a popover with role='tooltip'."""
        js_path = Path("web/static/js/schedule_calendar.js")
        content = js_path.read_text()
        assert "popover" in content.lower() or "tooltip" in content.lower()

    def test_popover_has_close_button(self):
        """Popover includes a close button."""
        js_path = Path("web/static/js/schedule_calendar.js")
        content = js_path.read_text()
        assert "close" in content.lower() or "×" in content or "&times;" in content

    def test_popover_escape_key_handler(self):
        """Popover can be dismissed with Escape key."""
        js_path = Path("web/static/js/schedule_calendar.js")
        content = js_path.read_text()
        assert "Escape" in content


class TestAvailabilityCalendarNoAlert:
    def test_no_alert_in_availability_calendar(self):
        """availability_calendar.js does not contain alert() calls."""
        js_path = Path("web/static/js/availability_calendar.js")
        content = js_path.read_text()
        import re
        alert_calls = re.findall(r'\balert\s*\(', content)
        assert len(alert_calls) == 0, f"Found {len(alert_calls)} alert() calls"

    def test_uses_toast_instead(self):
        """availability_calendar.js uses showToast for notifications."""
        js_path = Path("web/static/js/availability_calendar.js")
        content = js_path.read_text()
        assert "showToast" in content or "toast" in content.lower()
```

## Acceptance Criteria

- [ ] Zero `alert()` calls remain in `schedule_calendar.js`
- [ ] Zero `alert()` calls remain in `availability_calendar.js`
- [ ] Event details display in an accessible popover with `role="tooltip"`
- [ ] Popover positioned near the clicked calendar event
- [ ] Popover dismissed via close button, outside click, or Escape key
- [ ] Worker selection warning uses toast notification instead of alert
- [ ] Tests pass: `uv run pytest tests/test_web/test_schedule_calendar.py`
- [ ] Lint clean: `uv run ruff check web/`
- [ ] Commit: `fix: replace alert() with accessible popover in schedule calendar`
