"""Tests for Coverage Time Series chart."""

from datetime import date, time

import plotly.graph_objects as go
import pytest

from shift_solver.io.plotly_handler.charts.coverage import create_coverage_chart
from shift_solver.models import ShiftType, Worker
from shift_solver.models.schedule import PeriodAssignment, Schedule
from shift_solver.models.shift import ShiftInstance


class TestCoverageChart:
    def test_coverage_returns_figure(self, sample_schedule: Schedule) -> None:
        """create_coverage_chart returns a plotly Figure."""
        fig = create_coverage_chart(sample_schedule)
        assert isinstance(fig, go.Figure)

    def test_coverage_has_line_per_shift_type(
        self, sample_schedule: Schedule
    ) -> None:
        """One Scatter trace per shift type."""
        fig = create_coverage_chart(sample_schedule)
        scatter_traces = [t for t in fig.data if isinstance(t, go.Scatter) and t.mode and "lines" in t.mode]
        assert len(scatter_traces) == 2  # day and night

    def test_coverage_100_percent_when_fully_covered(self) -> None:
        """Coverage is 100% when assigned == required."""
        workers = [Worker(id="W1", name="Alice"), Worker(id="W2", name="Bob")]
        shift_types = [
            ShiftType(
                id="day",
                name="Day",
                category="day",
                start_time=time(7, 0),
                end_time=time(15, 0),
                duration_hours=8.0,
                workers_required=2,
            )
        ]
        period = PeriodAssignment(
            period_index=0,
            period_start=date(2026, 2, 2),
            period_end=date(2026, 2, 8),
            assignments={
                "W1": [
                    ShiftInstance(shift_type_id="day", period_index=0, date=date(2026, 2, 2), worker_id="W1"),
                ],
                "W2": [
                    ShiftInstance(shift_type_id="day", period_index=0, date=date(2026, 2, 2), worker_id="W2"),
                ],
            },
        )
        schedule = Schedule(
            schedule_id="full",
            start_date=date(2026, 2, 2),
            end_date=date(2026, 2, 8),
            period_type="week",
            periods=[period],
            workers=workers,
            shift_types=shift_types,
        )
        fig = create_coverage_chart(schedule)
        scatter_traces = [t for t in fig.data if isinstance(t, go.Scatter) and t.mode and "lines" in t.mode]
        assert len(scatter_traces) == 1
        assert scatter_traces[0].y[0] == pytest.approx(100.0)

    def test_coverage_below_100_when_understaffed(self) -> None:
        """Coverage < 100% when assigned < required."""
        workers = [Worker(id="W1", name="Alice")]
        shift_types = [
            ShiftType(
                id="day",
                name="Day",
                category="day",
                start_time=time(7, 0),
                end_time=time(15, 0),
                duration_hours=8.0,
                workers_required=2,
            )
        ]
        period = PeriodAssignment(
            period_index=0,
            period_start=date(2026, 2, 2),
            period_end=date(2026, 2, 8),
            assignments={
                "W1": [
                    ShiftInstance(shift_type_id="day", period_index=0, date=date(2026, 2, 2), worker_id="W1"),
                ],
            },
        )
        schedule = Schedule(
            schedule_id="under",
            start_date=date(2026, 2, 2),
            end_date=date(2026, 2, 8),
            period_type="week",
            periods=[period],
            workers=workers,
            shift_types=shift_types,
        )
        fig = create_coverage_chart(schedule)
        scatter_traces = [t for t in fig.data if isinstance(t, go.Scatter) and t.mode and "lines" in t.mode]
        assert scatter_traces[0].y[0] == pytest.approx(50.0)

    def test_coverage_reference_line_at_100(self, sample_schedule: Schedule) -> None:
        """Chart includes a horizontal reference line at y=100."""
        fig = create_coverage_chart(sample_schedule)
        # Check for shapes (hlines are added as shapes in plotly)
        has_ref_line = False
        if fig.layout.shapes:
            for shape in fig.layout.shapes:
                if hasattr(shape, "y0") and shape.y0 == 100:
                    has_ref_line = True
                    break
        assert has_ref_line

    def test_coverage_handles_applicable_days_filtering(self) -> None:
        """Shift types with applicable_days are handled correctly."""
        workers = [Worker(id="W1", name="Alice")]
        # Weekend shift only applicable on Sat(5) and Sun(6)
        shift_types = [
            ShiftType(
                id="weekend",
                name="Weekend",
                category="weekend",
                start_time=time(8, 0),
                end_time=time(16, 0),
                duration_hours=8.0,
                workers_required=1,
                applicable_days=frozenset({5, 6}),
            )
        ]
        # Period starts on Monday - no applicable days
        period = PeriodAssignment(
            period_index=0,
            period_start=date(2026, 2, 2),  # Monday
            period_end=date(2026, 2, 8),
            assignments={},
        )
        schedule = Schedule(
            schedule_id="appdays",
            start_date=date(2026, 2, 2),
            end_date=date(2026, 2, 8),
            period_type="week",
            periods=[period],
            workers=workers,
            shift_types=shift_types,
        )
        fig = create_coverage_chart(schedule)
        assert isinstance(fig, go.Figure)
