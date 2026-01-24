"""Command-line interface for shift-solver."""

import json
from datetime import date, timedelta
from pathlib import Path

import click

from shift_solver import __version__
from shift_solver.config import ShiftSolverConfig
from shift_solver.models import Worker, ShiftType
from shift_solver.solver import ShiftSolver
from shift_solver.io import (
    CSVLoader,
    CSVLoaderError,
    ExcelLoader,
    ExcelExporter,
    ExcelHandlerError,
    SampleGenerator,
)


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
@click.option(
    "--num-workers",
    type=int,
    default=15,
    help="Number of workers to generate",
)
@click.option(
    "--months",
    type=int,
    default=3,
    help="Number of months of data to generate",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["csv", "excel", "both"]),
    default="csv",
    help="Output format",
)
@click.option(
    "--seed",
    type=int,
    default=None,
    help="Random seed for reproducible generation",
)
def generate_samples(
    output_dir: Path,
    industry: str,
    num_workers: int,
    months: int,
    output_format: str,
    seed: int | None,
) -> None:
    """Generate sample input files for testing."""
    output_dir.mkdir(parents=True, exist_ok=True)

    click.echo(f"Generating {industry} sample data...")
    click.echo(f"  Workers: {num_workers}")
    click.echo(f"  Duration: {months} months")

    generator = SampleGenerator(industry=industry, seed=seed)

    # Calculate date range
    start_date = date.today().replace(day=1)
    # Add months
    end_month = start_date.month + months - 1
    end_year = start_date.year + (end_month - 1) // 12
    end_month = ((end_month - 1) % 12) + 1
    # Get last day of end month
    if end_month == 12:
        end_date = date(end_year, 12, 31)
    else:
        end_date = date(end_year, end_month + 1, 1) - timedelta(days=1)

    if output_format in ("csv", "both"):
        csv_dir = output_dir / "csv" if output_format == "both" else output_dir
        generator.generate_to_csv(
            output_dir=csv_dir,
            num_workers=num_workers,
            start_date=start_date,
            end_date=end_date,
        )
        click.echo(f"  CSV files written to: {csv_dir}")

    if output_format in ("excel", "both"):
        excel_dir = output_dir / "excel" if output_format == "both" else output_dir
        excel_dir.mkdir(parents=True, exist_ok=True)
        generator.generate_to_excel(
            output_file=excel_dir / "sample_data.xlsx",
            num_workers=num_workers,
            start_date=start_date,
            end_date=end_date,
        )
        click.echo(f"  Excel file written to: {excel_dir / 'sample_data.xlsx'}")

    click.echo("Sample data generation complete!")


@cli.command("import-data")
@click.option(
    "--workers",
    type=click.Path(exists=True, path_type=Path),
    help="Workers CSV or Excel file",
)
@click.option(
    "--availability",
    type=click.Path(exists=True, path_type=Path),
    help="Availability CSV or Excel file",
)
@click.option(
    "--requests",
    type=click.Path(exists=True, path_type=Path),
    help="Requests CSV or Excel file",
)
@click.option(
    "--excel",
    type=click.Path(exists=True, path_type=Path),
    help="Excel workbook with all data (Workers, Availability, Requests sheets)",
)
@click.pass_context
def import_data(
    ctx: click.Context,
    workers: Path | None,
    availability: Path | None,
    requests: Path | None,
    excel: Path | None,
) -> None:
    """Import worker and scheduling data from files."""
    verbose = ctx.obj.get("verbose", 0)

    if excel:
        # Import from single Excel workbook
        click.echo(f"Importing from Excel workbook: {excel}")
        try:
            loader = ExcelLoader()
            data = loader.load_all(excel)
            click.echo(f"  Workers: {len(data['workers'])}")
            click.echo(f"  Availability records: {len(data['availability'])}")
            click.echo(f"  Requests: {len(data['requests'])}")

            if verbose:
                for w in data["workers"]:
                    click.echo(f"    - {w.id}: {w.name}")

        except ExcelHandlerError as e:
            raise click.ClickException(f"Excel import error: {e}")
    else:
        # Import from individual files
        csv_loader = CSVLoader()
        excel_loader = ExcelLoader()

        if workers:
            click.echo(f"Importing workers from: {workers}")
            try:
                if workers.suffix == ".xlsx":
                    worker_list = excel_loader.load_workers(workers)
                else:
                    worker_list = csv_loader.load_workers(workers)
                click.echo(f"  Loaded {len(worker_list)} workers")

                if verbose:
                    for w in worker_list:
                        click.echo(f"    - {w.id}: {w.name}")

            except (CSVLoaderError, ExcelHandlerError) as e:
                raise click.ClickException(f"Worker import error: {e}")

        if availability:
            click.echo(f"Importing availability from: {availability}")
            try:
                if availability.suffix == ".xlsx":
                    avail_list = excel_loader.load_availability(availability)
                else:
                    avail_list = csv_loader.load_availability(availability)
                click.echo(f"  Loaded {len(avail_list)} availability records")

            except (CSVLoaderError, ExcelHandlerError) as e:
                raise click.ClickException(f"Availability import error: {e}")

        if requests:
            click.echo(f"Importing requests from: {requests}")
            try:
                if requests.suffix == ".xlsx":
                    req_list = excel_loader.load_requests(requests)
                else:
                    req_list = csv_loader.load_requests(requests)
                click.echo(f"  Loaded {len(req_list)} requests")

            except (CSVLoaderError, ExcelHandlerError) as e:
                raise click.ClickException(f"Request import error: {e}")

        if not workers and not availability and not requests:
            click.echo("No files specified. Use --workers, --availability, --requests, or --excel.")
            raise click.ClickException("No input files specified")

    click.echo("Import complete!")
    click.echo("Note: Database persistence not yet implemented. Data validated but not stored.")


