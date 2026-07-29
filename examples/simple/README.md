# Simple Example

A minimal 5-worker example to demonstrate basic shift-solver functionality.

## Files

- `config.yaml` - Configuration with 2 shift types
- `workers.csv` - 5 workers with no restrictions
- `run.sh` - Script to generate and validate a schedule

## Quick Start

```bash
# From the project root directory

# Generate a 2-week schedule from the real worker roster
uv run shift-solver -c examples/simple/config.yaml generate \
  --start-date 2026-02-01 \
  --end-date 2026-02-14 \
  --output examples/simple/output/schedule.json \
  --workers examples/simple/workers.csv \
  --quick-solve

# Validate the schedule against the same roster
uv run shift-solver -c examples/simple/config.yaml validate \
  --schedule examples/simple/output/schedule.json \
  --workers examples/simple/workers.csv

# Export to Excel
uv run shift-solver export \
  --schedule examples/simple/output/schedule.json \
  --config examples/simple/config.yaml \
  --output examples/simple/output/schedule.xlsx
```

Or simply run `bash examples/simple/run.sh` to do all three steps at once.

## Configuration

This example uses:
- 2 shift types: Day (requires 2 workers) and Night (requires 1 worker)
- 5 workers with no restrictions
- Basic fairness constraint to distribute night shifts evenly
- `worker_shift_limit` (max 1 shift per worker per period, the default)

## Expected Output

The solver should find an optimal solution quickly (under 10 seconds) that:
- Covers all shifts
- Distributes night shifts fairly among workers

`validate --workers examples/simple/workers.csv` passes cleanly: without
`--workers`, validate would only know about the workers actually present in
the generated schedule, which can never catch a mismatch against the real
roster (e.g. a worker in the schedule who isn't in `workers.csv`, or vice
versa).
