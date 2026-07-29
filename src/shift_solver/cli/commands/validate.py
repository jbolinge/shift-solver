"""Validate command for checking schedule constraints."""

from __future__ import annotations

import json
from pathlib import Path

import click

from shift_solver.cli.helpers import (
    build_schedule_from_json,
    infer_shift_types,
    shift_type_from_config,
)
from shift_solver.config import ShiftSolverConfig
from shift_solver.io import CSVLoader
from shift_solver.models import ShiftType, Worker
from shift_solver.validation import ScheduleValidator, ValidationResult
from shift_solver.validation.schedule_validator.validator import (
    DEFAULT_MAX_SHIFTS_PER_PERIOD,
)


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

    # Fall back to the group-level -c/--config when --config isn't given to
    # this subcommand directly (same pattern as list-shifts).
    config_path = config or ctx.obj.get("config_path")
    config_explicit = config is not None or bool(ctx.obj.get("config_explicit", False))

    click.echo(f"Validating schedule: {schedule}")

    # Load the schedule JSON
    try:
        with open(schedule) as f:
            schedule_data = json.load(f)
    except Exception as e:
        raise click.ClickException(f"Error reading schedule: {e}") from e

    cfg = _load_config(config_path, config_explicit, verbose)

    # Load shift types from config or infer from schedule
    shift_types = _load_shift_types(cfg, schedule_data, verbose)

    # Load workers
    worker_list = _load_workers(workers, schedule_data, verbose)

    # Load availability and requests
    availabilities = _load_availability(availability, verbose)
    request_list = _load_requests(requests, verbose)

    max_shifts_per_period = _resolve_max_shifts_per_period(cfg)

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
        shift_types=shift_types,
        workers=worker_list,
        max_shifts_per_period=max_shifts_per_period,
    )
    result = validator.validate()

    # Output results
    _print_results(result, verbose)

    # Write report if output specified
    if output:
        _write_report(output, result)

    if not result.is_valid:
        raise SystemExit(1)


def _load_config(
    config_path: Path | None, config_explicit: bool, verbose: int
) -> ShiftSolverConfig | None:
    """Load and validate a config file, or None if no config file is present.

    ``config_explicit`` distinguishes "the user passed -c/--config" from
    "click applied the default path": an explicitly-given path that doesn't
    exist is an error (silently validating against registry defaults instead
    of the intended config produces confidently wrong violations), while an
    absent default just means no config.

    Raises:
        click.ClickException: If an explicitly-given path is missing, or the
            path exists but fails to load/validate.
    """
    if not (config_path and config_path.exists()):
        if config_path and config_explicit:
            raise click.ClickException(f"Configuration file not found: {config_path}")
        return None
    try:
        cfg = ShiftSolverConfig.load_from_yaml(config_path)
    except Exception as e:
        raise click.ClickException(f"Error loading config: {e}") from e
    if verbose:
        click.echo(f"Loaded config from {config_path}")
    return cfg


def _resolve_max_shifts_per_period(cfg: ShiftSolverConfig | None) -> int:
    """Resolve worker_shift_limit's max_shifts_per_period from config.

    Falls back to the same default ScheduleValidator/the constraint registry
    use (DEFAULT_MAX_SHIFTS_PER_PERIOD) when no config or override is given.

    When the config explicitly disables worker_shift_limit, this returns an
    effectively-unbounded limit (the number of configured shift types, i.e.
    more than any single period could ever assign to one worker) instead of
    silently applying the registry's default cap of 1. Otherwise a config
    that turns the constraint OFF would still get it enforced post-solve,
    making generate -> validate self-contradict.
    """
    if cfg is None:
        return DEFAULT_MAX_SHIFTS_PER_PERIOD
    if not cfg.is_constraint_enabled("worker_shift_limit"):
        return len(cfg.shift_types)
    constraint_config = cfg.get_constraint_config("worker_shift_limit")
    return int(
        constraint_config.parameters.get(
            "max_shifts_per_period", DEFAULT_MAX_SHIFTS_PER_PERIOD
        )
    )


def _load_shift_types(
    cfg: ShiftSolverConfig | None,
    schedule_data: dict,
    verbose: int,
) -> list[ShiftType]:
    """Load shift types from config or infer from schedule."""
    if cfg is not None:
        shift_types = [shift_type_from_config(st) for st in cfg.shift_types]
        if verbose:
            click.echo(f"Loaded {len(shift_types)} shift types from config")
        return shift_types
    else:
        shift_types = infer_shift_types(schedule_data)
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
