---
id: scheduler-61
title: "Replace assertions with proper exception handling"
type: task
status: open
priority: 2
created: 2026-02-01
updated: 2026-02-01
parent: scheduler-51
---

# Replace assertions with proper exception handling

## Problem

Uses `assert` for validation which can be disabled with Python `-O` flag, causing silent failures in production.

**Current code:**
```python
# shift_solver.py:168-222
assert self._model is not None
assert self._variables is not None
```

## Files to Modify

- `src/shift_solver/solver/shift_solver.py:168-222`

## Acceptance Criteria

- [ ] Replace `assert` with `if not x: raise RuntimeError(...)`
- [ ] Add descriptive error messages
- [ ] Add test that errors are raised correctly
