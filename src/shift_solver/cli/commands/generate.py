"""Generate command for creating optimized schedules."""

from __future__ import annotations

import json
import signal
import threading
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

import click

from shift_solver.cli.helpers import shift_type_from_config
from shift_solver.config import ShiftSolverConfig
from shift_solver.config.schema import SolverConfig
from shift_solver.constraints.base import ConstraintConfig
from shift_solver.io import CSVLoaderError, ExcelHandlerError, make_loader
from shift_solver.models import Availability, SchedulingRequest, ShiftType, Worker
from shift_solver.solver import ShiftSolver

if TYPE_CHECKING:
    from collections.abc import Callable

    from shift_solver.models import Schedule
    from shift_solver.solver import SolverProgressCallback

# Period types this command can compute date ranges for. The config schema
# (ScheduleConfig.period_type) validates against the same set at load time,
# but _check_period_type_supported keeps a defensive check here so a schema/
# CLI drift fails loudly rather than producing wrong period math. "day" gives
# each calendar day its own period, which is what day-granular constraints
# (min_rest, weekend, max_consecutive, ...) need to be meaningful.
SUPPORTED_PERIOD_TYPES = frozenset({"day", "week"})

_PERIOD_LENGTH_DAYS = {"day": 1, "week": 7}


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
    default=None,
    help=(
        "Schedule end date (YYYY-MM-DD). Optional when the config sets "
        "schedule.num_periods, which then determines the horizon."
    ),
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
@click.option(
    "--gap",
    type=click.FloatRange(min=0.0),
    default=None,
    help="Relative optimality gap to stop at (0.0 = prove optimal)",
)
@click.option(
    "--log-search",
    is_flag=True,
    help="Log CP-SAT search progress to stderr",
)
@click.option(
    "--progress",
    is_flag=True,
    help="Print solution progress while solving; Ctrl-C keeps the best so far",
)
@click.option(
    "--explain",
    is_flag=True,
    help="Print a per-constraint objective penalty breakdown after solving",
)
@click.pass_context
def generate(
    ctx: click.Context,
    start_date: datetime,
    end_date: datetime | None,
    output: Path,
    quick_solve: bool,
    time_limit: int | None,
    demo: bool,
    workers: Path | None,
    availability: Path | None,
    requests: Path | None,
    gap: float | None,
    log_search: bool,
    progress: bool,
    explain: bool,
) -> None:
    """Generate an optimized schedule for the specified date range."""
    config_path = ctx.obj.get("config_path")
    config_explicit = bool(ctx.obj.get("config_explicit", False))
    verbose = ctx.obj.get("verbose", 0)

    # Load configuration
    cfg = _load_config(config_path, config_explicit, verbose)
    shift_types = _load_shift_types(cfg, verbose)
    constraint_configs = _load_constraint_configs(config_path, verbose)
    _check_period_type_supported(cfg)
    period_type = cfg.schedule.period_type if cfg is not None else "week"

    # Resolve the horizon: an explicit --end-date wins; otherwise
    # schedule.num_periods from config determines it.
    start = _to_date(start_date)
    end = _resolve_end_date(start, end_date, cfg, period_type)
    click.echo(f"Generating schedule from {start} to {end}")

    # Date format for CSV/Excel cells (schedule.date_format in config,
    # defaulting to "auto" like the loaders themselves when no config is
    # present).
    date_format = cfg.schedule.date_format.value if cfg is not None else "auto"

    # Get workers - exactly one of --demo or --workers is required.
    worker_list = _load_workers(demo, workers, verbose, date_format)
    availabilities = _load_availability(availability, verbose, date_format)
    request_list = _load_requests(requests, verbose, date_format)

    period_dates = _calculate_period_dates(start, end, period_type)
    click.echo(f"Schedule covers {len(period_dates)} {period_type} periods")

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

    callback, restore_sigint = _make_progress_callback(progress)
    try:
        result = solver.solve(
            time_limit_seconds=solve_time,
            num_workers=solver_config.num_workers,
            relative_gap_limit=gap,
            log_search_progress=log_search or None,
            solution_callback=callback,
        )
    finally:
        restore_sigint()

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

        if explain or verbose:
            _print_objective_breakdown(result.objective_breakdown)

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

    ScheduleConfig.period_type is already schema-validated against the same
    set, so this only fires if the schema and this command drift apart -
    better a clear error than silently wrong period math.
    """
    if cfg is None:
        return
    if cfg.schedule.period_type not in SUPPORTED_PERIOD_TYPES:
        raise click.ClickException(
            f"schedule.period_type '{cfg.schedule.period_type}' is not yet "
            f"supported by 'generate' (only {sorted(SUPPORTED_PERIOD_TYPES)} "
            "periods are implemented)."
        )


def _resolve_end_date(
    start: date,
    end_date: datetime | None,
    cfg: ShiftSolverConfig | None,
    period_type: str,
) -> date:
    """Resolve the schedule end date from --end-date or schedule.num_periods.

    An explicit --end-date always wins. Without one, schedule.num_periods
    from config determines the horizon (num_periods whole periods starting
    at start). Neither -> error.
    """
    if end_date is not None:
        return _to_date(end_date)

    num_periods = cfg.schedule.num_periods if cfg is not None else None
    if num_periods is None:
        raise click.ClickException(
            "No schedule horizon: pass --end-date or set schedule.num_periods "
            "in the config file."
        )
    period_length = _PERIOD_LENGTH_DAYS[period_type]
    return start + timedelta(days=num_periods * period_length - 1)


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


def _load_workers(
    demo: bool, workers_path: Path | None, verbose: int, date_format: str
) -> list[Worker]:
    """Load workers from --demo or a --workers CSV/Excel file (exactly one required)."""
    if demo and workers_path:
        raise click.ClickException("Use either --demo or --workers, not both.")
    if demo:
        worker_list = [Worker(id=f"W{i:03d}", name=f"Worker {i}") for i in range(1, 11)]
        click.echo(f"Using {len(worker_list)} demo workers")
        return worker_list
    if workers_path:
        try:
            worker_list = make_loader(workers_path, date_format).load_workers(
                workers_path
            )
        except (CSVLoaderError, ExcelHandlerError) as e:
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
    availability_path: Path | None, verbose: int, date_format: str
) -> list[Availability]:
    """Load availability records from a CSV/Excel file, if provided."""
    if not availability_path:
        return []
    try:
        availabilities = make_loader(availability_path, date_format).load_availability(
            availability_path
        )
    except (CSVLoaderError, ExcelHandlerError) as e:
        raise click.ClickException(f"Error loading availability: {e}") from e
    if verbose:
        click.echo(f"Loaded {len(availabilities)} availability records")
    return availabilities


def _load_requests(
    requests_path: Path | None, verbose: int, date_format: str
) -> list[SchedulingRequest]:
    """Load scheduling requests from a CSV/Excel file, if provided."""
    if not requests_path:
        return []
    try:
        request_list = make_loader(requests_path, date_format).load_requests(
            requests_path
        )
    except (CSVLoaderError, ExcelHandlerError) as e:
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


def _calculate_period_dates(
    start: date, end: date, period_type: str = "week"
) -> list[tuple[date, date]]:
    """Calculate period dates for the given period type.

    "day" makes each calendar day its own period; "week" chunks the range
    into 7-day periods (the final period is truncated at end when the range
    is not a whole number of weeks).
    """
    period_length = _PERIOD_LENGTH_DAYS[period_type]
    period_dates: list[tuple[date, date]] = []
    current = start
    while current <= end:
        period_end = min(current + timedelta(days=period_length - 1), end)
        period_dates.append((current, period_end))
        current = period_end + timedelta(days=1)
    return period_dates


def _make_progress_callback(
    progress: bool,
) -> tuple[SolverProgressCallback | None, Callable[[], None]]:
    """Build the --progress solution callback and a SIGINT restorer.

    With --progress, solution improvements are echoed as they are found and
    the first Ctrl-C sets a cancel event so CP-SAT stops gracefully and
    returns the best solution found so far (instead of killing the process).
    Returns (callback_or_None, restore_fn); callers must invoke restore_fn
    when solving finishes to reinstate the previous SIGINT handler.
    """
    if not progress:
        return None, lambda: None

    from shift_solver.solver import SolverProgressCallback

    cancel_event = threading.Event()

    def _on_progress(data: dict[str, Any]) -> None:
        click.echo(
            f"  [{data['wall_time']}s] solutions={data['solutions_found']} "
            f"objective={data['objective_value']:.0f} "
            f"bound={data['best_bound']:.0f} gap={data['gap_percent']}%"
        )

    def _on_sigint(signum: int, frame: Any) -> None:  # noqa: ARG001
        click.echo("Cancellation requested - returning best solution found...")
        cancel_event.set()

    previous_handler = signal.signal(signal.SIGINT, _on_sigint)

    def _restore() -> None:
        signal.signal(signal.SIGINT, previous_handler)

    callback = SolverProgressCallback(
        cancel_event=cancel_event, on_progress=_on_progress
    )
    return callback, _restore


def _print_objective_breakdown(
    breakdown: dict[str, dict[str, float]] | None,
) -> None:
    """Print the per-constraint objective penalty table (--explain)."""
    if not breakdown:
        click.echo("\nObjective breakdown: no soft constraint penalties recorded.")
        return

    click.echo("\nObjective breakdown (penalty = violations x weight):")
    width = max(len(cid) for cid in breakdown)
    for constraint_id in sorted(breakdown, key=lambda c: -breakdown[c]["penalty"]):
        entry = breakdown[constraint_id]
        click.echo(
            f"  {constraint_id:<{width}}  violations={entry['violations']:.0f}  "
            f"total={entry['violation_total']:.0f}  penalty={entry['penalty']:.0f}"
        )


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
