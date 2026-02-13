---
id: scheduler-99
title: "Plotly handler package skeleton"
type: task
status: open
priority: 1
created: 2026-02-13
updated: 2026-02-13
parent: scheduler-98
labels: [io, visualization]
---

# Plotly handler package skeleton

Create the `plotly_handler/` subpackage structure, stub classes, dependency registration, and initial tests.

## Files to Create

- `src/shift_solver/io/plotly_handler/__init__.py` - Export PlotlyVisualizer, PlotlyHandlerError
- `src/shift_solver/io/plotly_handler/exceptions.py` - PlotlyHandlerError(Exception)
- `src/shift_solver/io/plotly_handler/visualizer.py` - PlotlyVisualizer class stub
- `src/shift_solver/io/plotly_handler/utils.py` - Empty placeholder
- `src/shift_solver/io/plotly_handler/charts/__init__.py` - Empty placeholder
- `tests/test_io/test_plotly_handler.py` - Initial test file

## Files to Modify

- `src/shift_solver/io/__init__.py` - Add PlotlyVisualizer, PlotlyHandlerError to imports and __all__
- `pyproject.toml` - Add `plotly>=5.0.0` to dependencies

## Implementation

### PlotlyHandlerError
```python
class PlotlyHandlerError(Exception):
    """Error in Plotly visualization handler."""
```

### PlotlyVisualizer (stub)
```python
class PlotlyVisualizer:
    """Generates interactive Plotly visualizations for schedule data."""

    def export_all(self, schedule: Schedule, output_dir: Path) -> None:
        """Export all chart types to a directory."""
        output_dir.mkdir(parents=True, exist_ok=True)
```

## Tests (write first)

```python
class TestPlotlyHandlerSkeleton:
    def test_plotly_handler_error_is_exception(self):
        """PlotlyHandlerError inherits from Exception."""

    def test_plotly_visualizer_importable_from_io(self):
        """PlotlyVisualizer can be imported from shift_solver.io."""

    def test_plotly_visualizer_creates_output_directory(self, tmp_path):
        """export_all creates the output directory."""

    def test_plotly_visualizer_creates_parent_directories(self, tmp_path):
        """export_all creates nested parent directories."""
```

## Acceptance Criteria

- [ ] Package structure matches plan
- [ ] PlotlyHandlerError importable from shift_solver.io
- [ ] PlotlyVisualizer importable from shift_solver.io
- [ ] export_all creates output directory (including nested parents)
- [ ] plotly added to pyproject.toml dependencies
- [ ] All 4 tests pass
