"""Worker-Period Heatmap chart."""

from collections import defaultdict

import plotly.graph_objects as go

from shift_solver.io.plotly_handler.utils import get_default_layout
from shift_solver.models.schedule import Schedule


def create_heatmap(schedule: Schedule) -> go.Figure:
    """Create a heatmap showing shift counts per worker per period."""
    shift_type_map = {st.id: st for st in schedule.shift_types}

    # Build worker labels (Y-axis)
    worker_labels = [f"{w.name} ({w.id})" for w in schedule.workers]
    worker_ids = [w.id for w in schedule.workers]

    # Build period labels (X-axis)
    period_labels = [
        f"P{p.period_index}: {p.period_start}" for p in schedule.periods
    ]

    # Build z-matrix (shift counts) and text matrix (abbreviations)
    z: list[list[int]] = []
    text: list[list[str]] = []

    for worker_id in worker_ids:
        row_z: list[int] = []
        row_text: list[str] = []
        for period in schedule.periods:
            shifts = period.get_worker_shifts(worker_id)
            row_z.append(len(shifts))
            # Build abbreviation string
            abbrevs: list[str] = []
            for shift in shifts:
                st = shift_type_map.get(shift.shift_type_id)
                if st:
                    abbrevs.append(st.name[0].upper())
                else:
                    abbrevs.append("?")
            row_text.append(", ".join(abbrevs) if abbrevs else "")
        z.append(row_z)
        text.append(row_text)

    # Build hover text
    hover: list[list[str]] = []
    for wi, worker_id in enumerate(worker_ids):
        row_hover: list[str] = []
        for pi, period in enumerate(schedule.periods):
            shifts = period.get_worker_shifts(worker_id)
            breakdown: dict[str, int] = defaultdict(int)
            for shift in shifts:
                st = shift_type_map.get(shift.shift_type_id)
                name = st.name if st else shift.shift_type_id
                breakdown[name] += 1
            lines = [
                f"Worker: {schedule.workers[wi].name} ({worker_id})",
                f"Period: {period.period_start} - {period.period_end}",
            ]
            for name, count in breakdown.items():
                lines.append(f"  {name}: {count}")
            lines.append(f"Total: {z[wi][pi]}")
            row_hover.append("<br>".join(lines))
        hover.append(row_hover)

    fig = go.Figure(
        data=go.Heatmap(
            z=z,
            x=period_labels,
            y=worker_labels,
            text=text,
            texttemplate="%{text}",
            hovertext=hover,
            hovertemplate="%{hovertext}<extra></extra>",
            colorscale="Blues",
        )
    )

    layout = get_default_layout(
        title="Worker-Period Shift Assignment Heatmap",
        xaxis_title="Period",
        yaxis_title="Worker",
    )
    fig.update_layout(**layout)
    return fig
