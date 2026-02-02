---
id: scheduler-75
title: "Test Priority Field Coercion Consistency"
type: task
status: closed
priority: 2
created: 2026-02-02T12:00:00Z
updated: 2026-02-02T16:00:00Z
closed: 2026-02-02T16:00:00Z
labels: [testing, edge-case, io]
parent: scheduler-65
---

# Test Priority Field Coercion Consistency

## Problem

Priority field handling differs between CSV and Excel loaders:

**Excel loader**:
```python
int(priority_val) if priority_val else 1  # No error handling
```

**CSV loader**:
```python
int(priority_str)  # With try/except
```

This inconsistency could cause different behavior for the same data.

## Test Cases

1. **Valid integer**: "2" -> 2 (both formats)
2. **Float string**: "2.5" -> ? (Excel truncates, CSV raises?)
3. **Empty string**: "" -> 1 (default)
4. **None/null**: None -> 1 (default)
5. **Non-numeric**: "high" -> error
6. **Negative**: "-1" -> error?
7. **Zero**: "0" -> 0 (valid priority?)
8. **Very large**: "999999" -> valid?
9. **Whitespace**: " 2 " -> 2 (trimmed?)

## Expected Behavior

- Consistent behavior between CSV and Excel loaders
- Clear error messages for invalid priorities
- Validation of priority range (should be >= 1)

## Files to Modify

- `tests/test_io/test_csv_loader.py`
- `tests/test_io/test_excel_loader.py`
- `tests/test_io/test_priority_consistency.py` (new file)

## Notes

### Resolution (2026-02-02)

**Issues Found:**
- Excel loader had no error handling for `int()` conversion
- Excel loader didn't validate priority > 0
- Excel loader treated 0 as falsy (returned default 1 instead of error)
- Float values were silently truncated in Excel loader

**Changes Made:**
1. Added `_parse_priority()` method to Excel loader (`src/shift_solver/io/excel_handler/loader.py`)
2. Created comprehensive test suite (`tests/test_io/test_priority_consistency.py`) with 22 tests:
   - 8 CSV loader tests
   - 9 Excel loader tests
   - 5 cross-loader consistency tests

**Behavior Now Consistent:**
| Scenario | Result |
|----------|--------|
| Valid integer (2) | Accepted |
| Empty/""/None | Default to 1 |
| Float (2.5) | Error |
| Non-numeric ("high") | Error |
| Zero (0) | Error |
| Negative (-1) | Error |
| Large (999999) | Accepted |
