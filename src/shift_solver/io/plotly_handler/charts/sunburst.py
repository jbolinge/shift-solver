"""Sunburst Drill-Down chart."""

from collections import defaultdict

import plotly.graph_objects as go

from shift_solver.io.plotly_handler.utils import (
    flatten_assignments,
    get_category_color,
    get_default_layout,
)
from shift_solver.models.schedule import Schedule


def create_sunburst(schedule: Schedule) -> go.Figure:
    """Create a hierarchical sunburst: Schedule > Categories > Shift Types > Workers."""
    flat_records = flatten_assignments(schedule)
    shift_type_map = {st.id: st for st in schedule.shift_types}
    worker_map = {w.id: w for w in schedule.workers}

    total_assignments = len(flat_records)

    # Count assignments per category, shift_type, and worker
    cat_totals: dict[str, int] = defaultdict(int)
    st_totals: dict[str, int] = defaultdict(int)
    worker_st_counts: dict[str, dict[str, int]] = defaultdict(
        lambda: defaultdict(int)
    )

    for rec in flat_records:
        cat_totals[rec["category"]] += 1
        st_totals[rec["shift_type_id"]] += 1
        worker_st_counts[rec["shift_type_id"]][rec["worker_id"]] += 1

    # Build parallel arrays
    ids: list[str] = ["Schedule"]
    labels: list[str] = ["Schedule"]
    parents: list[str] = [""]
    values: list[int] = [total_assignments]
    colors: list[str] = [""]

    categories = sorted(cat_totals.keys())
    for category in categories:
        cat_id = f"cat-{category}"
        ids.append(cat_id)
        labels.append(category.title())
        parents.append("Schedule")
        values.append(cat_totals[category])
        colors.append(get_category_color(category))

        # Shift types in this category
        for st in schedule.shift_types:
            if st.category != category or st.id not in st_totals:
                continue
            st_id = f"st-{st.id}"
            ids.append(st_id)
            labels.append(st.name)
            parents.append(cat_id)
            values.append(st_totals[st.id])
            colors.append(get_category_color(category))

            # Workers with this shift type
            for worker_id, count in sorted(
                worker_st_counts[st.id].items()
            ):
                worker = worker_map.get(worker_id)
                w_id = f"w-{worker_id}-{st.id}"
                ids.append(w_id)
                labels.append(worker.name if worker else worker_id)
                parents.append(st_id)
                values.append(count)
                colors.append(get_category_color(category))

    fig = go.Figure(
        go.Sunburst(
            ids=ids,
            labels=labels,
            parents=parents,
            values=values,
            branchvalues="total",
            marker={"colors": colors},
        )
    )

    layout = get_default_layout(
        title="Assignment Hierarchy: Category > Shift Type > Worker",
        margin={"l": 10, "r": 10, "t": 60, "b": 10},
    )
    fig.update_layout(**layout)
    return fig
