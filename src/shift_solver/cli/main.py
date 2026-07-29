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
    "-v",
    "--verbose",
    count=True,
    help="Increase verbosity (-v, -vv, -vvv)",
)
@click.pass_context
def cli(ctx: click.Context, config: Path, verbose: int) -> None:
    """shift-solver: General-purpose shift scheduling optimization."""
    ctx.ensure_object(dict)
    ctx.obj["config_path"] = config
    # Distinguish "user explicitly passed -c/--config" from "click applied
    # its 'config/config.yaml' default because none was given" -- callers
    # need this to tell "no config specified" (fall back to demo data) apart
    # from "a config WAS specified but that path doesn't exist" (an error).
    ctx.obj["config_explicit"] = (
        ctx.get_parameter_source("config") != click.core.ParameterSource.DEFAULT
    )
    ctx.obj["verbose"] = verbose


@cli.command()
def version() -> None:
    """Show version information."""
    click.echo(f"shift-solver v{__version__}")


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
    # list-shifts' own --config already declares exists=True, so if `config`
    # is set here it necessarily exists (click would have rejected it
    # before this function ran) and was explicitly passed by the user.
    # Otherwise we fall back to the group's `-c`/default, which uses
    # exists=False and therefore needs its own explicit-vs-default check.
    if config is not None:
        config_path: Path | None = config
        config_explicit = True
    else:
        config_path = ctx.obj.get("config_path")
        config_explicit = bool(ctx.obj.get("config_explicit", False))

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
    elif config_path and config_explicit:
        # A config path WAS specified (not just click's default) but it
        # doesn't exist -- this is a user error, not "no config given".
        raise click.ClickException(f"Configuration file not found: {config_path}")
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
