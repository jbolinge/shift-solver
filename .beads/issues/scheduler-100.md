---
id: scheduler-100
title: "Chart utilities: color palette and data transforms"
type: task
status: open
priority: 1
created: 2026-02-13
updated: 2026-02-13
parent: scheduler-98
depends-on: scheduler-99
labels: [io, visualization]
---

# Chart utilities: color palette and data transforms

Build shared utilities for consistent colors, layout defaults, and data transformation across all charts.

## Files to Modify

- `src/shift_solver/io/plotly_handler/utils.py` - All utility functions

## Implementation

### Worker Color Palette
Assign consistent, distinct colors to workers across all charts. Use a curated palette of 20 visually distinct colors. Given a list of workers, return a `dict[str, str]` mapping worker_id to hex color.

```python
WORKER_COLORS = ["#1f77b4", "#ff7f0e", "#2ca02c", ...]  # 20 distinct colors

def get_worker_color_map(workers: list[Worker]) -> dict[str, str]:
    """Map worker IDs to consistent colors."""
```

### Shift Category Color Map
Fixed color mapping for known categories:
```python
CATEGORY_COLORS = {
    "day": "#4CAF50",       # Green
    "night": "#3F51B5",     # Indigo
    "weekend": "#FF9800",   # Orange
    "evening": "#9C27B0",   # Purple
}

def get_category_color(category: str) -> str:
    """Get color for a shift category, with fallback for unknown categories."""
```

### Default Layout Template
Shared Plotly layout settings for consistent look:
```python
def get_default_layout(**overrides) -> dict:
    """Base layout dict with font, margins, theme."""
```

### Flatten Assignments
Transform `Schedule` into flat records for chart consumption:
```python
def flatten_assignments(schedule: Schedule) -> list[dict]:
    """Convert schedule to list of flat assignment records.

    Each record: {worker_id, worker_name, shift_type_id, category,
                  date, period_index, is_undesirable}
    """
```

## Tests (write first)

```python
class TestChartUtils:
    def test_worker_color_palette_assigns_consistent_colors(self):
        """Same workers always get same colors."""

    def test_worker_color_palette_handles_up_to_20_workers(self):
        """20 workers get 20 distinct colors."""

    def test_shift_category_colors_map_known_categories(self):
        """Known categories return expected colors."""

    def test_shift_category_colors_fallback_for_unknown(self):
        """Unknown categories get a fallback color."""

    def test_flatten_assignments_returns_correct_records(self):
        """Records contain all expected fields with correct values."""

    def test_flatten_assignments_empty_schedule(self):
        """Empty schedule returns empty list."""

    def test_flatten_assignments_includes_all_fields(self):
        """Each record has worker_id, worker_name, shift_type_id, category, date, period_index, is_undesirable."""

    def test_default_layout_contains_font_and_margins(self):
        """Default layout includes font family, margins, template."""

    def test_default_layout_accepts_overrides(self):
        """Overrides are merged into default layout."""
```

## Acceptance Criteria

- [ ] Worker color palette: consistent mapping, supports up to 20 workers
- [ ] Category color map: fixed colors for day/night/weekend/evening, fallback for unknown
- [ ] Flatten assignments: correct record structure from Schedule
- [ ] Default layout: consistent font, margins, theme across charts
- [ ] All 9 tests pass
