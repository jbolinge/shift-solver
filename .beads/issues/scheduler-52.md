---
id: scheduler-52
title: "Add type coercion validation in IO layer"
type: bug
status: closed
priority: 0
created: 2026-02-01
updated: 2026-02-01
parent: scheduler-51
---

# Add type coercion validation in IO layer

## Problem

CSV/Excel loaders use `int()` without try-except, causing unhandled ValueError/IndexError on malformed input.

**Current code:**
```python
# csv_loader.py:245
priority = int(priority_str)  # ValueError if "high" or "1.5"

# schema.py:55
return time(int(parts[0]), int(parts[1]))  # IndexError if "14" instead of "14:30"
```

## Files to Modify

- `src/shift_solver/io/csv_loader.py:245` - priority parsing
- `src/shift_solver/config/schema.py:55` - time parsing

## Acceptance Criteria

- [x] Wrap `int(priority_str)` in try-except with descriptive error
- [x] Validate time string format before parsing (must contain ":")
- [x] Add tests for malformed priority values ("high", "1.5", "")
- [x] Add tests for malformed time values ("14", "25:00", "abc")

## Resolution

- Added `_parse_priority()` method to CSVLoader that validates priority is a positive integer
- Updated `parse_time()` validator in ShiftTypeConfig to check for colon separator, valid hour (0-23) and minute (0-59) ranges
- Added test class `TestCSVLoaderTypeCoercion` with 4 tests for priority validation
- Added test class `TestTimeParsingValidation` with 5 tests for time parsing validation
