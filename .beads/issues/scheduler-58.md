---
id: scheduler-58
title: "Unify CSV and Excel error handling"
type: task
status: open
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

- [ ] ExcelLoader wraps row parsing errors with row numbers
- [ ] Both loaders raise similar error types with consistent info
- [ ] Add test for Excel row parsing error message format
