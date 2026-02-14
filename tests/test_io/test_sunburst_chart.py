"""Tests for Sunburst Drill-Down chart."""

from datetime import date, time

import plotly.graph_objects as go
import pytest

from shift_solver.io.plotly_handler.charts.sunburst import create_sunburst
from shift_solver.models import ShiftType, Worker
from shift_solver.models.schedule import PeriodAssignment, Schedule
from shift_solver.models.shift import ShiftInstance


class TestSunburstChart:
    def test_sunburst_returns_figure(self, sample_schedule: Schedule) -> None:
        """create_sunburst returns a plotly Figure."""
        fig = create_sunburst(sample_schedule)
        assert isinstance(fig, go.Figure)

    def test_sunburst_root_is_schedule(self, sample_schedule: Schedule) -> None:
        """Root node is labeled 'Schedule'."""
        fig = create_sunburst(sample_schedule)
        trace = fig.data[0]
        assert "Schedule" in list(trace.labels)

    def test_sunburst_categories_at_level_two(
        self, sample_schedule: Schedule
    ) -> None:
        """Category nodes have 'Schedule' as parent."""
        fig = create_sunburst(sample_schedule)
        trace = fig.data[0]
        ids_list = list(trace.ids)
        parents_list = list(trace.parents)
        for i, id_val in enumerate(ids_list):
            if str(id_val).startswith("cat-"):
                assert parents_list[i] == "Schedule"

    def test_sunburst_shift_types_under_correct_category(
        self, sample_schedule: Schedule
    ) -> None:
        """Shift type nodes parent to their category."""
        fig = create_sunburst(sample_schedule)
        trace = fig.data[0]
        ids_list = list(trace.ids)
        parents_list = list(trace.parents)
        for i, id_val in enumerate(ids_list):
            if str(id_val).startswith("st-"):
                # Parent should be a category node
                assert str(parents_list[i]).startswith("cat-")

    def test_sunburst_worker_values_sum_to_shift_type_total(
        self, sample_schedule: Schedule
    ) -> None:
        """Worker counts under a shift type sum to that shift type's total."""
        fig = create_sunburst(sample_schedule)
        trace = fig.data[0]
        ids_list = list(trace.ids)
        parents_list = list(trace.parents)
        values_list = list(trace.values)

        # For each shift type, sum worker values
        for i, id_val in enumerate(ids_list):
            if str(id_val).startswith("st-"):
                st_total = values_list[i]
                worker_sum = sum(
                    values_list[j]
                    for j, parent in enumerate(parents_list)
                    if parent == id_val
                )
                assert worker_sum == st_total

    def test_sunburst_handles_single_shift_type(self) -> None:
        """Works with only one shift type."""
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
            schedule_id="single-st",
            start_date=date(2026, 2, 2),
            end_date=date(2026, 2, 8),
            period_type="week",
            periods=[period],
            workers=workers,
            shift_types=shift_types,
        )
        fig = create_sunburst(schedule)
        assert isinstance(fig, go.Figure)
        trace = fig.data[0]
        assert "Schedule" in list(trace.labels)
