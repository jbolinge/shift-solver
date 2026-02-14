"""Tests for PlotlyVisualizer.export_all() and index page."""

from datetime import date, time
from pathlib import Path

from shift_solver.io.plotly_handler import PlotlyVisualizer
from shift_solver.models import ShiftType, Worker
from shift_solver.models.schedule import PeriodAssignment, Schedule
from shift_solver.models.shift import ShiftInstance

CHART_NAMES = ["heatmap", "gantt", "fairness", "sunburst", "coverage"]


class TestExportAll:
    def test_export_all_creates_all_chart_files(
        self, tmp_path: Path, sample_schedule: Schedule
    ) -> None:
        """All 5 chart HTML files are created."""
        visualizer = PlotlyVisualizer()
        visualizer.export_all(sample_schedule, tmp_path / "charts")
        for name in CHART_NAMES:
            assert (tmp_path / "charts" / f"{name}.html").exists()

    def test_export_all_creates_index_html(
        self, tmp_path: Path, sample_schedule: Schedule
    ) -> None:
        """index.html is created in output directory."""
        visualizer = PlotlyVisualizer()
        visualizer.export_all(sample_schedule, tmp_path / "charts")
        assert (tmp_path / "charts" / "index.html").exists()

    def test_index_html_contains_schedule_summary(
        self, tmp_path: Path, sample_schedule: Schedule
    ) -> None:
        """Index page includes schedule ID, date range, counts."""
        visualizer = PlotlyVisualizer()
        visualizer.export_all(sample_schedule, tmp_path / "charts")
        content = (tmp_path / "charts" / "index.html").read_text()
        assert "test-schedule" in content
        assert "2026-02-02" in content
        assert "2026-02-15" in content

    def test_index_html_links_to_all_charts(
        self, tmp_path: Path, sample_schedule: Schedule
    ) -> None:
        """Index page contains links to all 5 chart files."""
        visualizer = PlotlyVisualizer()
        visualizer.export_all(sample_schedule, tmp_path / "charts")
        content = (tmp_path / "charts" / "index.html").read_text()
        for name in CHART_NAMES:
            assert f"{name}.html" in content

    def test_export_all_with_minimal_schedule(self, tmp_path: Path) -> None:
        """Works with minimal schedule (1 worker, 1 shift, 1 period)."""
        workers = [Worker(id="W1", name="Alice")]
        shift_types = [
            ShiftType(
                id="day",
                name="Day",
                category="day",
                start_time=time(7, 0),
                end_time=time(15, 0),
                duration_hours=8.0,
            )
        ]
        period = PeriodAssignment(
            period_index=0,
            period_start=date(2026, 2, 2),
            period_end=date(2026, 2, 8),
            assignments={
                "W1": [
                    ShiftInstance(
                        shift_type_id="day",
                        period_index=0,
                        date=date(2026, 2, 2),
                        worker_id="W1",
                    )
                ]
            },
        )
        schedule = Schedule(
            schedule_id="minimal",
            start_date=date(2026, 2, 2),
            end_date=date(2026, 2, 8),
            period_type="week",
            periods=[period],
            workers=workers,
            shift_types=shift_types,
        )
        visualizer = PlotlyVisualizer()
        visualizer.export_all(schedule, tmp_path / "charts")
        for name in CHART_NAMES:
            assert (tmp_path / "charts" / f"{name}.html").exists()
        assert (tmp_path / "charts" / "index.html").exists()

    def test_export_all_creates_nested_output_dir(
        self, tmp_path: Path, sample_schedule: Schedule
    ) -> None:
        """Creates nested parent directories for output."""
        visualizer = PlotlyVisualizer()
        output = tmp_path / "deep" / "nested" / "charts"
        visualizer.export_all(sample_schedule, output)
        assert output.exists()
        assert (output / "index.html").exists()
