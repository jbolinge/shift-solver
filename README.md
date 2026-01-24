# shift-solver

General-purpose shift scheduling optimization using constraint programming.

## Features

- **Configurable**: Workers, shift types, and constraints defined in YAML/CSV/Excel
- **Constraint library**: Coverage, fairness, restrictions, availability, requests, and more
- **Flexible periods**: Schedule by day, week, or month
- **Multiple formats**: Import/export CSV and Excel
- **Validation**: Pre-solve feasibility checks and post-solve schedule validation
- **CLI interface**: Full-featured command-line tool

## Installation

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
# Clone the repository
git clone https://github.com/jbolinge/shift-solver.git
cd shift-solver

# Install dependencies
uv sync

# Verify installation
uv run shift-solver version
```

## Quick Start

### 1. Generate Sample Data

```bash
# Generate retail industry sample data
uv run shift-solver generate-samples \
  --industry retail \
  --num-workers 10 \
  --months 1 \
  --output-dir data/samples

# Or healthcare/warehouse presets
uv run shift-solver generate-samples --industry healthcare
uv run shift-solver generate-samples --industry warehouse
```

### 2. Generate a Schedule

```bash
# Quick demo schedule (uses built-in demo data)
uv run shift-solver generate \
  --start-date 2026-02-01 \
  --end-date 2026-02-28 \
  --output output/schedule.json \
  --demo

# With custom config
uv run shift-solver -c config/examples/retail.yaml generate \
  --start-date 2026-02-01 \
  --end-date 2026-02-28 \
  --output output/schedule.json \
  --demo
```

### 3. Validate a Schedule

```bash
# Basic validation
uv run shift-solver validate --schedule output/schedule.json

# Full validation with config and worker data
uv run shift-solver -c config/config.yaml validate \
  --schedule output/schedule.json \
  --workers data/workers.csv \
  --output report.json
```

### 4. Export to Excel

```bash
uv run shift-solver export \
  --schedule output/schedule.json \
  --output output/schedule.xlsx \
  --format excel
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `version` | Show version information |
| `generate` | Generate an optimized schedule |
| `validate` | Validate a schedule against constraints |
| `generate-samples` | Generate sample input files |
| `import-data` | Import worker/availability data |
| `export` | Export schedule to Excel/JSON |
| `check-config` | Validate a configuration file |
| `list-shifts` | List shift types from config |
| `init-db` | Initialize the database |

Use `--help` with any command for detailed options:
```bash
uv run shift-solver generate --help
```

## Configuration

### Main Config (`config/config.yaml`)

```yaml
# Solver settings
solver:
  max_time_seconds: 300
  num_workers: 8

# Shift types
shift_types:
  - id: "day"
    name: "Day Shift"
    category: "day"
    start_time: "07:00"
    end_time: "15:00"
    duration_hours: 8.0
    workers_required: 2

  - id: "night"
    name: "Night Shift"
    category: "night"
    start_time: "23:00"
    end_time: "07:00"
    duration_hours: 8.0
    is_undesirable: true
    workers_required: 1

# Constraints
constraints:
  coverage:
    enabled: true
    is_hard: true

  fairness:
    enabled: true
    is_hard: false
    weight: 1000
```

### Workers CSV

```csv
id,name,worker_type,restricted_shifts,preferred_shifts
W001,Alice Smith,full_time,,day
W002,Bob Jones,full_time,night,
W003,Carol White,part_time,,
```

### Availability CSV

```csv
worker_id,start_date,end_date,availability_type,shift_type_id
W001,2026-02-15,2026-02-20,unavailable,
W002,2026-02-01,2026-02-28,preferred,day
```

## Constraints

### Hard Constraints (must satisfy)
- **Coverage**: Required workers per shift type per period
- **Restrictions**: Workers cannot work shifts they're restricted from
- **Availability**: Workers cannot work when marked unavailable

### Soft Constraints (penalized in objective)
- **Fairness**: Distribute undesirable shifts evenly
- **Frequency**: Ensure workers get shifts at regular intervals
- **Requests**: Honor worker preferences (positive/negative)
- **Sequence**: Avoid consecutive shifts of certain types
- **Max Absence**: Limit consecutive periods without shifts

## Examples

See `examples/` directory for complete working examples:

- `examples/simple/` - Basic 5-worker setup
- `examples/retail/` - Retail store coverage
- `examples/healthcare/` - Hospital rotation schedule

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

## Architecture

```
src/shift_solver/
├── models/          # Core domain models (Worker, ShiftType, Schedule)
├── constraints/     # Constraint library (coverage, fairness, etc.)
├── solver/          # OR-Tools CP-SAT integration
├── validation/      # Pre/post-solve validation
├── db/              # SQLite persistence
├── io/              # CSV/Excel import/export
├── cli/             # Click CLI commands
└── utils/           # Logging, exceptions, utilities
```

## License

GPL-3.0-or-later - see LICENSE file for details.
