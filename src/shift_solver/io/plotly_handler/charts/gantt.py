"""Gantt Timeline chart."""

from dataclasses import dataclass
from datetime import datetime, timedelta

import plotly.graph_objects as go

from shift_solver.io.plotly_handler.utils import get_category_color, get_default_layout
from shift_solver.models.schedule import Schedule


@dataclass
class _GanttRecord:
    worker: str
    start: datetime
    end: datetime
    shift: str
    category: str


def create_gantt(schedule: Schedule) -> go.Figure:
    """Create a Gantt timeline showing worker shift assignments."""
    shift_type_map = {st.id: st for st in schedule.shift_types}
    worker_map = {w.id: w for w in schedule.workers}

    category_records: dict[str, list[_GanttRecord]] = {}

    for period in schedule.periods:
        for worker_id, shifts in period.assignments.items():
            worker = worker_map.get(worker_id)
            worker_name = worker.name if worker else worker_id
            for shift in shifts:
                st = shift_type_map.get(shift.shift_type_id)
                if not st:
                    continue
                category = st.category
                start = datetime.combine(shift.date, st.start_time)
                end = start + timedelta(hours=st.duration_hours)

                if category not in category_records:
                    category_records[category] = []
                category_records[category].append(
                    _GanttRecord(
                        worker=worker_name,
                        start=start,
                        end=end,
                        shift=st.name,
                        category=category,
                    )
                )

    fig = go.Figure()
    for category, records in sorted(category_records.items()):
        color = get_category_color(category)
        durations_ms = [
            (rec.end - rec.start).total_seconds() * 1000
            for rec in records
        ]
        fig.add_trace(
            go.Bar(
                x=durations_ms,
                y=[rec.worker for rec in records],
                base=[rec.start for rec in records],
                orientation="h",
                name=category,
                marker_color=color,
                text=[rec.shift for rec in records],
                hovertemplate=(
                    "Worker: %{y}<br>"
                    "Shift: %{text}<br>"
                    "Start: %{base}<br>"
                    "<extra></extra>"
                ),
            )
        )

    layout = get_default_layout(
        title="Shift Assignment Timeline",
        xaxis_title="Date/Time",
        yaxis_title="Worker",
        barmode="stack",
        xaxis_type="date",
    )
    fig.update_layout(**layout)
    return fig
