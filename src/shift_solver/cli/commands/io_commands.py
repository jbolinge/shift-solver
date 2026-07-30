"""Import and export commands for scheduling data."""

import json
from pathlib import Path

import click

from shift_solver.cli.helpers import build_schedule_from_json, shift_type_from_config
from shift_solver.config import ShiftSolverConfig
from shift_solver.io import (
    CSVLoaderError,
    ExcelExporter,
    ExcelHandlerError,
    ExcelLoader,
    make_loader,
)
from shift_solver.models import ShiftType, Worker


@click.command("import-data")
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Configuration file (used for schedule.date_format)",
)
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
    config: Path | None,
    workers: Path | None,
    availability: Path | None,
    requests: Path | None,
    excel: Path | None,
) -> None:
    """Import worker and scheduling data from files."""
    verbose = ctx.obj.get("verbose", 0)

    # Fall back to the group-level -c/--config when --config isn't given to
    # this subcommand directly (same pattern as list-shifts/export_schedule).
    config_path = config or ctx.obj.get("config_path")
    date_format = _resolve_date_format(config_path)

    if excel:
        _import_from_excel(excel, verbose, date_format)
    else:
        _import_from_separate_files(
            workers, availability, requests, verbose, date_format
        )

    # shift-solver has no database: this command validates that the given
    # files parse cleanly, it does not persist anything. Pass the same files
    # directly to 'generate --workers/--availability/--requests' or
    # 'validate --workers/--availability/--requests' to actually use them.
    click.echo("All files are valid.")
    click.echo(
        "Note: this command only validates files; shift-solver has no "
        "database. Pass them to 'generate' or 'validate' via "
        "--workers/--availability/--requests to use them."
    )


def _resolve_date_format(config_path: Path | None) -> str:
    """Resolve schedule.date_format from --config, defaulting to "auto".

    Mirrors generate/validate's date_format resolution: a config that
    doesn't exist (e.g. the group's unmodified default path) is silently
    treated as "no config", not an error -- import-data is a validate-only
    convenience command, not the strict entry point for config errors.
    """
    if not (config_path and config_path.exists()):
        return "auto"
    try:
        cfg = ShiftSolverConfig.load_from_yaml(config_path)
    except Exception as e:
        raise click.ClickException(f"Error loading config: {e}") from e
    return cfg.schedule.date_format.value


def _import_from_excel(excel: Path, verbose: int, date_format: str) -> None:
    """Import from a single Excel workbook."""
    click.echo(f"Importing from Excel workbook: {excel}")
    try:
        loader = ExcelLoader(date_format=date_format)
        data = loader.load_all(excel)
        click.echo(f"  Workers: {len(data['workers'])}")
        click.echo(f"  Availability records: {len(data['availability'])}")
        click.echo(f"  Requests: {len(data['requests'])}")

        if verbose:
            for w in data["workers"]:
                if isinstance(w, Worker):
                    click.echo(f"    - {w.id}: {w.name}")

    except ExcelHandlerError as e:
        raise click.ClickException(f"Excel import error: {e}") from e


def _import_from_separate_files(
    workers: Path | None,
    availability: Path | None,
    requests: Path | None,
    verbose: int,
    date_format: str,
) -> None:
    """Import from individual CSV/Excel files."""
    if workers:
        _import_workers(workers, verbose, date_format)

    if availability:
        _import_availability(availability, verbose, date_format)

    if requests:
        _import_requests(requests, verbose, date_format)

    if not workers and not availability and not requests:
        click.echo(
            "No files specified. Use --workers, --availability, --requests, or --excel."
        )
        raise click.ClickException("No input files specified")


def _import_workers(file_path: Path, verbose: int, date_format: str) -> None:
    """Import workers from a file."""
    click.echo(f"Importing workers from: {file_path}")
    try:
        worker_list = make_loader(file_path, date_format).load_workers(file_path)
        click.echo(f"  Loaded {len(worker_list)} workers")

        if verbose:
            for w in worker_list:
                click.echo(f"    - {w.id}: {w.name}")

    except (CSVLoaderError, ExcelHandlerError) as e:
        raise click.ClickException(f"Worker import error: {e}") from e


