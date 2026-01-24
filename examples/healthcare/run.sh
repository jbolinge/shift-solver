#!/bin/bash
# Healthcare example runner script
# Run from the project root: bash examples/healthcare/run.sh

set -e

EXAMPLE_DIR="examples/healthcare"
OUTPUT_DIR="$EXAMPLE_DIR/output"

echo "=== Healthcare Rotation Example ==="
echo ""

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Generate schedule
echo "1. Generating 4-week schedule..."
uv run shift-solver -c "$EXAMPLE_DIR/config.yaml" generate \
  --start-date 2026-02-01 \
  --end-date 2026-02-28 \
  --output "$OUTPUT_DIR/schedule.json" \
  --demo

echo ""

# Validate schedule
echo "2. Validating schedule..."
uv run shift-solver -c "$EXAMPLE_DIR/config.yaml" -v validate \
  --schedule "$OUTPUT_DIR/schedule.json" \
  --workers "$EXAMPLE_DIR/workers.csv" \
  --availability "$EXAMPLE_DIR/availability.csv" \
  --requests "$EXAMPLE_DIR/requests.csv" \
  --output "$OUTPUT_DIR/validation_report.json"

echo ""

# Export to Excel
echo "3. Exporting to Excel..."
uv run shift-solver export \
  --schedule "$OUTPUT_DIR/schedule.json" \
  --output "$OUTPUT_DIR/schedule.xlsx"

echo ""
echo "=== Done! ==="
echo "Output files in: $OUTPUT_DIR/"
echo ""
echo "Check validation_report.json for detailed statistics."
