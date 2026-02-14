"""E2E integration tests for Plotly visualization pipeline."""

from datetime import date, time
from pathlib import Path

import pytest

from shift_solver.io.plotly_handler import PlotlyVisualizer
from shift_solver.models import ShiftType, Worker
from shift_solver.models.schedule import PeriodAssignment, Schedule
from shift_solver.models.shift import ShiftInstance


def _build_minimal_schedule() -> Schedule:
    """Build a minimal schedule: 2 workers, 1 shift type, 2 periods."""
    workers = [
        Worker(id="W001", name="Alice"),
        Worker(id="W002", name="Bob"),
    ]
    shift_types = [
        ShiftType(
            id="day",
            name="Day Shift",
            category="day",
            start_time=time(7, 0),
            end_time=time(15, 0),
            duration_hours=8.0,
            workers_required=2,
        ),
    ]
    period0 = PeriodAssignment(
        period_index=0,
        period_start=date(2026, 2, 2),
        period_end=date(2026, 2, 8),
        assignments={
            "W001": [
                ShiftInstance(shift_type_id="day", period_index=0, date=date(2026, 2, 2), worker_id="W001"),
            ],
            "W002": [
                ShiftInstance(shift_type_id="day", period_index=0, date=date(2026, 2, 3), worker_id="W002"),
            ],
        },
    )
    period1 = PeriodAssignment(
        period_index=1,
        period_start=date(2026, 2, 9),
        period_end=date(2026, 2, 15),
        assignments={
            "W001": [
                ShiftInstance(shift_type_id="day", period_index=1, date=date(2026, 2, 9), worker_id="W001"),
            ],
            "W002": [
                ShiftInstance(shift_type_id="day", period_index=1, date=date(2026, 2, 10), worker_id="W002"),
            ],
        },
    )
    return Schedule(
        schedule_id="E2E-MINIMAL",
        start_date=date(2026, 2, 2),
        end_date=date(2026, 2, 15),
        period_type="week",
        periods=[period0, period1],
        workers=workers,
        shift_types=shift_types,
    )


def _build_realistic_schedule() -> Schedule:
    """Build a realistic schedule: 8 workers, 3 shift types, 4 periods."""
    workers = [
        Worker(id=f"W{i:03d}", name=name)
        for i, name in enumerate(
            ["Alice", "Bob", "Charlie", "Diana", "Eve", "Frank", "Grace", "Hank"],
            start=1,
        )
    ]
    shift_types = [
        ShiftType(
            id="day",
            name="Day Shift",
            category="day",
            start_time=time(7, 0),
            end_time=time(15, 0),
            duration_hours=8.0,
            workers_required=3,
        ),
        ShiftType(
            id="night",
            name="Night Shift",
            category="night",
            start_time=time(23, 0),
            end_time=time(7, 0),
            duration_hours=8.0,
            workers_required=2,
            is_undesirable=True,
        ),
        ShiftType(
            id="weekend",
            name="Weekend Shift",
            category="weekend",
            start_time=time(8, 0),
            end_time=time(16, 0),
            duration_hours=8.0,
            workers_required=2,
            is_undesirable=True,
            applicable_days=frozenset({5, 6}),
        ),
    ]

    periods = []
    base = date(2026, 2, 2)
    for pi in range(4):
        from datetime import timedelta

        p_start = base + timedelta(weeks=pi)
        p_end = p_start + timedelta(days=6)
        assignments: dict[str, list[ShiftInstance]] = {}
        # Assign day shifts to first 3 workers
        for wi in range(3):
            wid = f"W{wi + 1:03d}"
            if wid not in assignments:
                assignments[wid] = []
            assignments[wid].append(
                ShiftInstance(
                    shift_type_id="day",
                    period_index=pi,
                    date=p_start,
                    worker_id=wid,
                )
            )
        # Assign night shifts to next 2 workers
        for wi in range(3, 5):
            wid = f"W{wi + 1:03d}"
            if wid not in assignments:
                assignments[wid] = []
            assignments[wid].append(
                ShiftInstance(
                    shift_type_id="night",
                    period_index=pi,
                    date=p_start,
                    worker_id=wid,
                )
            )
        # Assign weekend shifts to last 2 workers
        for wi in range(5, 7):
            wid = f"W{wi + 1:03d}"
            if wid not in assignments:
                assignments[wid] = []
            # Find the Saturday in this period
            sat = p_start
            while sat.weekday() != 5:
                sat += timedelta(days=1)
            if sat <= p_end:
                assignments[wid].append(
                    ShiftInstance(
                        shift_type_id="weekend",
                        period_index=pi,
                        date=sat,
                        worker_id=wid,
                    )
                )

        periods.append(
            PeriodAssignment(
                period_index=pi,
                period_start=p_start,
                period_end=p_end,
                assignments=assignments,
            )
        )

    return Schedule(
        schedule_id="E2E-REALISTIC",
        start_date=base,
        end_date=base + timedelta(weeks=4) - timedelta(days=1),
        period_type="week",
        periods=periods,
        workers=workers,
        shift_types=shift_types,
    )


