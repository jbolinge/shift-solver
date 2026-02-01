---
id: scheduler-55
title: "Unify soft constraint default config with registry"
type: bug
status: open
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

- [ ] Remove hardcoded ConstraintConfig in constraint `__init__` methods
- [ ] Use registry defaults consistently
- [ ] Add test verifying constraints use registry weights when no config provided
