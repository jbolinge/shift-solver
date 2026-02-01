---
id: scheduler-56
title: "Respect explicit constraint_configs for RequestConstraint"
type: bug
status: open
priority: 1
created: 2026-02-01
updated: 2026-02-01
parent: scheduler-51
---

# Respect explicit constraint_configs for RequestConstraint

## Problem

Solver auto-enables RequestConstraint if requests exist, ignoring user's explicit `enabled=False` config.

**Current code:**
```python
# shift_solver.py:227-233
if constraint_id == "request" and not default_config.enabled:
    default_config = ConstraintConfig(
        enabled=bool(self.requests),  # Ignores user config!
        is_hard=False,
        weight=default_config.weight,
    )
```

## Files to Modify

- `src/shift_solver/solver/shift_solver.py:227-233`

## Acceptance Criteria

- [ ] Only auto-enable if user didn't provide explicit config
- [ ] Add test: requests exist + explicit enabled=False → constraint disabled
