"""Plotly visualizer for schedule data."""

from pathlib import Path

from shift_solver.io.plotly_handler.charts.coverage import create_coverage_chart
from shift_solver.io.plotly_handler.charts.fairness import create_fairness_chart
from shift_solver.io.plotly_handler.charts.gantt import create_gantt
from shift_solver.io.plotly_handler.charts.heatmap import create_heatmap
from shift_solver.io.plotly_handler.charts.sunburst import create_sunburst
from shift_solver.models.schedule import Schedule

CHART_DESCRIPTIONS: dict[str, str] = {
    "heatmap": "Worker-Period assignment density",
    "gantt": "Timeline view of shift assignments",
    "fairness": "Assignment distribution analysis",
    "sunburst": "Hierarchical category breakdown",
    "coverage": "Shift coverage over time",
}


class PlotlyVisualizer:
    """Generates interactive Plotly visualizations for schedule data."""

    def export_all(self, schedule: Schedule, output_dir: Path) -> None:
        """Export all chart types and index page to a directory."""
        output_dir.mkdir(parents=True, exist_ok=True)

        charts = {
            "heatmap": create_heatmap(schedule),
            "gantt": create_gantt(schedule),
            "fairness": create_fairness_chart(schedule),
            "sunburst": create_sunburst(schedule),
            "coverage": create_coverage_chart(schedule),
        }

        for name, fig in charts.items():
            fig.write_html(output_dir / f"{name}.html")

        self._write_index_page(schedule, output_dir, list(charts.keys()))

    def _write_index_page(
        self,
        schedule: Schedule,
        output_dir: Path,
        chart_names: list[str],
    ) -> None:
        """Generate an index HTML page with summary stats and chart links."""
        total_assignments = sum(
            len(shifts)
            for period in schedule.periods
            for shifts in period.assignments.values()
        )

        chart_links = "\n".join(
            f'        <div class="card">'
            f'<a href="{name}.html">{name.title()}</a>'
            f"<p>{CHART_DESCRIPTIONS.get(name, '')}</p></div>"
            for name in chart_names
        )

        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Schedule Dashboard - {schedule.schedule_id}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }}
        h1 {{ color: #333; }}
        .summary {{ background: #fff; padding: 20px; border-radius: 8px;
                   margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .summary p {{ margin: 5px 0; color: #555; }}
        .charts {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
                  gap: 16px; }}
        .card {{ background: #fff; padding: 20px; border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .card a {{ font-size: 18px; font-weight: bold; color: #1976D2;
                  text-decoration: none; }}
        .card a:hover {{ text-decoration: underline; }}
        .card p {{ color: #777; margin-top: 8px; }}
    </style>
</head>
<body>
    <h1>Schedule Dashboard</h1>
    <div class="summary">
        <p><strong>Schedule:</strong> {schedule.schedule_id}</p>
        <p><strong>Period:</strong> {schedule.start_date} to {schedule.end_date} ({schedule.num_periods} {schedule.period_type}s)</p>
        <p><strong>Workers:</strong> {len(schedule.workers)} | <strong>Shift Types:</strong> {len(schedule.shift_types)} | <strong>Assignments:</strong> {total_assignments}</p>
    </div>
    <h2>Charts</h2>
    <div class="charts">
{chart_links}
    </div>
</body>
</html>"""

        (output_dir / "index.html").write_text(html)
