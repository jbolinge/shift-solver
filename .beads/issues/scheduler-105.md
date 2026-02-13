---
id: scheduler-105
title: "Coverage Time Series chart"
type: task
status: open
priority: 1
created: 2026-02-13
updated: 2026-02-13
parent: scheduler-98
depends-on: scheduler-100
labels: [io, visualization]
---

# Coverage Time Series chart

Create a line chart showing coverage percentage over time for each shift type, with a reference line at 100%.

## Files to Create

- `src/shift_solver/io/plotly_handler/charts/coverage.py`

## Implementation

### `create_coverage_chart(schedule: Schedule) -> go.Figure`

For each period and shift type, compute:
```python
assigned = len(period.get_shifts_by_type(shift_type.id))
required = shift_type.workers_required
coverage_pct = (assigned / required * 100) if required > 0 else 100.0
```

Handle `applicable_days`: If a shift type has `applicable_days` set and the period doesn't overlap with those days, skip it (or show as N/A).

Create one `go.Scatter` trace per shift type:
- `x`: Period labels (e.g., "P1: Feb 1-7")
- `y`: Coverage percentage
- `mode`: "lines+markers"
- `name`: Shift type name
- `line_color`: From utils category colors (using shift_type.category)
- `hovertemplate`: "Period: %{x}<br>Coverage: %{y:.0f}%<br>Assigned: {n}/{required}"

Add reference line at 100%:
```python
fig.add_hline(y=100, line_dash="dash", line_color="gray",
              annotation_text="100% Target")
```

Layout:
- Y-axis: "Coverage (%)", range slightly beyond data bounds
- X-axis: "Period"
- Title: "Shift Coverage Over Time"

## Tests (write first)

```python
class TestCoverageChart:
    def test_coverage_returns_figure(self, sample_schedule):
        """create_coverage_chart returns a plotly Figure."""

    def test_coverage_has_line_per_shift_type(self, sample_schedule):
        """One Scatter trace per shift type."""

    def test_coverage_100_percent_when_fully_covered(self):
        """Coverage is 100% when assigned == required."""

    def test_coverage_below_100_when_understaffed(self):
        """Coverage < 100% when assigned < required."""

    def test_coverage_reference_line_at_100(self, sample_schedule):
        """Chart includes a horizontal reference line at y=100."""

    def test_coverage_handles_applicable_days_filtering(self):
        """Shift types with applicable_days are handled correctly
        (periods without applicable days show N/A or are skipped)."""
```

## Acceptance Criteria

- [ ] Returns valid `go.Figure` with Scatter traces
- [ ] One line per shift type
- [ ] Coverage percentages are computed correctly (assigned/required * 100)
- [ ] Reference line at 100%
- [ ] Handles applicable_days filtering
- [ ] All 6 tests pass
