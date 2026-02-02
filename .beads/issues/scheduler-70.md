---
id: scheduler-70
title: "Test Context Dictionary Type Safety"
type: task
status: closed
priority: 2
created: 2026-02-02T12:00:00Z
updated: 2026-02-02T15:00:00Z
labels: [testing, api-mismatch, solver]
parent: scheduler-65
---

# Test Context Dictionary Type Safety

## Problem

The context dictionary passed to constraint `apply()` methods is `Dict[str, Any]`:

```python
context = {
    "workers": list[Worker],
    "shift_types": list[ShiftType],
    "num_periods": int,
    "availabilities": list[Availability],
    "requests": list[SchedulingRequest],
    "period_dates": list[tuple[date, date]],
}
```

Constraints access these with direct key lookups like `context["shift_types"]`. A typo (e.g., `context["shift_type"]`) fails at apply time, not registration time.

## Test Cases

1. **Missing required key**: Verify clear error when "workers" missing
2. **Typo in key name**: Verify error message indicates the bad key
3. **Wrong type in context**: Verify behavior when string passed instead of list
4. **Empty context**: Verify all required keys are validated
5. **Extra keys**: Verify extra keys don't cause issues
6. **None values**: Verify behavior when optional keys are None vs missing

## Expected Behavior

- Clear, actionable error messages for context issues
- Validation should happen early (ideally at registration)
- Type mismatches should be caught

## Files to Modify

- `tests/test_constraints/test_constraint_context.py` (new file)
- Potentially `src/shift_solver/constraints/base.py` (if validation added)

## Notes

