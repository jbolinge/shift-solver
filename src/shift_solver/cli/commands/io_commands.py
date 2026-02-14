"""Import and export commands for scheduling data."""

import json
from pathlib import Path

import click

from shift_solver.cli.helpers import build_schedule_from_json
from shift_solver.io import (
    CSVLoader,
    CSVLoaderError,
    ExcelExporter,
    ExcelHandlerError,
    ExcelLoader,
)
from shift_solver.models import Worker


@click.command("import-data")
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
        _import_from_excel(excel, verbose)
    else:
        _import_from_separate_files(workers, availability, requests, verbose)

    click.echo("Import complete!")
    click.echo(
        "Note: Database persistence not yet implemented. Data validated but not stored."
    )


def _import_from_excel(excel: Path, verbose: int) -> None:
    """Import from a single Excel workbook."""
    click.echo(f"Importing from Excel workbook: {excel}")
    try:
        loader = ExcelLoader()
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
) -> None:
    """Import from individual CSV/Excel files."""
    csv_loader = CSVLoader()
    excel_loader = ExcelLoader()

    if workers:
        _import_workers(workers, csv_loader, excel_loader, verbose)

    if availability:
        _import_availability(availability, csv_loader, excel_loader, verbose)

    if requests:
        _import_requests(requests, csv_loader, excel_loader, verbose)

    if not workers and not availability and not requests:
        click.echo(
            "No files specified. Use --workers, --availability, --requests, or --excel."
        )
        raise click.ClickException("No input files specified")


def _import_workers(
    file_path: Path,
    csv_loader: CSVLoader,
    excel_loader: ExcelLoader,
    verbose: int,
) -> None:
    """Import workers from a file."""
    click.echo(f"Importing workers from: {file_path}")
    try:
        if file_path.suffix == ".xlsx":
            worker_list = excel_loader.load_workers(file_path)
        else:
            worker_list = csv_loader.load_workers(file_path)
        click.echo(f"  Loaded {len(worker_list)} workers")

        if verbose:
            for w in worker_list:
                click.echo(f"    - {w.id}: {w.name}")

    except (CSVLoaderError, ExcelHandlerError) as e:
        raise click.ClickException(f"Worker import error: {e}") from e


def _import_availability(
    file_path: Path,
    csv_loader: CSVLoader,
    excel_loader: ExcelLoader,
    verbose: int,  # noqa: ARG001
) -> None:
    """Import availability from a file."""
    click.echo(f"Importing availability from: {file_path}")
    try:
        if file_path.suffix == ".xlsx":
            avail_list = excel_loader.load_availability(file_path)
        else:
            avail_list = csv_loader.load_availability(file_path)
        click.echo(f"  Loaded {len(avail_list)} availability records")

    except (CSVLoaderError, ExcelHandlerError) as e:
        raise click.ClickException(f"Availability import error: {e}") from e


def _import_requests(
    file_path: Path,
    csv_loader: CSVLoader,
    excel_loader: ExcelLoader,
    verbose: int,  # noqa: ARG001
) -> None:
    """Import requests from a file."""
    click.echo(f"Importing requests from: {file_path}")
    try:
        if file_path.suffix == ".xlsx":
            req_list = excel_loader.load_requests(file_path)
        else:
            req_list = csv_loader.load_requests(file_path)
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
        raise click.ClickException(f"Error reading schedule: {e}") from e

    if output_format == "json":
        # Just copy/format the JSON
        output.parent.mkdir(parents=True, exist_ok=True)
        with open(output, "w") as f:
            json.dump(schedule_data, f, indent=2)
        click.echo(f"Schedule exported to: {output}")

    elif output_format == "plotly":
        from shift_solver.io import PlotlyVisualizer

        schedule_obj = build_schedule_from_json(schedule_data)
        visualizer = PlotlyVisualizer()
        visualizer.export_all(schedule_obj, output)

        chart_count = len(list(output.glob("*.html"))) - 1  # Exclude index
        click.echo(f"Exported {chart_count} charts + index to: {output}/")

    elif output_format == "excel":
        # Build Schedule object using helper
        schedule_obj = build_schedule_from_json(schedule_data)

        exporter = ExcelExporter()
        exporter.export_schedule(
            schedule_obj,
            output,
            include_worker_view=include_worker_view,
        )
        click.echo(f"Schedule exported to: {output}")
