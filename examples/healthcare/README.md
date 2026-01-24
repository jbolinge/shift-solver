# Healthcare Example

A hospital/clinic rotation schedule with 24/7 coverage requirements.

## Scenario

- 8 nurses/staff members
- 24/7 coverage with day, evening, and night shifts
- Weekend shifts with 12-hour coverage
- Fair distribution of undesirable shifts (nights, weekends)
- Some staff have restrictions (e.g., cannot work nights)

## Files

- `config.yaml` - Healthcare-specific configuration
- `workers.csv` - 8 staff members with various restrictions
- `availability.csv` - PTO and unavailability records
- `requests.csv` - Shift preferences
- `run.sh` - Script to generate and validate a schedule

## Quick Start

```bash
# From the project root directory

# Generate a 4-week schedule
uv run shift-solver -c examples/healthcare/config.yaml generate \
  --start-date 2026-02-01 \
  --end-date 2026-02-28 \
  --output examples/healthcare/schedule.json \
  --demo

# Validate with full data
uv run shift-solver -c examples/healthcare/config.yaml validate \
  --schedule examples/healthcare/schedule.json \
  --workers examples/healthcare/workers.csv \
  --availability examples/healthcare/availability.csv
```

## Key Features Demonstrated

1. **Multiple shift types** with different staffing requirements
2. **Worker restrictions** (some staff cannot work nights)
3. **Availability management** (PTO, unavailable dates)
4. **Fairness constraints** to distribute nights/weekends evenly
5. **Sequence constraints** to avoid back-to-back night shifts
