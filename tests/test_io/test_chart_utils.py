"""Tests for Plotly chart utilities."""

from datetime import date, time

from shift_solver.io.plotly_handler.utils import (
    flatten_assignments,
    get_category_color,
    get_default_layout,
    get_worker_color_map,
)
from shift_solver.models import ShiftType, Worker
from shift_solver.models.schedule import PeriodAssignment, Schedule
from shift_solver.models.shift import ShiftInstance


def _make_schedule(
    workers: list[Worker],
    shift_types: list[ShiftType],
    assignments: dict[int, dict[str, list[ShiftInstance]]] | None = None,
) -> Schedule:
    """Helper to build a Schedule with optional assignments."""
    period = PeriodAssignment(
        period_index=0,
        period_start=date(2026, 2, 2),
        period_end=date(2026, 2, 8),
        assignments=assignments.get(0, {}) if assignments else {},
    )
    return Schedule(
        schedule_id="test",
        start_date=date(2026, 2, 2),
        end_date=date(2026, 2, 8),
        period_type="week",
        periods=[period],
        workers=workers,
        shift_types=shift_types,
    )


class TestChartUtils:
    def test_worker_color_palette_assigns_consistent_colors(self) -> None:
        """Same workers always get same colors."""
        workers = [Worker(id=f"W{i}", name=f"Worker {i}") for i in range(5)]
        map1 = get_worker_color_map(workers)
        map2 = get_worker_color_map(workers)
        assert map1 == map2

    def test_worker_color_palette_handles_up_to_20_workers(self) -> None:
        """20 workers get 20 distinct colors."""
        workers = [Worker(id=f"W{i}", name=f"Worker {i}") for i in range(20)]
        color_map = get_worker_color_map(workers)
        assert len(color_map) == 20
        assert len(set(color_map.values())) == 20

    def test_worker_color_palette_wraps_beyond_20(self) -> None:
        """More than 20 workers wraps around the palette."""
        workers = [Worker(id=f"W{i}", name=f"Worker {i}") for i in range(25)]
        color_map = get_worker_color_map(workers)
        assert len(color_map) == 25

    def test_shift_category_colors_map_known_categories(self) -> None:
        """Known categories return expected colors."""
        assert get_category_color("day") == "#4CAF50"
        assert get_category_color("night") == "#3F51B5"
        assert get_category_color("weekend") == "#FF9800"
        assert get_category_color("evening") == "#9C27B0"

    def test_shift_category_colors_fallback_for_unknown(self) -> None:
        """Unknown categories get a fallback color."""
        color = get_category_color("custom_category")
        assert isinstance(color, str)
        assert color.startswith("#")

    def test_flatten_assignments_returns_correct_records(self) -> None:
        """Records contain all expected fields with correct values."""
        workers = [Worker(id="W1", name="Alice")]
        shift_types = [
            ShiftType(
                id="day",
                name="Day Shift",
                category="day",
                start_time=time(7, 0),
                end_time=time(15, 0),
                duration_hours=8.0,
            )
        ]
        assignments = {
            0: {
                "W1": [
                    ShiftInstance(
                        shift_type_id="day",
                        period_index=0,
                        date=date(2026, 2, 2),
                        worker_id="W1",
                    )
                ]
            }
        }
        schedule = _make_schedule(workers, shift_types, assignments)
        records = flatten_assignments(schedule)
        assert len(records) == 1
        rec = records[0]
        assert rec["worker_id"] == "W1"
        assert rec["worker_name"] == "Alice"
        assert rec["shift_type_id"] == "day"
        assert rec["category"] == "day"
        assert rec["date"] == date(2026, 2, 2)
        assert rec["period_index"] == 0

    def test_flatten_assignments_empty_schedule(self) -> None:
        """Empty schedule returns empty list."""
        schedule = _make_schedule([], [], {0: {}})
        records = flatten_assignments(schedule)
        assert records == []

    def test_flatten_assignments_includes_all_fields(self) -> None:
        """Each record has worker_id, worker_name, shift_type_id, category, date, period_index, is_undesirable."""
        workers = [Worker(id="W1", name="Alice")]
        shift_types = [
            ShiftType(
                id="night",
                name="Night Shift",
                category="night",
                start_time=time(23, 0),
                end_time=time(7, 0),
                duration_hours=8.0,
                is_undesirable=True,
            )
        ]
        assignments = {
            0: {
                "W1": [
                    ShiftInstance(
                        shift_type_id="night",
                        period_index=0,
                        date=date(2026, 2, 2),
                        worker_id="W1",
                    )
                ]
            }
        }
        schedule = _make_schedule(workers, shift_types, assignments)
        records = flatten_assignments(schedule)
        expected_keys = {
            "worker_id",
            "worker_name",
            "shift_type_id",
            "category",
            "date",
            "period_index",
            "is_undesirable",
        }
        assert set(records[0].keys()) == expected_keys
        assert records[0]["is_undesirable"] is True

    def test_default_layout_contains_font_and_margins(self) -> None:
        """Default layout includes font family, margins, template."""
        layout = get_default_layout()
        assert "font" in layout
        assert "margin" in layout
        assert "template" in layout

    def test_default_layout_accepts_overrides(self) -> None:
        """Overrides are merged into default layout."""
        layout = get_default_layout(title="Custom Title", height=800)
        assert layout["title"] == "Custom Title"
        assert layout["height"] == 800
        assert "font" in layout  # defaults still present
