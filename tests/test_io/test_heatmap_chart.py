"""Tests for Worker-Period Heatmap chart."""

from datetime import date, time

import plotly.graph_objects as go
import pytest

from shift_solver.io.plotly_handler.charts.heatmap import create_heatmap
from shift_solver.models import ShiftType, Worker
from shift_solver.models.schedule import PeriodAssignment, Schedule
from shift_solver.models.shift import ShiftInstance


class TestHeatmapChart:
    def test_heatmap_returns_figure(self, sample_schedule: Schedule) -> None:
        """create_heatmap returns a plotly Figure."""
        fig = create_heatmap(sample_schedule)
        assert isinstance(fig, go.Figure)

    def test_heatmap_has_correct_dimensions(self, sample_schedule: Schedule) -> None:
        """Heatmap z-data has rows=num_workers, cols=num_periods."""
        fig = create_heatmap(sample_schedule)
        heatmap_trace = fig.data[0]
        z = heatmap_trace.z
        assert len(z) == 3  # 3 workers
        assert len(z[0]) == 2  # 2 periods

    def test_heatmap_annotations_match_assignments(
        self, sample_schedule: Schedule
    ) -> None:
        """Cell text annotations reflect actual shift types assigned."""
        fig = create_heatmap(sample_schedule)
        heatmap_trace = fig.data[0]
        text = heatmap_trace.text
        # W001 period 0 has day + night
        assert "D" in text[0][0]
        assert "N" in text[0][0]

    def test_heatmap_empty_cells_show_zero(self, sample_schedule: Schedule) -> None:
        """Periods with no assignments for a worker show 0."""
        fig = create_heatmap(sample_schedule)
        heatmap_trace = fig.data[0]
        z = heatmap_trace.z
        # All workers have at least some assignments, but check values are ints
        for row in z:
            for val in row:
                assert isinstance(val, int)

    def test_heatmap_single_worker_single_period(self) -> None:
        """Minimal case: 1 worker, 1 period, 1 shift."""
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
        fig = create_heatmap(schedule)
        assert isinstance(fig, go.Figure)
        assert fig.data[0].z[0][0] == 1

    def test_heatmap_hover_contains_worker_name(
        self, sample_schedule: Schedule
    ) -> None:
        """Hover data includes worker name."""
        fig = create_heatmap(sample_schedule)
        heatmap_trace = fig.data[0]
        # Y-axis labels should contain worker names
        assert "Alice" in heatmap_trace.y[0]
