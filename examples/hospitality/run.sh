#!/bin/bash
# Hospitality example runner script
# Run from the project root: bash examples/hospitality/run.sh

set -e

EXAMPLE_DIR="examples/hospitality"
OUTPUT_DIR="$EXAMPLE_DIR/output"

echo "=== Hospitality (day-granular) Example ==="
echo ""

mkdir -p "$OUTPUT_DIR"

# Generate a 4-week schedule. No --end-date: the horizon comes from
# schedule.num_periods (28 day periods) in config.yaml.
echo "1. Generating 28-day schedule (horizon from schedule.num_periods)..."
uv run shift-solver -c "$EXAMPLE_DIR/config.yaml" generate \
  --start-date 2026-02-01 \
  --workers "$EXAMPLE_DIR/workers.csv" \
  --availability "$EXAMPLE_DIR/availability.csv" \
  --output "$OUTPUT_DIR/schedule.json" \
  --quick-solve \
  --explain

echo ""
echo "2. Validating the generated schedule..."
uv run shift-solver -c "$EXAMPLE_DIR/config.yaml" validate \
  --schedule "$OUTPUT_DIR/schedule.json" \
  --workers "$EXAMPLE_DIR/workers.csv" \
  --availability "$EXAMPLE_DIR/availability.csv"

echo ""
echo "3. Exporting to Excel..."
uv run shift-solver export \
  --schedule "$OUTPUT_DIR/schedule.json" \
  --config "$EXAMPLE_DIR/config.yaml" \
  --output "$OUTPUT_DIR/schedule.xlsx"

echo ""
echo "Done. Outputs in $OUTPUT_DIR/"
