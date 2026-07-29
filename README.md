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

Each preset's shift type ids/categories match the corresponding
`config/examples/<industry>.yaml`, so the generated `workers.csv`/
`availability.csv`/`requests.csv` can be solved directly against that
config (e.g. via `--workers`/`--availability`/`--requests` below).
`shift_types.csv` in the output is informational only -- no loader reads
it back in; shift types always come from the YAML config.

### 2. Generate a Schedule

`--config`/`-c` is a *group-level* option, so it must come before the
subcommand name (`shift-solver -c <path> generate ...`, not
`shift-solver generate -c <path> ...`) -- `generate` has no `--config`
option of its own. It defaults to `config/config.yaml` even if omitted.

`generate` needs exactly one worker source: `--demo` (10 synthetic
workers, `W001`-`W010`) or `--workers <file.csv>` (real worker data,
optionally paired with `--availability`/`--requests` CSVs); passing both
is an error.

```bash
# Quick demo schedule (uses built-in demo workers; shift types still come
# from config/config.yaml, the group-level default)
uv run shift-solver generate \
  --start-date 2026-02-01 \
  --end-date 2026-02-28 \
  --output output/schedule.json \
  --demo

# With a custom config and real worker/availability data
uv run shift-solver -c config/examples/retail.yaml generate \
  --start-date 2026-02-01 \
  --end-date 2026-02-28 \
  --output output/schedule.json \
  --workers data/workers.csv \
  --availability data/availability.csv
```

Note: `schedule.period_type` in the config must be `"week"` --
`generate` currently only implements weekly period computation and
rejects any other value. See
[`docs/configuration.md`](docs/configuration.md) for what this means for
scheduling at day/month granularity.

### 3. Validate a Schedule

`validate` accepts `--config`/`-c` either as its own option (after
`validate`) or inherited from the group-level `-c` given before the
subcommand -- the subcommand-local value wins if both are given. Either
way it defaults to `config/config.yaml`.

```bash
# Basic validation -- run from the repo root, this still loads
# config/config.yaml for shift types: the group-level -c default
# ("config/config.yaml") applies even when no -c is given at all. Shift
# types are only inferred from the schedule JSON when no config file
# resolves to an existing path.
uv run shift-solver validate --schedule output/schedule.json

# Full validation with config and worker data (-c after the subcommand)
uv run shift-solver validate -c config/config.yaml \
  --schedule output/schedule.json \
  --workers data/workers.csv \
  --output report.json

# Equivalent, using the group-level -c before the subcommand
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

Use `--help` with any command for detailed options:
```bash
uv run shift-solver generate --help
```

## Configuration

See [`docs/configuration.md`](docs/configuration.md) for the full
reference: every constraint id (hard/soft, registry defaults, every
parameter's type/default/meaning), the sliding-window semantics, the
period-granular scheduling model and its limitations, request semantics,
and the objective/weighting model. The excerpt below is illustrative only
-- `config/config.yaml` itself has several more constraint blocks
(`worker_shift_limit`, `skills`, etc.) not shown here.

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
W001,Worker 1,full_time,,day
W002,Worker 2,full_time,night,
W003,Worker 3,part_time,,
```

### Availability CSV

```csv
worker_id,start_date,end_date,availability_type,shift_type_id
W001,2026-02-15,2026-02-20,unavailable,
W002,2026-02-01,2026-02-28,preferred,day
```

## Constraints

Full parameter reference: [`docs/configuration.md`](docs/configuration.md).

### Hard Constraints (always enforced when enabled; `is_hard` has no effect on these)
- **Coverage**: Exact required workers per shift type per period
- **Restrictions**: Workers cannot work shifts they're restricted from
- **Availability**: Workers cannot work when marked unavailable
- **Worker Shift Limit**: Caps simultaneous shift assignments per worker per period (default: 1, i.e. mutually exclusive shifts)
- **Skills**: Workers may only work shifts whose `required_attributes` they satisfy

### Soft Constraints (penalized in objective; promotable to hard via `is_hard: true`)
- **Fairness**: Distribute undesirable shifts evenly
- **Frequency**: Ensure workers get shifts at regular intervals (sliding window)
- **Requests**: Honor worker preferences (positive = at-least-once-in-range, negative = every period)
- **Sequence**: Avoid consecutive shifts of the same category
- **Max Absence**: Limit consecutive periods without shifts (sliding window)
- **Shift Frequency**: Per-worker "must work one of [...] every N periods" requirements
- **Shift Order Preference**: Encourage a preferred shift/category adjacent to a trigger
- **Workload**: Bound each worker's total shift count over the whole horizon

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
├── io/              # CSV/Excel import/export
├── cli/             # Click CLI commands
└── utils/           # Logging, exceptions, utilities
```

## License

GPL-3.0-or-later - see LICENSE file for details.
