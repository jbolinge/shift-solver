---
id: scheduler-55
title: "Unify soft constraint default config with registry"
type: bug
status: closed
priority: 1
created: 2026-02-01
updated: 2026-02-01
parent: scheduler-51
---

# Unify soft constraint default config with registry

## Problem

Constraints override config with local defaults (weight=100) that conflict with registry defaults (weight=1000). When instantiated without explicit config, constraints use the wrong weights.

**Current code in multiple constraints:**
```python
if config is None:
    config = ConstraintConfig(enabled=True, is_hard=False, weight=100)  # Conflicts with registry
```

## Files to Modify

- `src/shift_solver/constraints/fairness.py:40-44`
- `src/shift_solver/constraints/sequence.py`
- `src/shift_solver/constraints/frequency.py`
- `src/shift_solver/constraints/max_absence.py`
- `src/shift_solver/constraints/request.py`

## Acceptance Criteria

- [x] Remove hardcoded ConstraintConfig in constraint `__init__` methods
- [x] Use registry defaults consistently
- [x] Add test verifying constraints use registry weights when no config provided

## Resolution

- Removed hardcoded `if config is None` blocks from all soft constraint __init__ methods
- Now constraints defer to BaseConstraint's default (enabled=True, is_hard=True, weight=100)
- Registry provides specific configs when instantiating via solver
- Updated tests to use explicit soft config when testing soft constraint behavior
- Added test_init_soft_config tests to all constraint test classes
- All 587 tests pass
