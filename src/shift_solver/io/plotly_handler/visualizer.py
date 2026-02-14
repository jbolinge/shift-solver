"""Plotly visualizer for schedule data."""

from pathlib import Path

from shift_solver.models.schedule import Schedule


class PlotlyVisualizer:
    """Generates interactive Plotly visualizations for schedule data."""

    def export_all(self, schedule: Schedule, output_dir: Path) -> None:
        """Export all chart types to a directory."""
        output_dir.mkdir(parents=True, exist_ok=True)
