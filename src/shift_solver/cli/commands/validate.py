"""Validate command for checking schedule constraints."""

from __future__ import annotations

import json
from datetime import time as dt_time
from pathlib import Path

import click

from shift_solver.cli.helpers import build_schedule_from_json
from shift_solver.config import ShiftSolverConfig
from shift_solver.io import CSVLoader
from shift_solver.models import ShiftType, Worker
from shift_solver.validation import ScheduleValidator, ValidationResult


@click.command()
@click.option(
    "--schedule",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help="Schedule JSON file to validate",
)
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Configuration file with shift type definitions",
)
@click.option(
    "--workers",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Workers CSV file (for restriction validation)",
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
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    default=None,
    help="Output file for validation report (JSON)",
)
@click.pass_context
def validate(
    ctx: click.Context,
    schedule: Path,
    config: Path | None,
    workers: Path | None,
    availability: Path | None,
    requests: Path | None,
    output: Path | None,
) -> None:
    """Validate a generated schedule against constraints."""
    verbose = ctx.obj.get("verbose", 0)

    click.echo(f"Validating schedule: {schedule}")

    # Load the schedule JSON
    try:
        with open(schedule) as f:
            schedule_data = json.load(f)
    except Exception as e:
        raise click.ClickException(f"Error reading schedule: {e}") from e

    # Load shift types from config or infer from schedule
    shift_types = _load_shift_types(config, schedule_data, verbose)

    # Load workers
    worker_list = _load_workers(workers, schedule_data, verbose)

    # Load availability and requests
    availabilities = _load_availability(availability, verbose)
    request_list = _load_requests(requests, verbose)

    # Build Schedule object
    schedule_obj = build_schedule_from_json(
        schedule_data,
        workers=worker_list,
        shift_types=shift_types,
    )

    # Run validation
    validator = ScheduleValidator(
        schedule=schedule_obj,
        availabilities=availabilities,
        requests=request_list,
    )
    result = validator.validate()

    # Output results
    _print_results(result, verbose)

    # Write report if output specified
    if output:
        _write_report(output, result)

    if not result.is_valid:
        raise SystemExit(1)


def _load_shift_types(
    config: Path | None,
    schedule_data: dict,
    verbose: int,
) -> list[ShiftType]:
    """Load shift types from config or infer from schedule."""
    if config and config.exists():
        try:
            cfg = ShiftSolverConfig.load_from_yaml(config)
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
        # Infer shift types from schedule
        shift_type_ids: set[str] = set()
        for period in schedule_data.get("periods", []):
            for shift_list in period.get("assignments", {}).values():
                for a in shift_list:
                    shift_type_ids.add(a.get("shift_type_id"))

        shift_types = [
            ShiftType(
                id=stid,
                name=stid,
                category="unknown",
                start_time=dt_time(0, 0),
                end_time=dt_time(8, 0),
                duration_hours=8.0,
                workers_required=1,
            )
            for stid in sorted(shift_type_ids)
        ]
        if verbose:
            click.echo(f"Inferred {len(shift_types)} shift types from schedule")
        return shift_types


def _load_workers(
    workers_path: Path | None,
    schedule_data: dict,
    verbose: int,
) -> list[Worker]:
    """Load workers from file or infer from schedule."""
    if workers_path:
        try:
            csv_loader = CSVLoader()
            worker_list = csv_loader.load_workers(workers_path)
            if verbose:
                click.echo(f"Loaded {len(worker_list)} workers")
            return worker_list
        except Exception as e:
            raise click.ClickException(f"Error loading workers: {e}") from e
    else:
        # Infer workers from schedule
        worker_ids: set[str] = set()
        for period in schedule_data.get("periods", []):
            worker_ids.update(period.get("assignments", {}).keys())

        worker_list = [Worker(id=wid, name=wid) for wid in sorted(worker_ids)]
        if verbose:
            click.echo(f"Inferred {len(worker_list)} workers from schedule")
        return worker_list


def _load_availability(availability_path: Path | None, verbose: int) -> list:
    """Load availability from file."""
    if not availability_path:
        return []

    try:
        csv_loader = CSVLoader()
        availabilities = csv_loader.load_availability(availability_path)
        if verbose:
            click.echo(f"Loaded {len(availabilities)} availability records")
        return availabilities
    except Exception as e:
        raise click.ClickException(f"Error loading availability: {e}") from e


def _load_requests(requests_path: Path | None, verbose: int) -> list:
    """Load requests from file."""
    if not requests_path:
        return []

    try:
        csv_loader = CSVLoader()
        request_list = csv_loader.load_requests(requests_path)
        if verbose:
            click.echo(f"Loaded {len(request_list)} requests")
        return request_list
    except Exception as e:
        raise click.ClickException(f"Error loading requests: {e}") from e


def _print_results(result: ValidationResult, verbose: int) -> None:
    """Print validation results to console."""
    if result.is_valid:
        click.echo(click.style("Validation PASSED", fg="green", bold=True))
    else:
        click.echo(click.style("Validation FAILED", fg="red", bold=True))
        click.echo(f"\n{len(result.violations)} violations found:")
        for v in result.violations:
            click.echo(f"  - [{v['type']}] {v['message']}")

    if result.warnings:
        click.echo(f"\n{len(result.warnings)} warnings:")
        for w in result.warnings:
            click.echo(f"  - [{w['type']}] {w['message']}")

    # Show statistics
    if verbose or not result.is_valid:
        click.echo("\nStatistics:")
        click.echo(
            f"  Total assignments: {result.statistics.get('total_assignments', 0)}"
        )

        if "fairness" in result.statistics:
            fairness = result.statistics["fairness"]
            click.echo(
                f"  Avg assignments/worker: {fairness.get('average_assignments', 0):.1f}"
            )
            click.echo(f"  Std deviation: {fairness.get('std_deviation', 0):.2f}")

        if "request_fulfillment" in result.statistics:
            req = result.statistics["request_fulfillment"]
            click.echo(f"  Request fulfillment: {req.get('rate', 0) * 100:.1f}%")


def _write_report(output: Path, result: ValidationResult) -> None:
    """Write validation report to JSON file."""
    report = {
        "is_valid": result.is_valid,
        "violations": result.violations,
        "warnings": result.warnings,
        "statistics": result.statistics,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w") as f:
        json.dump(report, f, indent=2, default=str)
    click.echo(f"\nValidation report written to: {output}")
