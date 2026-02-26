---
id: scheduler-124
title: "Plotly chart embedding and export"
type: feature
status: closed
closed: 2026-02-26
priority: 2
created: 2026-02-21
updated: 2026-02-21
parent: scheduler-109
depends-on: scheduler-123
labels: [web, django, plotly, visualization]
---

# Plotly chart embedding and export

Embed the existing Plotly interactive charts (heatmap, gantt, fairness, sunburst, coverage) in the web UI and provide download/export functionality.

## Description

Integrate the existing `PlotlyVisualizer` from `src/shift_solver/io/plotly_handler/` into the web UI. Serve Plotly charts inline on a dedicated analytics page and allow users to download charts as standalone HTML files or as a ZIP bundle.

## Files to Create

- `web/core/views/plotly_views.py` - Plotly chart views
- `web/templates/plotly/chart_page.html` - Analytics page with embedded charts
- `web/templates/plotly/chart_embed.html` - Single chart embed partial
- `web/templates/plotly/chart_tabs.html` - Tab navigation for chart types
- `tests/test_web/test_plotly_views.py` - Plotly view tests

## Files to Modify

- `web/core/urls.py` - Add plotly chart URL patterns

## Implementation

### URL Patterns

```python
urlpatterns += [
    path("solver-runs/<int:pk>/charts/", PlotlyChartPageView.as_view(), name="chart-page"),
    path("solver-runs/<int:pk>/charts/<str:chart_type>/", PlotlyChartView.as_view(), name="chart-view"),
    path("solver-runs/<int:pk>/charts/download/", PlotlyChartDownloadView.as_view(), name="chart-download"),
    path("solver-runs/<int:pk>/charts/download/<str:chart_type>/", PlotlyChartDownloadSingleView.as_view(), name="chart-download-single"),
]
```

### Chart Page Layout

Tabbed interface with 5 chart types:
1. Heatmap (worker-period)
2. Gantt (timeline)
3. Fairness (box plots)
4. Sunburst (drill-down)
5. Coverage (time series)

### Chart Rendering Strategy

Two approaches (choose during implementation):

**Option A: Inline HTML**
Generate Plotly figure HTML via `fig.to_html(include_plotlyjs="cdn", full_html=False)` and embed directly in Django template.

**Option B: Iframe**
Generate and cache chart HTML files, serve via Django view, embed in iframe.

Option A preferred for simplicity unless performance is an issue.

### Download/Export

- Single chart download: Returns standalone HTML file for one chart
- Bundle download: Generates ZIP containing all charts + index.html (using existing `PlotlyVisualizer.export_all()`)

### Integration with Existing Code

```python
from shift_solver.io import PlotlyVisualizer
from shift_solver.io.plotly_handler.charts import (
    create_heatmap, create_gantt, create_fairness,
    create_sunburst, create_coverage
)
```

Convert solver run results back to domain Schedule via conversion layer, then pass to existing chart functions.

## Tests (write first)

```python
class TestPlotlyChartPage:
    def test_chart_page_returns_200(self, client, completed_solver_run):
        """Chart analytics page returns HTTP 200."""

    def test_chart_page_has_tabs(self, client, completed_solver_run):
        """Chart page includes tab navigation for all 5 chart types."""

    def test_chart_page_renders_default_chart(self, client, completed_solver_run):
        """Chart page renders heatmap chart by default."""

class TestPlotlyChartView:
    def test_heatmap_chart_returns_html(self, client, completed_solver_run):
        """Heatmap chart endpoint returns Plotly HTML content."""

    def test_invalid_chart_type_returns_404(self, client, completed_solver_run):
        """Unknown chart type returns HTTP 404."""

class TestPlotlyChartDownload:
    def test_download_single_chart(self, client, completed_solver_run):
        """Download single chart returns HTML file attachment."""

    def test_download_bundle_returns_zip(self, client, completed_solver_run):
        """Download all returns ZIP file with all charts."""

    def test_download_bundle_contains_all_charts(self, client, completed_solver_run):
        """ZIP bundle contains all 5 chart HTML files plus index."""
```

## Acceptance Criteria

- [ ] Tests written before implementation
- [ ] Analytics page displays all 5 Plotly chart types via tabs
- [ ] Charts render interactively (zoom, hover, pan)
- [ ] Single chart download as standalone HTML
- [ ] Bundle download as ZIP with all charts
- [ ] Reuses existing PlotlyVisualizer and chart functions
- [ ] All 8 tests pass
- [ ] ruff and mypy clean
- [ ] Frequent, focused commits
