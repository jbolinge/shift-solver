---
id: scheduler-104
title: "Sunburst Drill-Down chart"
type: task
status: closed
priority: 1
created: 2026-02-13
updated: 2026-02-13
parent: scheduler-98
depends-on: scheduler-100
labels: [io, visualization]
---

# Sunburst Drill-Down chart

Create a hierarchical sunburst chart allowing drill-down from schedule overview through categories and shift types to individual worker assignments.

## Files to Create

- `src/shift_solver/io/plotly_handler/charts/sunburst.py`

## Implementation

### `create_sunburst(schedule: Schedule) -> go.Figure`

Build the hierarchy using parallel arrays for `go.Sunburst`:

**Level 0 (root)**: "Schedule" - total assignments
**Level 1 (categories)**: Each unique category - sum of assignments in that category
**Level 2 (shift types)**: Each shift type under its category - count of assignments
**Level 3 (workers)**: Each worker under each shift type - individual count

```python
ids = ["Schedule"]
labels = ["Schedule"]
parents = [""]
values = [total_assignments]

for category in categories:
    cat_id = f"cat-{category}"
    ids.append(cat_id)
    labels.append(category.title())
    parents.append("Schedule")
    values.append(category_total)

    for shift_type in shift_types_in_category:
        st_id = f"st-{shift_type.id}"
        ids.append(st_id)
        labels.append(shift_type.name)
        parents.append(cat_id)
        values.append(shift_type_total)

        for worker in workers_with_this_shift:
            w_id = f"w-{worker.id}-{shift_type.id}"
            ids.append(w_id)
            labels.append(worker.name)
            parents.append(st_id)
            values.append(worker_shift_count)
```

Use `go.Sunburst` with:
- `ids`, `labels`, `parents`, `values`
- `branchvalues`: "total"
- `marker_colors`: Category colors at level 1, inherited below

Layout:
- Title: "Assignment Hierarchy: Category > Shift Type > Worker"
- Margin: minimal for maximum chart area

## Tests (write first)

```python
class TestSunburstChart:
    def test_sunburst_returns_figure(self, sample_schedule):
        """create_sunburst returns a plotly Figure."""

    def test_sunburst_root_is_schedule(self, sample_schedule):
        """Root node is labeled 'Schedule'."""

    def test_sunburst_categories_at_level_two(self, sample_schedule):
        """Category nodes have 'Schedule' as parent."""

    def test_sunburst_shift_types_under_correct_category(self, sample_schedule):
        """Shift type nodes parent to their category."""

    def test_sunburst_worker_values_sum_to_shift_type_total(self, sample_schedule):
        """Worker counts under a shift type sum to that shift type's total."""

    def test_sunburst_handles_single_shift_type(self):
        """Works with only one shift type."""
```

## Acceptance Criteria

- [ ] Returns valid `go.Figure` with Sunburst trace
- [ ] Correct hierarchy: Schedule → Categories → Shift Types → Workers
- [ ] Values sum correctly at each level
- [ ] Click to drill down works (Plotly built-in)
- [ ] Handles single shift type edge case
- [ ] All 6 tests pass
