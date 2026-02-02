---
id: scheduler-72
title: "Test Frequency/MaxAbsence Window Size Edge Cases"
type: task
status: closed
priority: 2
created: 2026-02-02T12:00:00Z
updated: 2026-02-02T12:00:00Z
labels: [testing, edge-case, constraints]
parent: scheduler-65
---

# Test Frequency/MaxAbsence Window Size Edge Cases

## Problem

Frequency and MaxAbsence constraints use sliding windows:

```python
window_size = max_periods_between + 1
if window_size > num_periods:
    return  # Exit silently if window larger than schedule
```

**Locations**:
- `src/shift_solver/constraints/frequency.py:70`
- `src/shift_solver/constraints/max_absence.py:70`

When window size exceeds num_periods, the constraint is silently skipped with no logging.

## Test Cases

1. **window_size == num_periods**: Exactly 1 window (boundary)
2. **window_size == num_periods + 1**: Silent skip (edge)
3. **window_size >> num_periods**: Large config, small schedule
4. **max_periods_between = 0**: window_size = 1 (each period independent)
5. **max_periods_between = num_periods - 1**: Maximum useful value
6. **Verify logging**: Confirm warning when constraint skipped

## Expected Behavior

- Constraints should log when configuration makes them ineffective
- Boundary conditions should be handled gracefully
- Configuration validation should warn about unusable settings

## Files to Modify

- `tests/test_constraints/test_frequency.py`
- `tests/test_constraints/test_max_absence.py`

## Notes

