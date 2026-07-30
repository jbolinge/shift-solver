"""Generate command for creating optimized schedules."""

from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

import click

from shift_solver.cli.helpers import shift_type_from_config
from shift_solver.config import ShiftSolverConfig
from shift_solver.config.schema import SolverConfig
from shift_solver.constraints.base import ConstraintConfig
from shift_solver.io import CSVLoader, CSVLoaderError
from shift_solver.models import Availability, SchedulingRequest, ShiftType, Worker
from shift_solver.solver import ShiftSolver

if TYPE_CHECKING:
    from shift_solver.models import Schedule

# Shift-length limitation on the `schedule:` config section: period
# computation below is entirely week-based (see _calculate_period_dates).
# num_periods and date_format are similarly not consulted anywhere in this
# command. Rather than silently ignoring an unsupported period_type, reject
# it clearly - see _check_period_type_supported.
SUPPORTED_PERIOD_TYPES = frozenset({"week"})


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
    type=click.IntRange(min=1),
    default=None,
    help="Custom time limit in seconds",
)
@click.option(
    "--demo",
    is_flag=True,
    help="Use demo data instead of --workers",
)
@click.option(
    "--workers",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Workers CSV file (alternative to --demo)",
)
@click.option(
    "--availability",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Availability CSV file",
)
@click.option(
    "--requests",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Requests CSV file",
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
    workers: Path | None,
    availability: Path | None,
    requests: Path | None,
) -> None:
    """Generate an optimized schedule for the specified date range."""
    config_path = ctx.obj.get("config_path")
    config_explicit = bool(ctx.obj.get("config_explicit", False))
    verbose = ctx.obj.get("verbose", 0)

    click.echo(f"Generating schedule from {start_date.date()} to {end_date.date()}")

    # Load configuration
    cfg = _load_config(config_path, config_explicit, verbose)
    shift_types = _load_shift_types(cfg, verbose)
    constraint_configs = _load_constraint_configs(config_path, verbose)
    _check_period_type_supported(cfg)

    # Get workers - exactly one of --demo or --workers is required.
    worker_list = _load_workers(demo, workers, verbose)
    availabilities = _load_availability(availability, verbose)
    request_list = _load_requests(requests, verbose)

    # Calculate period dates (weekly periods)
    start = _to_date(start_date)
    end = _to_date(end_date)

    period_dates = _calculate_period_dates(start, end)
    click.echo(f"Schedule covers {len(period_dates)} periods")

    # Determine time limit and worker count, honoring solver: config with
    # explicit CLI flags taking priority.
    solver_config = cfg.solver if cfg is not None else SolverConfig()
    solve_time = _determine_time_limit(time_limit, quick_solve, solver_config)
    click.echo(f"Solving with {solve_time}s time limit...")

    # Create and run solver. constraint_configs from config.yaml ARE honored
    # here, as are any --workers/--availability/--requests CSVs supplied.
    solver = ShiftSolver(
        workers=worker_list,
        shift_types=shift_types,
        period_dates=period_dates,
        schedule_id=f"SCH-{start.strftime('%Y%m%d')}",
        availabilities=availabilities,
        requests=request_list,
        constraint_configs=constraint_configs,
    )

    result = solver.solve(
        time_limit_seconds=solve_time,
        num_workers=solver_config.num_workers,
    )

    for warning in result.warnings:
        click.echo(f"Warning: {warning}")

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


def _load_config(
    config_path: Path | None, config_explicit: bool, verbose: int
) -> ShiftSolverConfig | None:
    """Load and validate a config file, or None if no config file is present.

    ``config_explicit`` distinguishes "the user passed -c/--config" from
    "click applied its 'config/config.yaml' default because none was
    given" (see ``cli.main.cli``'s ``config_explicit`` context value).
    Falling back to demo shift types (a None return) is only appropriate
    when NO config was specified at all -- if the user DID specify a path
    and it doesn't exist, that's an error, not "no config".

    Raises:
        click.ClickException: If a config path was explicitly given but
            does not exist, or if the path exists but fails to load/validate.
    """
    if not config_path:
        return None
    if not config_path.exists():
        if config_explicit:
            raise click.ClickException(f"Configuration file not found: {config_path}")
        return None
    try:
        cfg = ShiftSolverConfig.load_from_yaml(config_path)
    except Exception as e:
        raise click.ClickException(f"Error loading config: {e}") from e
    if verbose:
        click.echo(f"Loaded config from {config_path}")
    return cfg


def _check_period_type_supported(cfg: ShiftSolverConfig | None) -> None:
    """Reject a schedule.period_type this command can't actually honor.

    Period computation below (_calculate_period_dates) is hardcoded to
    weekly periods; num_periods and date_format are likewise not consulted
    anywhere in this command. Rather than silently ignoring a
    schedule.period_type of anything else, fail clearly.
    """
    if cfg is None:
        return
    if cfg.schedule.period_type not in SUPPORTED_PERIOD_TYPES:
        raise click.ClickException(
            f"schedule.period_type '{cfg.schedule.period_type}' is not yet "
            f"supported by 'generate' (only {sorted(SUPPORTED_PERIOD_TYPES)} "
            "periods are implemented)."
        )


