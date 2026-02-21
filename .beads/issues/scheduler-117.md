---
id: scheduler-117
title: "Availability calendar with FullCalendar"
type: feature
status: open
priority: 1
created: 2026-02-21
updated: 2026-02-21
parent: scheduler-109
depends-on: [scheduler-115, scheduler-116]
labels: [web, django, fullcalendar, availability]
---

# Availability calendar with FullCalendar

Build an interactive availability calendar using FullCalendar.io where workers can mark their available and unavailable dates.

## Description

Create a FullCalendar-based availability management interface. Users select a worker, then click/drag on calendar dates to toggle availability. The calendar displays color-coded availability status and supports per-shift-type availability with preference levels. Changes are saved via HTMX/JSON endpoints.

## Files to Create

- `web/core/views/availability_views.py` - Availability views and JSON endpoints
- `web/templates/availability/availability_page.html` - Main availability page
- `web/templates/availability/availability_form.html` - Availability edit partial
- `web/static/js/availability_calendar.js` - FullCalendar initialization and event handling
- `tests/test_web/test_availability_views.py` - Availability view tests

## Files to Modify

- `web/core/urls.py` - Add availability URL patterns

## Implementation

### URL Patterns

```python
urlpatterns += [
    path("availability/", AvailabilityPageView.as_view(), name="availability-page"),
    path("availability/events/", AvailabilityEventsView.as_view(), name="availability-events"),
    path("availability/update/", AvailabilityUpdateView.as_view(), name="availability-update"),
]
```

### FullCalendar Integration

```javascript
// web/static/js/availability_calendar.js
document.addEventListener("DOMContentLoaded", function() {
    const calendar = new FullCalendar.Calendar(el, {
        initialView: "dayGridMonth",
        selectable: true,
        editable: true,
        events: "/availability/events/?worker_id=...",
        select: function(info) { /* HTMX POST to toggle availability */ },
        eventClick: function(info) { /* Edit availability preference */ },
    });
});
```

### JSON Events Endpoint

Returns availability entries as FullCalendar events:
```json
[
    {
        "title": "Available - Day Shift",
        "start": "2026-03-01",
        "color": "#22c55e",
        "extendedProps": {"worker_id": 1, "shift_type_id": 1, "preference": 1}
    }
]
```

### Color Coding

- Green: Available (prefer)
- Light green: Available (neutral)
- Red: Unavailable
- Gray: No entry (default available)

### Worker Selector

Dropdown or sidebar list of workers. Selecting a worker refreshes the calendar via HTMX.

## Tests (write first)

```python
class TestAvailabilityPage:
    def test_availability_page_returns_200(self, client):
        """Availability page returns HTTP 200."""

    def test_availability_page_includes_fullcalendar(self, client):
        """Page includes FullCalendar JavaScript library."""

    def test_availability_page_has_worker_selector(self, client, workers):
        """Page includes worker selection dropdown."""

class TestAvailabilityEventsEndpoint:
    def test_events_returns_json(self, client, worker, availabilities):
        """Events endpoint returns JSON array."""

    def test_events_filtered_by_worker(self, client, workers, availabilities):
        """Events endpoint filters by worker_id parameter."""

    def test_events_include_correct_colors(self, client, worker, availabilities):
        """Event colors match availability preference levels."""

class TestAvailabilityUpdate:
    def test_update_creates_availability(self, client, worker, shift_type):
        """POST creates a new availability entry."""

    def test_update_toggles_existing_availability(self, client, worker, availability):
        """POST toggles an existing availability entry."""

    def test_update_requires_worker_id(self, client):
        """POST without worker_id returns 400."""
```

## Acceptance Criteria

- [ ] Tests written before implementation
- [ ] FullCalendar renders monthly calendar view
- [ ] Worker selector filters calendar to selected worker
- [ ] Click/drag on dates creates or toggles availability entries
- [ ] Color coding reflects availability status and preference
- [ ] Events endpoint returns correct JSON for FullCalendar
- [ ] All 9 tests pass
- [ ] ruff and mypy clean
- [ ] Frequent, focused commits
