---
id: scheduler-103
title: "Fairness Box Plots chart"
type: task
status: closed
priority: 1
created: 2026-02-13
updated: 2026-02-13
parent: scheduler-98
depends-on: scheduler-100
labels: [io, visualization]
---

# Fairness Box Plots chart

Create box plots showing the distribution of shift assignments across workers, grouped by shift category. This is the key chart for fairness analysis.

## Files to Create

- `src/shift_solver/io/plotly_handler/charts/fairness.py`

## Implementation

### `create_fairness_chart(schedule: Schedule) -> go.Figure`

For each shift category, compute per-worker assignment counts:
```python
# category -> [count_worker1, count_worker2, ...]
category_counts = defaultdict(list)
for worker in schedule.workers:
    for category in categories:
        count = sum(1 for record in flat_records
                    if record["worker_id"] == worker.id
                    and record["category"] == category)
        category_counts[category].append(count)
```

Create one `go.Box` trace per category:
- `y`: list of per-worker counts
- `name`: category name
- `boxpoints`: "all" (show individual points)
- `pointpos`: 0 (center points on box)
- `jitter`: 0.3
- `marker_color`: from utils category colors
- `hovertext`: worker names for each point

Also add a horizontal reference line at the mean for each category using `go.Scatter` with `mode='lines'` and `line_dash='dash'`.

Layout:
- Y-axis: "Number of Assignments"
- X-axis: "Shift Category"
- Title: "Fairness Analysis: Assignment Distribution by Category"

## Tests (write first)

```python
class TestFairnessChart:
    def test_fairness_returns_figure(self, sample_schedule):
        """create_fairness_chart returns a plotly Figure."""

    def test_fairness_has_box_per_category(self, sample_schedule):
        """One Box trace per unique shift category."""

    def test_fairness_points_match_worker_count(self, sample_schedule):
        """Each box has points equal to number of workers."""

    def test_fairness_hover_shows_worker_names(self, sample_schedule):
        """Hover text on points includes worker names."""

    def test_fairness_handles_single_category(self):
        """Works with only one shift category."""

    def test_fairness_handles_zero_assignments(self):
        """Workers with 0 assignments in a category are still represented."""
```

## Acceptance Criteria

- [ ] Returns valid `go.Figure` with Box traces
- [ ] One box per shift category
- [ ] Individual worker points overlaid on boxes
- [ ] Hover shows worker names
- [ ] Handles edge cases (single category, zero assignments)
- [ ] All 6 tests pass
