"""Generate command for creating optimized schedules."""

from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

import click

from shift_solver.config import ShiftSolverConfig
from shift_solver.models import ShiftType, Worker
from shift_solver.solver import ShiftSolver

if TYPE_CHECKING:
    from shift_solver.models import Schedule


@click.command()
@click.option(
    "--start-date",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    required=True,
    help="Schedule start date (YYYY-MM-DD)",
)
@click.option(
    "--end-date",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    required=True,
    help="Schedule end date (YYYY-MM-DD)",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    required=True,
    help="Output file path",
)
@click.option(
    "--quick-solve",
    is_flag=True,
    help="Use quick solve mode (shorter time limit)",
)
@click.option(
    "--time-limit",
    type=int,
    default=None,
    help="Custom time limit in seconds",
)
@click.option(
    "--demo",
    is_flag=True,
    help="Use demo data (no database required)",
)
@click.pass_context
def generate(
    ctx: click.Context,
    start_date: datetime,
    end_date: datetime,
    output: Path,
    quick_solve: bool,
    time_limit: int | None,
    demo: bool,
) -> None:
    """Generate an optimized schedule for the specified date range."""
    config_path = ctx.obj.get("config_path")
    verbose = ctx.obj.get("verbose", 0)

    click.echo(f"Generating schedule from {start_date.date()} to {end_date.date()}")

    # Load configuration
    shift_types = _load_shift_types(config_path, verbose)

    # Get workers - demo mode creates sample workers
    if demo:
        workers = [Worker(id=f"W{i:03d}", name=f"Worker {i}") for i in range(1, 11)]
        click.echo(f"Using {len(workers)} demo workers")
    else:
        click.echo("Database not yet implemented. Use --demo flag for now.")
        raise click.ClickException("Use --demo flag until database is implemented")

    # Calculate period dates (weekly periods)
    start = _to_date(start_date)
    end = _to_date(end_date)

    period_dates = _calculate_period_dates(start, end)
    click.echo(f"Schedule covers {len(period_dates)} periods")

    # Determine time limit
    solve_time = _determine_time_limit(time_limit, quick_solve)
    click.echo(f"Solving with {solve_time}s time limit...")

    # Create and run solver
    solver = ShiftSolver(
        workers=workers,
        shift_types=shift_types,
        period_dates=period_dates,
        schedule_id=f"SCH-{start.strftime('%Y%m%d')}",
    )

    result = solver.solve(time_limit_seconds=solve_time)

    if result.success:
        click.echo(f"Solution found! Status: {result.status_name}")
        click.echo(f"Solve time: {result.solve_time_seconds:.2f}s")

        schedule = result.schedule
        assert schedule is not None

        # Write output
        output_data = _build_output_data(schedule)
        output.parent.mkdir(parents=True, exist_ok=True)
        with open(output, "w") as f:
            json.dump(output_data, f, indent=2)

        click.echo(f"Schedule written to: {output}")

        # Print summary
        if verbose:
            click.echo("\nWorker Statistics:")
            for worker_id, stats in schedule.statistics.items():
                click.echo(f"  {worker_id}: {stats.get('total_shifts', 0)} shifts")
    else:
        click.echo(f"No solution found. Status: {result.status_name}")
        raise click.ClickException("Failed to generate schedule")


def _load_shift_types(config_path: Path | None, verbose: int) -> list[ShiftType]:
    """Load shift types from config or use demo defaults."""
    if config_path and config_path.exists():
        try:
            cfg = ShiftSolverConfig.load_from_yaml(config_path)
            shift_types = [
                ShiftType(
                    id=st.id,
                    name=st.name,
                    category=st.category,
                    start_time=st.start_time,
                    end_time=st.end_time,
                    duration_hours=st.duration_hours,
                    is_undesirable=st.is_undesirable,
                    workers_required=st.workers_required,
                )
                for st in cfg.shift_types
            ]
            if verbose:
                click.echo(f"Loaded {len(shift_types)} shift types from config")
            return shift_types
        except Exception as e:
            raise click.ClickException(f"Error loading config: {e}") from e
    else:
        # Use demo shift types
        click.echo("Using demo shift types (no config file)")
        return [
            ShiftType(
                id="day",
                name="Day Shift",
                category="day",
                start_time=time(7, 0),
                end_time=time(15, 0),
                duration_hours=8.0,
                workers_required=2,
            ),
            ShiftType(
                id="night",
                name="Night Shift",
                category="night",
                start_time=time(23, 0),
                end_time=time(7, 0),
                duration_hours=8.0,
                workers_required=1,
                is_undesirable=True,
            ),
        ]


def _to_date(dt: datetime) -> date:
    """Convert datetime to date."""
    if hasattr(dt, "date"):
        return dt.date()
    return date.fromisoformat(str(dt)[:10])


def _calculate_period_dates(start: date, end: date) -> list[tuple[date, date]]:
    """Calculate weekly period dates."""
    period_dates: list[tuple[date, date]] = []
    current = start
    while current <= end:
        period_end = min(current + timedelta(days=6), end)
        period_dates.append((current, period_end))
        current = period_end + timedelta(days=1)
    return period_dates


def _determine_time_limit(time_limit: int | None, quick_solve: bool) -> int:
    """Determine the time limit for solving."""
    if time_limit:
        return time_limit
    elif quick_solve:
        return 60
    else:
        return 300


def _build_output_data(schedule: Schedule) -> dict[str, object]:
    """Build output data dict from schedule."""
    periods_list: list[dict[str, object]] = []
    output_data: dict[str, object] = {
        "schedule_id": schedule.schedule_id,
        "start_date": str(schedule.start_date),
        "end_date": str(schedule.end_date),
        "periods": periods_list,
        "statistics": schedule.statistics,
    }

    for period in schedule.periods:
        assignments_dict: dict[str, list[dict[str, str]]] = {}
        period_data: dict[str, object] = {
            "period_index": period.period_index,
            "period_start": str(period.period_start),
            "period_end": str(period.period_end),
            "assignments": assignments_dict,
        }
        for worker_id, shifts in period.assignments.items():
            assignments_dict[worker_id] = [
                {
                    "shift_type_id": s.shift_type_id,
                    "date": str(s.date),
                }
                for s in shifts
            ]
        periods_list.append(period_data)

    return output_data
