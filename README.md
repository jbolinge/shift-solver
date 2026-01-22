# shift-solver

General-purpose shift scheduling optimization using constraint programming.

## Features

- **Configurable**: Workers, shift types, and constraints defined in YAML/CSV/Excel
- **Constraint library**: Coverage, fairness, restrictions, availability, and more
- **Flexible periods**: Schedule by day, week, or month
- **Multiple formats**: Import/export CSV and Excel
- **CLI interface**: Command-line tool for all operations

## Installation

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
# Clone the repository
git clone https://github.com/jbolinge/shift-solver.git
cd shift-solver

# Install dependencies
uv sync

# Verify installation
uv run shift-solver --version
```

## Quick Start

```bash
# Initialize database
uv run shift-solver init-db

# Import sample data
uv run shift-solver generate-samples --industry retail

# Generate a schedule
uv run shift-solver generate \
  --start-date 2026-01-01 \
  --end-date 2026-03-31 \
  --output schedule.xlsx

# Validate a schedule
uv run shift-solver validate --schedule schedule.xlsx
```

## Configuration

Edit `config/config.yaml` to customize:

- Solver settings (time limit, threads)
- Constraint weights and parameters
- Shift type definitions

See `config/examples/` for industry-specific configurations.

## Development

```bash
# Install with dev dependencies
uv sync --all-groups

# Run tests
uv run pytest

# Run with coverage
uv run pytest --cov=src/shift_solver

# Type checking
uv run mypy src/

# Linting
uv run ruff check src/
```

## License

MIT License - see LICENSE file for details.
