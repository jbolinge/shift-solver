---
id: scheduler-57
title: "Make Fairness-ObjectiveBuilder coupling explicit"
type: task
status: open
deferred: true
priority: 1
created: 2026-02-01
updated: 2026-02-01
parent: scheduler-51
---

# Make Fairness-ObjectiveBuilder coupling explicit

## Problem

ObjectiveBuilder has hardcoded handling for fairness variable names (`"spread"`, `"max_undesirable"`, `"min_undesirable"`). Changes to FairnessConstraint break ObjectiveBuilder silently.

**Current code:**
```python
# objective_builder.py:77-94
if var_name in ("total", "spread", "max_undesirable", "min_undesirable"):
    if var_name == "spread":
        # Only handle spread
        continue
```

## Files to Modify

- `src/shift_solver/constraints/fairness.py:147-149`
- `src/shift_solver/constraints/base.py` - add variable type metadata
- `src/shift_solver/solver/objective_builder.py:77-94`

## Acceptance Criteria

- [ ] Add metadata indicating variable type (spread, count, etc.)
- [ ] ObjectiveBuilder uses metadata, not hardcoded names
- [ ] Add test for custom fairness variable naming
