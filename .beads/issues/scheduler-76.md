---
id: scheduler-76
title: "Test Empty Frozenset CSV Parsing"
type: task
status: closed
priority: 2
created: 2026-02-02T12:00:00Z
updated: 2026-02-02T16:30:00Z
closed: 2026-02-02T16:30:00Z
labels: [testing, edge-case, io]
parent: scheduler-65
---

# Test Empty Frozenset CSV Parsing

## Problem

CSV parsing of `restricted_shifts` and `preferred_shifts`:

```python
split(",")  # on empty string -> [""]
frozenset([""])  # Bug: frozenset containing empty string
```

Instead of:
```python
frozenset()  # Correct: empty frozenset
```

## Test Cases

1. **Empty field**: `""` -> `frozenset()`
2. **Whitespace only**: `"   "` -> `frozenset()`
3. **Single value**: `"day"` -> `frozenset({"day"})`
4. **Multiple values**: `"day,night"` -> `frozenset({"day", "night"})`
5. **Trailing comma**: `"day,"` -> `frozenset({"day"})` (not `{"day", ""}`)
6. **Leading comma**: `",day"` -> `frozenset({"day"})`
7. **Multiple commas**: `"day,,night"` -> `frozenset({"day", "night"})`
8. **Whitespace around values**: `" day , night "` -> `frozenset({"day", "night"})`

## Expected Behavior

- Empty strings should result in empty frozensets
- Whitespace should be trimmed
- Empty elements from split should be filtered out

## Files to Modify

- `tests/test_io/test_csv_loader.py`
- Potentially `src/shift_solver/io/csv_loader.py` (if bug fix needed)

## Notes

### Resolution (2026-02-02)

**Finding:** The existing implementation was already correct. Both CSV and Excel loaders use:
```python
frozenset(s.strip() for s in value.split(",") if s.strip())
```

The `if s.strip()` filter properly handles all edge cases:
- Empty strings → filtered out
- Whitespace-only → filtered out
- Trailing/leading commas → empty elements filtered out

**Tests Added:** Created `tests/test_io/test_frozenset_parsing.py` with 32 tests:
- 12 CSV loader tests
- 10 Excel loader tests
- 10 parameterized consistency tests

All edge cases from the issue now have explicit test coverage to prevent regressions.
