# Simple Example

A minimal 5-worker example to demonstrate basic shift-solver functionality.

## Files

- `config.yaml` - Configuration with 2 shift types
- `workers.csv` - 5 workers with no restrictions
- `run.sh` - Script to generate and validate a schedule

## Quick Start

```bash
# From the project root directory

# Generate a 2-week schedule
uv run shift-solver -c examples/simple/config.yaml generate \
  --start-date 2026-02-01 \
  --end-date 2026-02-14 \
  --output examples/simple/schedule.json \
  --demo

# Validate the schedule
uv run shift-solver -c examples/simple/config.yaml validate \
  --schedule examples/simple/schedule.json

# Export to Excel
uv run shift-solver export \
  --schedule examples/simple/schedule.json \
  --output examples/simple/schedule.xlsx
```

## Configuration

This example uses:
- 2 shift types: Day (requires 2 workers) and Night (requires 1 worker)
- 5 workers with no restrictions
- Basic fairness constraint to distribute night shifts evenly

## Expected Output

The solver should find an optimal solution quickly (under 10 seconds) that:
- Covers all shifts
- Distributes night shifts fairly among workers
