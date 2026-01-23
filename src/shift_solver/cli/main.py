"""Command-line interface for shift-solver."""

import json
from datetime import date, timedelta
from pathlib import Path

import click

from shift_solver import __version__
from shift_solver.config import ShiftSolverConfig
from shift_solver.models import Worker, ShiftType
from shift_solver.solver import ShiftSolver


@click.group()
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=False, path_type=Path),
    default="config/config.yaml",
    help="Configuration file path",
)
@click.option(
    "--db",
    type=click.Path(path_type=Path),
    default=None,
    help="Database path override",
)
@click.option(
    "-v",
    "--verbose",
    count=True,
    help="Increase verbosity (-v, -vv, -vvv)",
)
@click.pass_context
def cli(ctx: click.Context, config: Path, db: Path | None, verbose: int) -> None:
    """shift-solver: General-purpose shift scheduling optimization."""
    ctx.ensure_object(dict)
    ctx.obj["config_path"] = config
    ctx.obj["db_path"] = db
    ctx.obj["verbose"] = verbose


@cli.command()
def version() -> None:
    """Show version information."""
    click.echo(f"shift-solver v{__version__}")


@cli.command("init-db")
@click.option(
    "--db",
    type=click.Path(path_type=Path),
    default=None,
    help="Database path (overrides config)",
)
@click.pass_context
def init_db(ctx: click.Context, db: Path | None) -> None:
    """Initialize the SQLite database."""
    db_path = db or ctx.obj.get("db_path") or Path("shift_solver.db")

    # Create parent directories if needed
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # For now, just create an empty file as placeholder
    # Will be replaced with proper SQLAlchemy initialization
    db_path.touch()

    click.echo(f"Database initialized at: {db_path}")


@cli.command("check-config")
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help="Configuration file to validate",
)
def check_config(config: Path) -> None:
    """Validate a configuration file."""
    try:
        cfg = ShiftSolverConfig.load_from_yaml(config)
        click.echo(f"Configuration is valid!")
        click.echo(f"  Shift types: {len(cfg.shift_types)}")
        click.echo(f"  Constraints configured: {len(cfg.constraints)}")
        click.echo(f"  Solver time limit: {cfg.solver.max_time_seconds}s")
    except FileNotFoundError:
        raise click.ClickException(f"Configuration file not found: {config}")
    except Exception as e:
        raise click.ClickException(f"Invalid configuration: {e}")


@cli.command("list-workers")
@click.pass_context
def list_workers(ctx: click.Context) -> None:
    """List all workers in the database."""
    # Placeholder - will be implemented with database integration
    click.echo("No workers found. Import data first with 'import-data'.")


@cli.command("list-shifts")
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Configuration file",
)
@click.pass_context
def list_shifts(ctx: click.Context, config: Path | None) -> None:
    """List all shift types from configuration."""
    config_path = config or ctx.obj.get("config_path")

    if config_path and config_path.exists():
        try:
            cfg = ShiftSolverConfig.load_from_yaml(config_path)
            click.echo("Shift Types:")
            for st in cfg.shift_types:
                undesirable = " (undesirable)" if st.is_undesirable else ""
                click.echo(
                    f"  {st.id}: {st.name} [{st.category}] "
                    f"{st.start_time.strftime('%H:%M')}-{st.end_time.strftime('%H:%M')} "
                    f"({st.workers_required} workers){undesirable}"
                )
        except Exception as e:
            raise click.ClickException(f"Error loading config: {e}")
    else:
        click.echo("No configuration file found. Specify with --config.")


@cli.command()
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
    start_date: click.DateTime,
    end_date: click.DateTime,
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
        except Exception as e:
            raise click.ClickException(f"Error loading config: {e}")
    else:
        # Use demo shift types
        from datetime import time

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
        click.echo("Using demo shift types (no config file)")

    # Get workers - demo mode creates sample workers
    if demo:
        workers = [Worker(id=f"W{i:03d}", name=f"Worker {i}") for i in range(1, 11)]
        click.echo(f"Using {len(workers)} demo workers")
    else:
        # TODO: Load workers from database
        click.echo("Database not yet implemented. Use --demo flag for now.")
        raise click.ClickException("Use --demo flag until database is implemented")

    # Calculate period dates (weekly periods)
    start = start_date.date() if hasattr(start_date, "date") else date.fromisoformat(str(start_date)[:10])
    end = end_date.date() if hasattr(end_date, "date") else date.fromisoformat(str(end_date)[:10])

    period_dates: list[tuple[date, date]] = []
    current = start
    while current <= end:
        period_end = min(current + timedelta(days=6), end)
        period_dates.append((current, period_end))
        current = period_end + timedelta(days=1)

    click.echo(f"Schedule covers {len(period_dates)} periods")

    # Determine time limit
    if time_limit:
        solve_time = time_limit
    elif quick_solve:
        solve_time = 60
    else:
        solve_time = 300

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

        # Output schedule
        schedule = result.schedule
        assert schedule is not None

        # Write output
        output_data = {
            "schedule_id": schedule.schedule_id,
            "start_date": str(schedule.start_date),
            "end_date": str(schedule.end_date),
            "periods": [],
            "statistics": schedule.statistics,
        }

        for period in schedule.periods:
            period_data = {
                "period_index": period.period_index,
                "period_start": str(period.period_start),
                "period_end": str(period.period_end),
                "assignments": {},
            }
            for worker_id, shifts in period.assignments.items():
                period_data["assignments"][worker_id] = [
                    {
                        "shift_type_id": s.shift_type_id,
                        "date": str(s.date),
                    }
                    for s in shifts
                ]
            output_data["periods"].append(period_data)

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


@cli.command("generate-samples")
@click.option(
    "--output-dir",
    type=click.Path(path_type=Path),
    default="./data/samples",
    help="Output directory for sample files",
)
@click.option(
    "--industry",
    type=click.Choice(["retail", "healthcare", "warehouse"]),
    default="retail",
    help="Industry preset for sample data",
)
def generate_samples(output_dir: Path, industry: str) -> None:
    """Generate sample input files."""
    # Placeholder - will be implemented with I/O module
    output_dir.mkdir(parents=True, exist_ok=True)
    click.echo(f"Generating {industry} sample data in {output_dir}")
    click.echo("Sample generator not yet implemented. Coming in Epic 4.")


if __name__ == "__main__":
    cli()
