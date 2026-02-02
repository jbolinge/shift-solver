---
id: scheduler-76
title: "Test Empty Frozenset CSV Parsing"
type: task
status: open
priority: 2
created: 2026-02-02T12:00:00Z
updated: 2026-02-02T12:00:00Z
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

