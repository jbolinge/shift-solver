---
id: scheduler-98
title: "Plotly Interactive Visualization"
type: epic
status: open
priority: 1
created: 2026-02-13
updated: 2026-02-13
labels: [io, visualization]
---

# Plotly Interactive Visualization

Generate a suite of interactive HTML chart files from schedule JSON using Plotly. Provides analyst-grade visualizations for spotting fairness imbalances, coverage gaps, and workload patterns at a glance.

## Summary

Mirror the existing `excel_handler/` subpackage pattern. Create `src/shift_solver/io/plotly_handler/` with a `PlotlyVisualizer` class that accepts a `Schedule` object and generates 5 interactive charts plus an index page. Extend the CLI `export` command with a `plotly` format option.

### Charts

1. **Worker-Period Heatmap** - Grid showing shift counts per worker per period with annotations
2. **Gantt Timeline** - Horizontal timeline of assignments colored by shift category
3. **Fairness Box Plots** - Distribution of shift assignments across workers by category
4. **Sunburst Drill-Down** - Hierarchical view: categories → shift types → workers
5. **Coverage Time Series** - Line chart of coverage percentage over periods per shift type

### Output

```bash
shift-solver export --schedule output.json -o charts/ --format plotly
```

Generates a directory:
```
charts/
├── index.html       # Summary stats + links to all charts
├── heatmap.html     # Worker-Period heatmap
├── gantt.html       # Timeline view
├── fairness.html    # Box plots
├── sunburst.html    # Drill-down
└── coverage.html    # Time series
```

## Child Issues

### Foundation
- **scheduler-99** - Plotly handler package skeleton
- **scheduler-100** - Chart utilities: color palette and data transforms (depends on scheduler-99)

### Charts (all depend on scheduler-100)
- **scheduler-101** - Worker-Period Heatmap chart
- **scheduler-102** - Gantt Timeline chart
- **scheduler-103** - Fairness Box Plots chart
- **scheduler-104** - Sunburst Drill-Down chart
- **scheduler-105** - Coverage Time Series chart

### Integration
- **scheduler-106** - Dashboard index page and PlotlyVisualizer.export_all() (depends on scheduler-101 through scheduler-105)
- **scheduler-107** - CLI integration: extend export command (depends on scheduler-106)
- **scheduler-108** - E2E integration test (depends on scheduler-107)

## Dependency Chain

```
scheduler-99  (skeleton)
    └── scheduler-100  (utils)
            ├── scheduler-101  (heatmap)
            ├── scheduler-102  (gantt)
            ├── scheduler-103  (fairness)
            ├── scheduler-104  (sunburst)
            └── scheduler-105  (coverage)
                    └── scheduler-106  (dashboard + export_all)
                            └── scheduler-107  (CLI)
                                    └── scheduler-108  (E2E)
```

## Branch

`feature/plotly-visualization` off `main`

## Acceptance Criteria

- [ ] 5 interactive Plotly charts generated from any schedule JSON
- [ ] Index page with summary stats and links to all charts
- [ ] CLI integration via `--format plotly` on export command
- [ ] All charts render correctly in browser with zoom, hover, and pan
- [ ] TDD: tests written before implementation for every component
- [ ] All tests pass (existing + new)
- [ ] ruff and mypy clean