def _import_availability(
    file_path: Path,
    verbose: int,  # noqa: ARG001
    date_format: str,
) -> None:
    """Import availability from a file."""
    click.echo(f"Importing availability from: {file_path}")
    try:
        avail_list = make_loader(file_path, date_format).load_availability(file_path)
        click.echo(f"  Loaded {len(avail_list)} availability records")

    except (CSVLoaderError, ExcelHandlerError) as e:
        raise click.ClickException(f"Availability import error: {e}") from e


def _import_requests(
    file_path: Path,
    verbose: int,  # noqa: ARG001
    date_format: str,
) -> None:
    """Import requests from a file."""
    click.echo(f"Importing requests from: {file_path}")
    try:
        req_list = make_loader(file_path, date_format).load_requests(file_path)
        click.echo(f"  Loaded {len(req_list)} requests")

    except (CSVLoaderError, ExcelHandlerError) as e:
        raise click.ClickException(f"Request import error: {e}") from e


@click.command("export")
@click.option(
    "--schedule",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help="Schedule JSON file to export",
)
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Configuration file with shift type definitions (falls back to "
    "inferring approximate metadata from the schedule if omitted)",
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
    type=click.Choice(["excel", "json", "plotly"]),
    default="excel",
    help="Output format (plotly uses output as directory path)",
)
@click.option(
    "--include-worker-view/--no-worker-view",
    default=True,
    help="Include per-worker view in Excel export",
)
@click.pass_context
def export_schedule(
    ctx: click.Context,
    schedule: Path,
    config: Path | None,
    output: Path,
    output_format: str,
    include_worker_view: bool,
) -> None:
    """Export a schedule to Excel or JSON format."""
    # Fall back to the group-level -c/--config when --config isn't given to
    # this subcommand directly (same pattern as list-shifts).
    config_path = config or ctx.obj.get("config_path")

    click.echo(f"Exporting schedule from: {schedule}")

    # Load the schedule JSON
    try:
        with open(schedule) as f:
            schedule_data = json.load(f)
    except Exception as e:
        raise click.ClickException(f"Error reading schedule: {e}") from e

    if output_format == "json":
        # Just copy/format the JSON - no shift type metadata needed, so
        # --config (or its absence) is irrelevant here.
        output.parent.mkdir(parents=True, exist_ok=True)
        with open(output, "w") as f:
            json.dump(schedule_data, f, indent=2)
        click.echo(f"Schedule exported to: {output}")
        return

    # Real shift type metadata (category/times/duration/workers_required)
    # from config, if given; otherwise fall back to inference from the
    # schedule itself with a printed warning, since that's only an
    # approximation (category="unknown", a fixed 00:00-08:00 window).
    shift_types = _load_export_shift_types(config_path)

    if output_format == "plotly":
        from shift_solver.io import PlotlyVisualizer

        schedule_obj = build_schedule_from_json(schedule_data, shift_types=shift_types)
        visualizer = PlotlyVisualizer()
        visualizer.export_all(schedule_obj, output)

        chart_count = len(list(output.glob("*.html"))) - 1  # Exclude index
        click.echo(f"Exported {chart_count} charts + index to: {output}/")

    elif output_format == "excel":
        # Build Schedule object using helper
        schedule_obj = build_schedule_from_json(schedule_data, shift_types=shift_types)

        exporter = ExcelExporter()
        exporter.export_schedule(
            schedule_obj,
            output,
            include_worker_view=include_worker_view,
        )
        click.echo(f"Schedule exported to: {output}")


def _load_export_shift_types(config_path: Path | None) -> list[ShiftType] | None:
    """Build real ShiftTypes from --config, or None to fall back to inference.

    Returning None lets build_schedule_from_json infer approximate shift
    type metadata from the schedule JSON itself (see
    cli.helpers.infer_shift_types) - a printed warning makes that fallback
    visible rather than silent.
    """
    if config_path and config_path.exists():
        try:
            cfg = ShiftSolverConfig.load_from_yaml(config_path)
        except Exception as e:
            raise click.ClickException(f"Error loading config: {e}") from e
        return [shift_type_from_config(st) for st in cfg.shift_types]

    click.echo(
        "Warning: no --config given; inferring shift type metadata from the "
        "schedule (category/times/duration will be approximate)."
    )
    return None
