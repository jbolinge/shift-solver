"""Generate-samples command for creating sample data files."""

from datetime import date, timedelta
from pathlib import Path

import click

from shift_solver.io import SampleGenerator


@click.command("generate-samples")
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
    start_date, end_date = _calculate_date_range(months)

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


def _calculate_date_range(months: int) -> tuple[date, date]:
    """Calculate start and end dates for the given number of months."""
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

    return start_date, end_date
