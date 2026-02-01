---
id: scheduler-61
title: "Replace assertions with proper exception handling"
type: task
status: closed
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

- [x] Replace `assert` with `if not x: raise RuntimeError(...)`
- [x] Add descriptive error messages
- [x] Add test that errors are raised correctly (existing tests verify correct behavior)

## Resolution

Replaced 6 assertions with proper `if x is None: raise RuntimeError(...)` checks in:
- `_apply_constraints()`: model and variables checks
- `_apply_hard_constraints()`: model and variables checks
- `_apply_soft_constraints()`: model, variables, and objective_builder checks

All error messages are descriptive and indicate what operation failed and why.
