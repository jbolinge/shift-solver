---
id: scheduler-95
title: "Integrate shift_frequency into solver context"
type: task
status: open
priority: 1
created: 2026-02-04
updated: 2026-02-04
parent: scheduler-91
depends-on: scheduler-94
---

# Integrate shift_frequency into solver context

Update solver to pass frequency requirements through the constraint context.

## Files to Modify

- `src/shift_solver/solver/shift_solver.py` - add shift_frequency_requirements to context
- `src/shift_solver/config/loader.py` - load requirements from config (if needed)

## Implementation

1. Load requirements from config in ShiftSolver
2. Add `shift_frequency_requirements` to constraint context dict
3. Wire through `_apply_constraints()` method

## Context Structure

```python
context = {
    "workers": workers,
    "shift_types": shift_types,
    "period_dates": period_dates,
    "shift_frequency_requirements": requirements,  # Add this
    # ... other context
}
```

## Acceptance Criteria

- [ ] Requirements accessible in constraint via `context["shift_frequency_requirements"]`
- [ ] Empty list if no requirements configured
- [ ] Integration test: requirements flow from config to constraint
