---
id: scheduler-101
title: "Worker-Period Heatmap chart"
type: task
status: closed
priority: 1
created: 2026-02-13
updated: 2026-02-13
parent: scheduler-98
depends-on: scheduler-100
labels: [io, visualization]
---

# Worker-Period Heatmap chart

Create an interactive heatmap showing shift assignment density across workers and periods.

## Files to Create

- `src/shift_solver/io/plotly_handler/charts/heatmap.py`

## Implementation

### `create_heatmap(schedule: Schedule) -> go.Figure`

Build a 2D matrix:
- **Rows** (Y-axis): Workers (display as "Name (ID)")
- **Columns** (X-axis): Periods (display as "P{n}: {start_date}")
- **Cell value**: Number of shifts assigned to that worker in that period
- **Cell annotation**: Shift type abbreviations (e.g., "D, N" for day + night)
- **Color scale**: White (0 shifts) → Blue (max shifts), sequential

Hover template should show:
- Worker name and ID
- Period date range
- Shift type breakdown (e.g., "day: 1, night: 1")
- Total shifts in cell

Use `go.Heatmap` with:
- `z`: 2D array of shift counts
- `text`: 2D array of abbreviation strings for annotations
- `texttemplate`: "%{text}"
- `hovertemplate`: Custom template with worker/period/shift details
- `colorscale`: "Blues"

Apply default layout from utils.

## Tests (write first)

```python
class TestHeatmapChart:
    def test_heatmap_returns_figure(self, sample_schedule):
        """create_heatmap returns a plotly Figure."""

    def test_heatmap_has_correct_dimensions(self, sample_schedule):
        """Heatmap z-data has rows=num_workers, cols=num_periods."""

    def test_heatmap_annotations_match_assignments(self, sample_schedule):
        """Cell text annotations reflect actual shift types assigned."""

    def test_heatmap_empty_cells_show_zero(self, sample_schedule):
        """Periods with no assignments for a worker show 0."""

    def test_heatmap_single_worker_single_period(self):
        """Minimal case: 1 worker, 1 period, 1 shift."""

    def test_heatmap_hover_contains_worker_name(self, sample_schedule):
        """Hover data includes worker name."""
```

Use conftest fixtures `sample_workers()`, `sample_shift_types()`, `sample_period_dates()` to build a `Schedule` fixture for these tests.

## Acceptance Criteria

- [ ] Returns valid `go.Figure` with `Heatmap` trace
- [ ] Correct dimensions matching workers × periods
- [ ] Cell annotations show shift type abbreviations
- [ ] Empty cells show 0
- [ ] Hover includes worker name and shift breakdown
- [ ] All 6 tests pass