@cli.command("export")
@click.option(
    "--schedule",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help="Schedule JSON file to export",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    required=True,
    help="Output file path",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["excel", "json"]),
    default="excel",
    help="Output format",
)
@click.option(
    "--include-worker-view/--no-worker-view",
    default=True,
    help="Include per-worker view in Excel export",
)
def export_schedule(
    schedule: Path,
    output: Path,
    output_format: str,
    include_worker_view: bool,
) -> None:
    """Export a schedule to Excel or JSON format."""
    click.echo(f"Exporting schedule from: {schedule}")

    # Load the schedule JSON
    try:
        with open(schedule) as f:
            schedule_data = json.load(f)
    except Exception as e:
        raise click.ClickException(f"Error reading schedule: {e}")

    if output_format == "json":
        # Just copy/format the JSON
        output.parent.mkdir(parents=True, exist_ok=True)
        with open(output, "w") as f:
            json.dump(schedule_data, f, indent=2)
        click.echo(f"Schedule exported to: {output}")

    elif output_format == "excel":
        # Convert to Schedule object and export
        from shift_solver.models import Schedule, PeriodAssignment, ShiftInstance

        # Reconstruct workers (minimal info from assignments)
        worker_ids = set()
        for period in schedule_data.get("periods", []):
            worker_ids.update(period.get("assignments", {}).keys())

        workers = [Worker(id=wid, name=wid) for wid in sorted(worker_ids)]

        # Reconstruct shift types (minimal info from assignments)
        shift_type_ids = set()
        for period in schedule_data.get("periods", []):
            for assignments in period.get("assignments", {}).values():
                for a in assignments:
                    shift_type_ids.add(a.get("shift_type_id"))

        from datetime import time

        shift_types = [
            ShiftType(
                id=stid,
                name=stid,
                category="unknown",
                start_time=time(0, 0),
                end_time=time(8, 0),
                duration_hours=8.0,
                workers_required=1,
            )
            for stid in sorted(shift_type_ids)
        ]

        # Reconstruct periods
        periods = []
        for p in schedule_data.get("periods", []):
            assignments: dict[str, list[ShiftInstance]] = {}
            for worker_id, shifts in p.get("assignments", {}).items():
                assignments[worker_id] = [
                    ShiftInstance(
                        shift_type_id=s["shift_type_id"],
                        period_index=p["period_index"],
                        date=date.fromisoformat(s["date"]),
                        worker_id=worker_id,
                    )
                    for s in shifts
                ]
            periods.append(
                PeriodAssignment(
                    period_index=p["period_index"],
                    period_start=date.fromisoformat(p["period_start"]),
                    period_end=date.fromisoformat(p["period_end"]),
                    assignments=assignments,
                )
            )

        schedule_obj = Schedule(
            schedule_id=schedule_data.get("schedule_id", "UNKNOWN"),
            start_date=date.fromisoformat(schedule_data["start_date"]),
            end_date=date.fromisoformat(schedule_data["end_date"]),
            period_type="week",
            periods=periods,
            workers=workers,
            shift_types=shift_types,
        )

        exporter = ExcelExporter()
        exporter.export_schedule(
            schedule_obj,
            output,
            include_worker_view=include_worker_view,
        )
        click.echo(f"Schedule exported to: {output}")


if __name__ == "__main__":
    cli()
