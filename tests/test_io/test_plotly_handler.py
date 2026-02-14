"""Tests for Plotly handler package."""

from pathlib import Path

import pytest

from shift_solver.io.plotly_handler import PlotlyHandlerError, PlotlyVisualizer


class TestPlotlyHandlerSkeleton:
    def test_plotly_handler_error_is_exception(self) -> None:
        """PlotlyHandlerError inherits from Exception."""
        assert issubclass(PlotlyHandlerError, Exception)
        err = PlotlyHandlerError("test error")
        assert str(err) == "test error"

    def test_plotly_visualizer_importable_from_io(self) -> None:
        """PlotlyVisualizer can be imported from shift_solver.io."""
        from shift_solver.io import PlotlyVisualizer as PV

        assert PV is PlotlyVisualizer

    def test_plotly_handler_error_importable_from_io(self) -> None:
        """PlotlyHandlerError can be imported from shift_solver.io."""
        from shift_solver.io import PlotlyHandlerError as PHE

        assert PHE is PlotlyHandlerError

    def test_plotly_visualizer_creates_output_directory(self, tmp_path: Path) -> None:
        """export_all creates the output directory."""
        from datetime import date

        from shift_solver.models import ShiftType, Worker
        from shift_solver.models.schedule import PeriodAssignment, Schedule

        schedule = Schedule(
            schedule_id="test",
            start_date=date(2026, 2, 2),
            end_date=date(2026, 2, 8),
            period_type="week",
            periods=[],
            workers=[],
            shift_types=[],
        )
        output_dir = tmp_path / "charts"
        visualizer = PlotlyVisualizer()
        visualizer.export_all(schedule, output_dir)
        assert output_dir.exists()
        assert output_dir.is_dir()

    def test_plotly_visualizer_creates_parent_directories(
        self, tmp_path: Path
    ) -> None:
        """export_all creates nested parent directories."""
        from datetime import date

        from shift_solver.models.schedule import Schedule

        schedule = Schedule(
            schedule_id="test",
            start_date=date(2026, 2, 2),
            end_date=date(2026, 2, 8),
            period_type="week",
            periods=[],
            workers=[],
            shift_types=[],
        )
        output_dir = tmp_path / "deep" / "nested" / "charts"
        visualizer = PlotlyVisualizer()
        visualizer.export_all(schedule, output_dir)
        assert output_dir.exists()
        assert output_dir.is_dir()
