---
id: scheduler-102
title: "Gantt Timeline chart"
type: task
status: closed
priority: 1
created: 2026-02-13
updated: 2026-02-13
parent: scheduler-98
depends-on: scheduler-100
labels: [io, visualization]
---

# Gantt Timeline chart

Create a horizontal timeline showing each worker's shift assignments over the schedule horizon, colored by shift category.

## Files to Create

- `src/shift_solver/io/plotly_handler/charts/gantt.py`

## Implementation

### `create_gantt(schedule: Schedule) -> go.Figure`

Transform schedule assignments into timeline records:
- Each assignment becomes a bar: worker_name (Y), start_date, end_date (start + duration_hours), shift_type_id (label)
- Color bars by shift category using `get_category_color()` from utils
- For shift types where `end_time < start_time` (overnight), extend bar to next day

Use `px.timeline()` with:
- `x_start`: shift date (as datetime with start_time)
- `x_end`: shift date + duration_hours
- `y`: worker name
- `color`: shift category
- `color_discrete_map`: from utils category colors

Add `updatemenus` buttons to filter by shift category (show/hide traces).

Apply default layout from utils. Set `xaxis_type='date'`.

### Data Transformation

```python
records = []
for period in schedule.periods:
    for worker_id, shifts in period.assignments.items():
        worker = schedule.get_worker_by_id(worker_id)
        for shift in shifts:
            shift_type = schedule.get_shift_type_by_id(shift.shift_type_id)
            records.append({
                "Worker": worker.name,
                "Start": datetime.combine(shift.date, shift_type.start_time),
                "End": datetime.combine(shift.date, shift_type.start_time) + timedelta(hours=shift_type.duration_hours),
                "Shift": shift_type.name,
                "Category": shift_type.category,
            })
```

## Tests (write first)

```python
class TestGanttChart:
    def test_gantt_returns_figure(self, sample_schedule):
        """create_gantt returns a plotly Figure."""

    def test_gantt_has_bar_per_assignment(self, sample_schedule):
        """Number of bars equals total assignments in schedule."""

    def test_gantt_colors_by_category(self, sample_schedule):
        """Bars are colored according to shift category."""

    def test_gantt_all_workers_present_on_yaxis(self, sample_schedule):
        """All workers with assignments appear on Y-axis."""

    def test_gantt_date_axis_spans_schedule_range(self, sample_schedule):
        """Timeline X-axis covers the full schedule date range."""

    def test_gantt_single_assignment(self):
        """Minimal case: one worker, one shift, one period."""
```

## Acceptance Criteria

- [ ] Returns valid `go.Figure` with timeline bars
- [ ] One bar per shift assignment
- [ ] Colors correspond to shift categories
- [ ] All assigned workers appear on Y-axis
- [ ] Date axis spans full schedule range
- [ ] All 6 tests pass
