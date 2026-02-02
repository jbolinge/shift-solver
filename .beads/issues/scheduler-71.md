---
id: scheduler-71
title: "Test Single Worker Schedule Edge Cases"
type: task
status: open
priority: 2
created: 2026-02-02T12:00:00Z
updated: 2026-02-02T12:00:00Z
labels: [testing, edge-case, constraints]
parent: scheduler-65
---

# Test Single Worker Schedule Edge Cases

## Problem

The fairness constraint exits early when there are fewer than 2 workers:

```python
if len(worker_totals) < 2:
    return  # Early exit, no fairness constraints added
```

**Location**: `src/shift_solver/constraints/fairness.py`

Other constraints may behave unexpectedly with single workers.

## Test Cases

1. **1 worker, 1 shift type, 1 period**: Minimal feasible schedule
2. **1 worker, multiple shift types**: Can they cover all?
3. **1 worker with restriction**: Worker restricted from required shift
4. **1 worker, undesirable shifts**: No fairness to balance against
5. **1 worker, coverage > 1**: Infeasible - verify error handling
6. **0 workers**: Edge case - should fail gracefully

## Expected Behavior

- Single worker schedules should solve when feasible
- Clear error when infeasible (coverage requires more workers)
- Fairness constraint should log that it's not applied

## Files to Modify

- `tests/test_e2e/test_single_worker_scenarios.py` (new file)

## Notes

