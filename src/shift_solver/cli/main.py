"""Command-line interface for shift-solver."""

from pathlib import Path

import click

from shift_solver import __version__
from shift_solver.cli.commands import (
    export_schedule,
    generate,
    generate_samples,
    import_data,
    validate,
)
from shift_solver.config import ShiftSolverConfig


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
        click.echo("Configuration is valid!")
        click.echo(f"  Shift types: {len(cfg.shift_types)}")
        click.echo(f"  Constraints configured: {len(cfg.constraints)}")
        click.echo(f"  Solver time limit: {cfg.solver.max_time_seconds}s")
    except FileNotFoundError as e:
        raise click.ClickException(f"Configuration file not found: {config}") from e
    except Exception as e:
        raise click.ClickException(f"Invalid configuration: {e}") from e


@cli.command("list-workers")
@click.pass_context
def list_workers(_ctx: click.Context) -> None:
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
            raise click.ClickException(f"Error loading config: {e}") from e
    else:
        click.echo("No configuration file found. Specify with --config.")


# Register commands from command modules
cli.add_command(generate)
cli.add_command(generate_samples)
cli.add_command(import_data)
cli.add_command(export_schedule)
cli.add_command(validate)


if __name__ == "__main__":
    cli()
