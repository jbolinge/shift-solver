#!/bin/bash
# Simple example runner script
# Run from the project root: bash examples/simple/run.sh

set -e

EXAMPLE_DIR="examples/simple"
OUTPUT_DIR="$EXAMPLE_DIR/output"

echo "=== Simple Example ==="
echo ""

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Generate schedule
echo "1. Generating 2-week schedule..."
uv run shift-solver -c "$EXAMPLE_DIR/config.yaml" generate \
  --start-date 2026-02-01 \
  --end-date 2026-02-14 \
  --output "$OUTPUT_DIR/schedule.json" \
  --demo \
  --quick-solve

echo ""

# Validate schedule
echo "2. Validating schedule..."
uv run shift-solver -c "$EXAMPLE_DIR/config.yaml" -v validate \
  --schedule "$OUTPUT_DIR/schedule.json"

echo ""

# Export to Excel
echo "3. Exporting to Excel..."
uv run shift-solver export \
  --schedule "$OUTPUT_DIR/schedule.json" \
  --output "$OUTPUT_DIR/schedule.xlsx"

echo ""
echo "=== Done! ==="
echo "Output files in: $OUTPUT_DIR/"
