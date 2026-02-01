---
id: scheduler-58
title: "Unify CSV and Excel error handling"
type: task
status: closed
priority: 1
created: 2026-02-01
updated: 2026-02-01
parent: scheduler-51
---

# Unify CSV and Excel error handling

## Problem

CSVLoader wraps errors with line numbers; ExcelLoader doesn't. Users get different debugging experience depending on file format.

**CSVLoader:**
```python
except Exception as e:
    raise CSVLoaderError(f"Error on line {line_num}: {e}") from e
```

**ExcelLoader:**
```python
worker = self._parse_worker_row(row, line_num)  # No error wrapping
```

## Files to Modify

- `src/shift_solver/io/excel_handler/loader.py:44-46`

## Acceptance Criteria

- [x] ExcelLoader wraps row parsing errors with row numbers
- [x] Both loaders raise similar error types with consistent info
- [x] Add test for Excel row parsing error message format

## Resolution

Added try/except wrappers to ExcelLoader's load methods (load_workers,
load_availability, load_requests) matching CSVLoader's pattern. Also fixed
None value handling for empty Excel cells using `row.get("field") or ""`
pattern instead of `row.get("field", "")`.

Added 4 tests in `TestExcelLoaderErrorHandling` class.
