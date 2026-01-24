# Retail Store Example

A retail store schedule with morning, afternoon, and weekend coverage.

## Scenario

- Small retail store with 6 employees
- Open 7 days a week
- Morning and afternoon shifts on weekdays
- Full-day weekend shifts with higher staffing
- Mix of full-time and part-time workers

## Files

- `config.yaml` - Retail-specific configuration
- `workers.csv` - 6 employees with different types
- `availability.csv` - Time-off requests
- `run.sh` - Script to generate and validate a schedule

## Quick Start

```bash
# From the project root directory

# Generate a 4-week schedule
uv run shift-solver -c examples/retail/config.yaml generate \
  --start-date 2026-02-01 \
  --end-date 2026-02-28 \
  --output examples/retail/schedule.json \
  --demo

# Validate the schedule
uv run shift-solver -c examples/retail/config.yaml validate \
  --schedule examples/retail/schedule.json \
  --workers examples/retail/workers.csv
```

## Key Features Demonstrated

1. **Part-time and full-time workers** with different availability
2. **Weekend coverage** with higher staffing requirements
3. **Fair distribution** of weekend shifts
4. **Simple constraint setup** appropriate for smaller teams
