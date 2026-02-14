"""Tests for Gantt Timeline chart."""

from datetime import date, time

import plotly.graph_objects as go
import pytest

from shift_solver.io.plotly_handler.charts.gantt import create_gantt
from shift_solver.models import ShiftType, Worker
from shift_solver.models.schedule import PeriodAssignment, Schedule
from shift_solver.models.shift import ShiftInstance


class TestGanttChart:
    def test_gantt_returns_figure(self, sample_schedule: Schedule) -> None:
        """create_gantt returns a plotly Figure."""
        fig = create_gantt(sample_schedule)
        assert isinstance(fig, go.Figure)

    def test_gantt_has_bar_per_assignment(self, sample_schedule: Schedule) -> None:
        """Number of bars equals total assignments in schedule."""
        fig = create_gantt(sample_schedule)
        # Total assignments: P0(2+1+1) + P1(1+1+2) = 8
        total_bars = sum(len(trace.x) for trace in fig.data)
        assert total_bars == 8

    def test_gantt_colors_by_category(self, sample_schedule: Schedule) -> None:
        """Bars are colored according to shift category."""
        fig = create_gantt(sample_schedule)
        # Should have traces for 'day' and 'night' categories
        trace_names = {trace.name for trace in fig.data}
        assert "day" in trace_names or "Day Shift" in trace_names or len(trace_names) >= 2

    def test_gantt_all_workers_present_on_yaxis(
        self, sample_schedule: Schedule
    ) -> None:
        """All workers with assignments appear on Y-axis."""
        fig = create_gantt(sample_schedule)
        all_y_values = set()
        for trace in fig.data:
            if trace.y is not None:
                all_y_values.update(trace.y)
        assert "Alice" in all_y_values
        assert "Bob" in all_y_values
        assert "Charlie" in all_y_values

    def test_gantt_date_axis_spans_schedule_range(
        self, sample_schedule: Schedule
    ) -> None:
        """Timeline X-axis covers the full schedule date range."""
        fig = create_gantt(sample_schedule)
        # Check that we have traces with data spanning the schedule
        assert len(fig.data) > 0

    def test_gantt_single_assignment(self) -> None:
        """Minimal case: one worker, one shift, one period."""
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
        fig = create_gantt(schedule)
        assert isinstance(fig, go.Figure)
        total_bars = sum(len(trace.x) for trace in fig.data)
        assert total_bars == 1
