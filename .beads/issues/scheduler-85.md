---
id: scheduler-85
title: "Test Full I/O Pipeline Round-Trip"
type: task
status: closed
priority: 2
created: 2026-02-02T12:00:00Z
updated: 2026-02-03T12:00:00Z
labels: [testing, integration, io]
parent: scheduler-65
---

# Test Full I/O Pipeline Round-Trip

## Problem

The I/O pipeline needs comprehensive testing:
```
CSV/Excel Import -> Domain Models -> Solve -> Export -> Re-Import
```

Need to verify data integrity throughout the pipeline.

## Test Cases

### CSV Pipeline
1. **Workers CSV round-trip**: Export -> Import -> Compare
2. **Availability CSV round-trip**: Same structure after round-trip
3. **Requests CSV round-trip**: Priority and dates preserved

### Excel Pipeline
4. **Multi-sheet import**: Workers, Availability, Requests from one file
5. **Export structure**: Verify all sheets created correctly
6. **Re-import exported schedule**: Can we reload an exported schedule?

### Cross-Format
7. **CSV to Excel**: Import CSV, export Excel, verify
8. **Excel to CSV**: Import Excel, export CSV (if supported)
9. **JSON intermediate**: Export to JSON, import from JSON

### Edge Cases
10. **Large file handling**: 1000+ workers/rows
11. **Special characters**: Unicode in names, shift IDs
12. **Empty sections**: No availability, no requests

## Expected Behavior

- Data should be identical after round-trip
- No loss of precision in dates/times
- Clear error messages for format issues

## Files to Modify

- `tests/test_integration/test_io_pipeline.py`
- `tests/test_io/test_roundtrip.py` (new file)

## Notes

