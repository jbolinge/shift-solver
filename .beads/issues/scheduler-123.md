---
id: scheduler-123
title: "Schedule visualization with FullCalendar"
type: feature
status: closed
closed: 2026-02-26
priority: 1
created: 2026-02-21
updated: 2026-02-21
parent: scheduler-109
depends-on: scheduler-122
labels: [web, django, fullcalendar, visualization]
---

# Schedule visualization with FullCalendar

Build an interactive schedule visualization using FullCalendar to display solver results as a calendar view.

## Description

Create a FullCalendar-based schedule view that displays the generated assignments from a solver run. Workers' shifts are shown as colored events on a calendar, with multiple view options (month, week, day, timeline). Users can filter by worker, shift type, or date range.

## Files to Create

- `web/core/views/schedule_views.py` - Schedule visualization views and JSON endpoints
- `web/templates/schedule/schedule_view.html` - Schedule visualization page
- `web/templates/schedule/schedule_filters.html` - Filter controls partial
- `web/static/js/schedule_calendar.js` - FullCalendar initialization for schedule display
- `tests/test_web/test_schedule_views.py` - Schedule view tests

## Files to Modify

- `web/core/urls.py` - Add schedule visualization URL patterns

## Implementation

### URL Patterns

```python
urlpatterns += [
    path("solver-runs/<int:pk>/schedule/", ScheduleView.as_view(), name="schedule-view"),
    path("solver-runs/<int:pk>/schedule/events/", ScheduleEventsView.as_view(), name="schedule-events"),
]
```

### FullCalendar Configuration

```javascript
// web/static/js/schedule_calendar.js
const calendar = new FullCalendar.Calendar(el, {
    initialView: "dayGridMonth",
    headerToolbar: {
        left: "prev,next today",
        center: "title",
        right: "dayGridMonth,timeGridWeek,timeGridDay,listMonth"
    },
    events: `/solver-runs/${runId}/schedule/events/`,
    eventClick: function(info) { /* Show assignment details */ },
});
```

### Events Endpoint

Returns assignments as FullCalendar events:
```json
[
    {
        "title": "Alice - Day Shift",
        "start": "2026-03-01T07:00:00",
        "end": "2026-03-01T19:00:00",
        "color": "#3b82f6",
        "extendedProps": {
            "worker_id": 1,
            "worker_name": "Alice",
            "shift_type": "Day",
            "shift_category": "Clinical"
        }
    }
]
```

### Color Coding

- Events colored by shift category using a consistent palette
- Each shift type category gets a distinct color
- Worker name displayed on each event

### Filtering

- Worker dropdown: filter to show only selected worker(s)
- Shift type checkboxes: toggle visibility by shift type
- Filters update via HTMX, refreshing calendar events

### View Modes

- **Month**: Overview of all assignments
- **Week**: Detailed weekly view with time slots
- **Day**: Single day with all assigned shifts
- **List**: Compact text list of assignments for a month

## Tests (write first)

```python
class TestScheduleView:
    def test_schedule_view_returns_200(self, client, completed_solver_run):
        """Schedule view page returns HTTP 200."""

    def test_schedule_view_includes_fullcalendar(self, client, completed_solver_run):
        """Schedule page includes FullCalendar JavaScript."""

    def test_schedule_view_has_filter_controls(self, client, completed_solver_run):
        """Schedule page includes worker and shift type filters."""

class TestScheduleEventsEndpoint:
    def test_events_returns_json(self, client, completed_solver_run):
        """Events endpoint returns JSON array."""

    def test_events_include_all_assignments(self, client, completed_solver_run):
        """Events include all assignments from the solver run."""

    def test_events_filtered_by_worker(self, client, completed_solver_run):
        """Events can be filtered by worker_id parameter."""

    def test_events_filtered_by_shift_type(self, client, completed_solver_run):
        """Events can be filtered by shift_type_id parameter."""

    def test_events_have_correct_time_range(self, client, completed_solver_run):
        """Event start/end times match shift type start time and duration."""

    def test_events_colored_by_category(self, client, completed_solver_run):
        """Events include color based on shift category."""
```

## Acceptance Criteria

- [ ] Tests written before implementation
- [ ] FullCalendar displays all assignments from a solver run
- [ ] Multiple view modes: month, week, day, list
- [ ] Events colored by shift category
- [ ] Filter by worker and shift type
- [ ] Event click shows assignment details
- [ ] Events endpoint returns correctly structured JSON
- [ ] All 9 tests pass
- [ ] ruff and mypy clean
- [ ] Frequent, focused commits
