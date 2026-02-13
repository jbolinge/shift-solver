---
id: scheduler-106
title: "Dashboard index page and PlotlyVisualizer.export_all()"
type: task
status: open
priority: 1
created: 2026-02-13
updated: 2026-02-13
parent: scheduler-98
depends-on: scheduler-101,scheduler-102,scheduler-103,scheduler-104,scheduler-105
labels: [io, visualization]
---

# Dashboard index page and PlotlyVisualizer.export_all()

Implement the full `export_all()` method that generates all 5 charts plus an index page linking them together.

## Files to Modify

- `src/shift_solver/io/plotly_handler/visualizer.py` - Implement export_all()

## Implementation

### PlotlyVisualizer.export_all()

```python
def export_all(self, schedule: Schedule, output_dir: Path) -> None:
    """Export all charts and index page to output directory."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate each chart
    charts = {
        "heatmap": create_heatmap(schedule),
        "gantt": create_gantt(schedule),
        "fairness": create_fairness_chart(schedule),
        "sunburst": create_sunburst(schedule),
        "coverage": create_coverage_chart(schedule),
    }

    # Write each chart to its own HTML file
    for name, fig in charts.items():
        fig.write_html(output_dir / f"{name}.html")

    # Generate index page
    self._write_index_page(schedule, output_dir, list(charts.keys()))
```

### Index Page (_write_index_page)

Generate a simple, clean HTML page with:

**Header**: Schedule title and metadata
- Schedule ID, date range, period type
- Worker count, shift type count, total assignments

**Chart Links**: Card-style links to each chart file with description
- Heatmap: "Worker-Period assignment density"
- Gantt: "Timeline view of shift assignments"
- Fairness: "Assignment distribution analysis"
- Sunburst: "Hierarchical category breakdown"
- Coverage: "Shift coverage over time"

**Styling**: Inline CSS, minimal and clean (no external dependencies)

```python
def _write_index_page(self, schedule: Schedule, output_dir: Path, chart_names: list[str]) -> None:
    total_assignments = sum(
        len(shifts)
        for period in schedule.periods
        for shifts in period.assignments.values()
    )

    html = f"""<!DOCTYPE html>
    <html><head><title>Schedule Dashboard - {schedule.schedule_id}</title>
    <style>/* inline styles */</style></head>
    <body>
    <h1>Schedule Dashboard</h1>
    <div class="summary">
        <p>Schedule: {schedule.schedule_id}</p>
        <p>Period: {schedule.start_date} to {schedule.end_date} ({schedule.num_periods} {schedule.period_type}s)</p>
        <p>Workers: {len(schedule.workers)} | Shift Types: {len(schedule.shift_types)} | Assignments: {total_assignments}</p>
    </div>
    <div class="charts">
        {chart_links}
    </div>
    </body></html>"""

    (output_dir / "index.html").write_text(html)
```

## Tests (write first)

```python
class TestExportAll:
    def test_export_all_creates_all_chart_files(self, tmp_path, sample_schedule):
        """All 5 chart HTML files are created."""
        visualizer = PlotlyVisualizer()
        visualizer.export_all(sample_schedule, tmp_path / "charts")
        for name in ["heatmap", "gantt", "fairness", "sunburst", "coverage"]:
            assert (tmp_path / "charts" / f"{name}.html").exists()

    def test_export_all_creates_index_html(self, tmp_path, sample_schedule):
        """index.html is created in output directory."""

    def test_index_html_contains_schedule_summary(self, tmp_path, sample_schedule):
        """Index page includes schedule ID, date range, counts."""

    def test_index_html_links_to_all_charts(self, tmp_path, sample_schedule):
        """Index page contains links to all 5 chart files."""

    def test_export_all_with_minimal_schedule(self, tmp_path):
        """Works with minimal schedule (1 worker, 1 shift, 1 period)."""

    def test_export_all_creates_nested_output_dir(self, tmp_path, sample_schedule):
        """Creates nested parent directories for output."""
```

## Acceptance Criteria

- [ ] export_all() generates 5 chart HTML files + index.html
- [ ] Each chart file is self-contained (Plotly JS embedded)
- [ ] Index page shows schedule metadata (ID, dates, counts)
- [ ] Index page links to all 5 charts
- [ ] Works with minimal and realistic schedules
- [ ] All 6 tests pass
