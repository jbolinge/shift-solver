"""Coverage Time Series chart."""

import plotly.graph_objects as go

from shift_solver.io.plotly_handler.utils import get_category_color, get_default_layout
from shift_solver.models.schedule import Schedule


def _has_applicable_days_in_period(
    shift_type_applicable_days: frozenset[int] | None,
    period_start: "date",
    period_end: "date",
) -> bool:
    """Check if any day in the period matches the shift's applicable days."""
    if shift_type_applicable_days is None:
        return True
    from datetime import timedelta

    current = period_start
    while current <= period_end:
        if current.weekday() in shift_type_applicable_days:
            return True
        current += timedelta(days=1)
    return False


def create_coverage_chart(schedule: Schedule) -> go.Figure:
    """Create a line chart showing coverage percentage over time per shift type."""
    from datetime import date  # noqa: F811

    fig = go.Figure()

    for shift_type in schedule.shift_types:
        x_labels: list[str] = []
        y_values: list[float] = []
        hover_texts: list[str] = []

        for period in schedule.periods:
            # Check applicable days
            if not _has_applicable_days_in_period(
                shift_type.applicable_days,
                period.period_start,
                period.period_end,
            ):
                continue

            label = f"P{period.period_index}: {period.period_start}"
            assigned = len(period.get_shifts_by_type(shift_type.id))
            required = shift_type.workers_required
            coverage_pct = (
                (assigned / required * 100) if required > 0 else 100.0
            )

            x_labels.append(label)
            y_values.append(coverage_pct)
            hover_texts.append(
                f"Period: {label}<br>"
                f"Coverage: {coverage_pct:.0f}%<br>"
                f"Assigned: {assigned}/{required}"
            )

        if x_labels:
            fig.add_trace(
                go.Scatter(
                    x=x_labels,
                    y=y_values,
                    mode="lines+markers",
                    name=shift_type.name,
                    line_color=get_category_color(shift_type.category),
                    hovertext=hover_texts,
                    hovertemplate="%{hovertext}<extra></extra>",
                )
            )

    # Reference line at 100%
    fig.add_hline(
        y=100,
        line_dash="dash",
        line_color="gray",
        annotation_text="100% Target",
    )

    layout = get_default_layout(
        title="Shift Coverage Over Time",
        xaxis_title="Period",
        yaxis_title="Coverage (%)",
    )
    fig.update_layout(**layout)
    return fig
