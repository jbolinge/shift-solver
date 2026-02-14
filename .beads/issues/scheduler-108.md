---
id: scheduler-108
title: "E2E integration test for Plotly visualization"
type: task
status: closed
priority: 2
created: 2026-02-13
updated: 2026-02-13
parent: scheduler-98
depends-on: scheduler-107
labels: [io, visualization, e2e, integration]
---

# E2E integration test for Plotly visualization

Full pipeline tests verifying chart generation from schedule data, including data accuracy checks.

## Files to Create

- `tests/test_e2e/test_plotly_visualization.py`

## Implementation

### Test 1: Minimal schedule export
Build a minimal schedule (2 workers, 1 shift type, 2 periods), export to plotly, verify all 6 HTML files exist and contain Plotly div elements.

### Test 2: Realistic schedule export
Use the multi-site medical scheduling pattern (8 workers, 7 shift types, 26 periods) or build a similar fixture. Export and verify all files generated.

### Test 3: Data accuracy
Export a known schedule and verify:
- Heatmap cell values match actual assignment counts
- Coverage percentages are mathematically correct (assigned/required * 100)
- Sunburst worker values sum correctly to shift type totals
- All workers from the schedule appear in the charts

### Verification approach
Read generated HTML files and check for:
- Presence of `<div id="...">` Plotly container elements
- Embedded JSON data matching expected values (parse from HTML)
- Index page links pointing to correct chart filenames

## Tests

```python
@pytest.mark.e2e
class TestPlotlyVisualizationE2E:
    def test_e2e_plotly_export_minimal_schedule(self, tmp_path):
        """Minimal schedule (2 workers, 1 shift, 2 periods) generates all chart files."""
        # Build minimal schedule
        # Export with PlotlyVisualizer
        # Assert all 6 HTML files exist
        # Assert each file contains plotly div

    def test_e2e_plotly_export_realistic_schedule(self, tmp_path):
        """Realistic schedule (8+ workers, 5+ shifts, 10+ periods) generates all charts."""
        # Build realistic schedule matching multi-site pattern
        # Export
        # Verify all files present and non-trivial size

    def test_e2e_chart_data_matches_schedule_statistics(self, tmp_path):
        """Chart data is mathematically consistent with schedule data."""
        # Build schedule with known exact assignment counts
        # Export
        # Parse generated HTML for embedded data
        # Verify heatmap values, coverage percentages, sunburst sums
```

## Acceptance Criteria

- [ ] Minimal schedule export produces valid chart files
- [ ] Realistic schedule export produces valid chart files
- [ ] Chart data is verified against source schedule data
- [ ] Tests marked with `@pytest.mark.e2e`
- [ ] All 3 tests pass
