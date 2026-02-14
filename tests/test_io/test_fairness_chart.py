"""Tests for Fairness Box Plots chart."""

from datetime import date, time

import plotly.graph_objects as go
import pytest

from shift_solver.io.plotly_handler.charts.fairness import create_fairness_chart
from shift_solver.models import ShiftType, Worker
from shift_solver.models.schedule import PeriodAssignment, Schedule
from shift_solver.models.shift import ShiftInstance


class TestFairnessChart:
    def test_fairness_returns_figure(self, sample_schedule: Schedule) -> None:
        """create_fairness_chart returns a plotly Figure."""
        fig = create_fairness_chart(sample_schedule)
        assert isinstance(fig, go.Figure)

    def test_fairness_has_box_per_category(self, sample_schedule: Schedule) -> None:
        """One Box trace per unique shift category."""
        fig = create_fairness_chart(sample_schedule)
        box_traces = [t for t in fig.data if isinstance(t, go.Box)]
        # 2 categories: day and night
        assert len(box_traces) == 2

    def test_fairness_points_match_worker_count(
        self, sample_schedule: Schedule
    ) -> None:
        """Each box has points equal to number of workers."""
        fig = create_fairness_chart(sample_schedule)
        box_traces = [t for t in fig.data if isinstance(t, go.Box)]
        for trace in box_traces:
            assert len(trace.y) == 3  # 3 workers

    def test_fairness_hover_shows_worker_names(
        self, sample_schedule: Schedule
    ) -> None:
        """Hover text on points includes worker names."""
        fig = create_fairness_chart(sample_schedule)
        box_traces = [t for t in fig.data if isinstance(t, go.Box)]
        for trace in box_traces:
            assert trace.text is not None
            names = list(trace.text)
            assert "Alice" in names
            assert "Bob" in names
            assert "Charlie" in names

    def test_fairness_handles_single_category(self) -> None:
        """Works with only one shift category."""
        workers = [
            Worker(id="W1", name="Alice"),
            Worker(id="W2", name="Bob"),
        ]
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
                ],
                "W2": [
                    ShiftInstance(
                        shift_type_id="day",
                        period_index=0,
                        date=date(2026, 2, 3),
                        worker_id="W2",
                    )
                ],
            },
        )
        schedule = Schedule(
            schedule_id="single-cat",
            start_date=date(2026, 2, 2),
            end_date=date(2026, 2, 8),
            period_type="week",
            periods=[period],
            workers=workers,
            shift_types=shift_types,
        )
        fig = create_fairness_chart(schedule)
        box_traces = [t for t in fig.data if isinstance(t, go.Box)]
        assert len(box_traces) == 1

    def test_fairness_handles_zero_assignments(self) -> None:
        """Workers with 0 assignments in a category are still represented."""
        workers = [
            Worker(id="W1", name="Alice"),
            Worker(id="W2", name="Bob"),
        ]
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
        # Only W1 has assignments
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
            schedule_id="zero-assign",
            start_date=date(2026, 2, 2),
            end_date=date(2026, 2, 8),
            period_type="week",
            periods=[period],
            workers=workers,
            shift_types=shift_types,
        )
        fig = create_fairness_chart(schedule)
        box_traces = [t for t in fig.data if isinstance(t, go.Box)]
        # W2 should have 0 count for day
        assert len(box_traces[0].y) == 2
        assert 0 in list(box_traces[0].y)