@pytest.mark.e2e
class TestPlotlyVisualizationE2E:
    def test_e2e_plotly_export_minimal_schedule(self, tmp_path: Path) -> None:
        """Minimal schedule (2 workers, 1 shift, 2 periods) generates all chart files."""
        schedule = _build_minimal_schedule()
        visualizer = PlotlyVisualizer()
        output = tmp_path / "minimal_charts"
        visualizer.export_all(schedule, output)

        # All 6 HTML files should exist
        expected_files = [
            "index.html",
            "heatmap.html",
            "gantt.html",
            "fairness.html",
            "sunburst.html",
            "coverage.html",
        ]
        for fname in expected_files:
            fpath = output / fname
            assert fpath.exists(), f"Missing: {fname}"
            content = fpath.read_text()
            assert len(content) > 100, f"File too small: {fname}"
            # Charts should contain plotly div
            if fname != "index.html":
                assert "plotly" in content.lower() or "<div" in content

    def test_e2e_plotly_export_realistic_schedule(self, tmp_path: Path) -> None:
        """Realistic schedule (8 workers, 3 shifts, 4 periods) generates all charts."""
        schedule = _build_realistic_schedule()
        visualizer = PlotlyVisualizer()
        output = tmp_path / "realistic_charts"
        visualizer.export_all(schedule, output)

        expected_files = [
            "index.html",
            "heatmap.html",
            "gantt.html",
            "fairness.html",
            "sunburst.html",
            "coverage.html",
        ]
        for fname in expected_files:
            fpath = output / fname
            assert fpath.exists(), f"Missing: {fname}"
            content = fpath.read_text()
            assert len(content) > 100, f"File too small: {fname}"

        # Index should reference schedule ID
        index_content = (output / "index.html").read_text()
        assert "E2E-REALISTIC" in index_content
        assert "8" in index_content  # 8 workers

    def test_e2e_chart_data_matches_schedule_statistics(
        self, tmp_path: Path
    ) -> None:
        """Chart data is mathematically consistent with schedule data."""
        schedule = _build_minimal_schedule()
        visualizer = PlotlyVisualizer()
        output = tmp_path / "verify_charts"
        visualizer.export_all(schedule, output)

        # Verify heatmap values by recreating the chart and inspecting data
        from shift_solver.io.plotly_handler.charts.heatmap import create_heatmap
        from shift_solver.io.plotly_handler.charts.coverage import create_coverage_chart
        from shift_solver.io.plotly_handler.charts.sunburst import create_sunburst

        # Heatmap: each worker has 1 shift per period = 2 total
        heatmap_fig = create_heatmap(schedule)
        z = heatmap_fig.data[0].z
        # W001: 1 shift in P0, 1 in P1
        assert z[0][0] == 1
        assert z[0][1] == 1
        # W002: 1 shift in P0, 1 in P1
        assert z[1][0] == 1
        assert z[1][1] == 1

        # Coverage: 2 assigned out of 2 required = 100%
        # (Each period has both W001 and W002 each with 1 day shift = 2 total)
        coverage_fig = create_coverage_chart(schedule)
        scatter_traces = [
            t for t in coverage_fig.data
            if hasattr(t, "mode") and t.mode and "lines" in t.mode
        ]
        assert len(scatter_traces) == 1  # 1 shift type
        for y_val in scatter_traces[0].y:
            assert y_val == pytest.approx(100.0)

        # Sunburst: total assignments = 4 (2 workers * 2 periods * 1 shift each)
        sunburst_fig = create_sunburst(schedule)
        trace = sunburst_fig.data[0]
        # Root "Schedule" value should be 4
        root_idx = list(trace.ids).index("Schedule")
        assert trace.values[root_idx] == 4

        # Verify all workers appear in sunburst
        labels = list(trace.labels)
        assert "Alice" in labels
        assert "Bob" in labels
