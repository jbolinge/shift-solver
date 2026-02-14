"""Fairness Box Plots chart."""

from collections import defaultdict

import plotly.graph_objects as go

from shift_solver.io.plotly_handler.utils import (
    flatten_assignments,
    get_category_color,
    get_default_layout,
)
from shift_solver.models.schedule import Schedule


def create_fairness_chart(schedule: Schedule) -> go.Figure:
    """Create box plots showing assignment distribution by category."""
    flat_records = flatten_assignments(schedule)
    categories = sorted({st.category for st in schedule.shift_types})

    # Count assignments per worker per category
    worker_cat_counts: dict[str, dict[str, int]] = defaultdict(
        lambda: defaultdict(int)
    )
    for rec in flat_records:
        worker_cat_counts[rec["worker_id"]][rec["category"]] += 1

    fig = go.Figure()
    for category in categories:
        counts = []
        names = []
        for worker in schedule.workers:
            counts.append(worker_cat_counts[worker.id][category])
            names.append(worker.name)

        fig.add_trace(
            go.Box(
                y=counts,
                name=category,
                boxpoints="all",
                pointpos=0,
                jitter=0.3,
                marker_color=get_category_color(category),
                text=names,
                hovertemplate=(
                    "Worker: %{text}<br>"
                    "Assignments: %{y}<br>"
                    "<extra></extra>"
                ),
            )
        )

    layout = get_default_layout(
        title="Fairness Analysis: Assignment Distribution by Category",
        xaxis_title="Shift Category",
        yaxis_title="Number of Assignments",
    )
    fig.update_layout(**layout)
    return fig