def _load_shift_types(cfg: ShiftSolverConfig | None, verbose: int) -> list[ShiftType]:
    """Load shift types from config or use demo defaults."""
    if cfg is not None:
        shift_types = [shift_type_from_config(st) for st in cfg.shift_types]
        if verbose:
            click.echo(f"Loaded {len(shift_types)} shift types from config")
        return shift_types
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


def _load_workers(demo: bool, workers_path: Path | None, verbose: int) -> list[Worker]:
    """Load workers from --demo or a --workers CSV file (exactly one required)."""
    if demo and workers_path:
        raise click.ClickException("Use either --demo or --workers, not both.")
    if demo:
        worker_list = [Worker(id=f"W{i:03d}", name=f"Worker {i}") for i in range(1, 11)]
        click.echo(f"Using {len(worker_list)} demo workers")
        return worker_list
    if workers_path:
        try:
            worker_list = CSVLoader().load_workers(workers_path)
        except CSVLoaderError as e:
            raise click.ClickException(f"Error loading workers: {e}") from e
        click.echo(f"Using {len(worker_list)} workers from {workers_path}")
        if verbose:
            for w in worker_list:
                click.echo(f"  - {w.id}: {w.name}")
        return worker_list

    raise click.ClickException(
        "No worker source specified. Use --workers <file.csv> or --demo."
    )


def _load_availability(
    availability_path: Path | None, verbose: int
) -> list[Availability]:
    """Load availability records from a CSV file, if provided."""
    if not availability_path:
        return []
    try:
        availabilities = CSVLoader().load_availability(availability_path)
    except CSVLoaderError as e:
        raise click.ClickException(f"Error loading availability: {e}") from e
    if verbose:
        click.echo(f"Loaded {len(availabilities)} availability records")
    return availabilities


def _load_requests(requests_path: Path | None, verbose: int) -> list[SchedulingRequest]:
    """Load scheduling requests from a CSV file, if provided."""
    if not requests_path:
        return []
    try:
        request_list = CSVLoader().load_requests(requests_path)
    except CSVLoaderError as e:
        raise click.ClickException(f"Error loading requests: {e}") from e
    if verbose:
        click.echo(f"Loaded {len(request_list)} requests")
    return request_list


def _load_constraint_configs(
    config_path: Path | None, verbose: int
) -> dict[str, ConstraintConfig]:
    """Load constraint configurations from config, converting to solver configs.

    The config file uses ``shift_solver.config.schema.ConstraintConfig`` (a
    Pydantic model whose enabled/is_hard/weight are Optional - None means
    "inherit the ConstraintRegistry registration's default"), but the
    solver/constraint classes expect
    ``shift_solver.constraints.base.ConstraintConfig`` (a dataclass with
    concrete bool/int fields and a ``get_param`` helper). This adapter
    resolves each configured constraint via
    ``ShiftSolverConfig.get_constraint_config`` (so None fields fall back to
    the registry, rather than leaking through as a falsy None that would
    look "disabled") and bridges the two.

    Returns an empty dict when no config file is present, so the solver falls
    back to the registry's default constraint configuration.
    """
    if not (config_path and config_path.exists()):
        return {}

    try:
        cfg = ShiftSolverConfig.load_from_yaml(config_path)
    except Exception as e:
        raise click.ClickException(f"Error loading config: {e}") from e

    constraint_configs = {}
    for constraint_id in cfg.constraints:
        resolved = cfg.get_constraint_config(constraint_id)
        constraint_configs[constraint_id] = ConstraintConfig(
            enabled=bool(resolved.enabled),
            is_hard=bool(resolved.is_hard),
            weight=resolved.weight if resolved.weight is not None else 100,
            parameters=dict(resolved.parameters),
        )
    if verbose:
        click.echo(f"Loaded {len(constraint_configs)} constraint configs from config")
    return constraint_configs


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


def _determine_time_limit(
    time_limit: int | None, quick_solve: bool, solver_config: SolverConfig
) -> int:
    """Determine the time limit for solving.

    Priority: an explicit --time-limit always wins; otherwise --quick-solve
    uses solver.quick_solution_seconds from config; otherwise
    solver.max_time_seconds from config. Both fall back to SolverConfig()'s
    defaults (quick_solution_seconds=60, max_time_seconds=3600) when no
    config file is present - note this raises the previous no-config,
    no-quick-solve default from a hardcoded 300s to 3600s, since that
    hardcoded value never came from anywhere honoring config.
    """
    if time_limit is not None:
        return time_limit
    elif quick_solve:
        return solver_config.quick_solution_seconds
    else:
        return solver_config.max_time_seconds


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
