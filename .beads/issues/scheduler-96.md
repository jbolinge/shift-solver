---
id: scheduler-96
title: "Pre-solve feasibility validation for shift frequency"
type: task
status: open
priority: 1
created: 2026-02-04
updated: 2026-02-04
parent: scheduler-91
depends-on: scheduler-92
---

# Pre-solve feasibility validation for shift frequency

Add validation to `FeasibilityChecker` to detect infeasible shift frequency requirements before solving.

## Files to Modify

- `src/shift_solver/validation/feasibility_checker.py` - add check_shift_frequency_requirements()

## Validations

1. **Worker not restricted from ALL required shift types**
   - If worker is restricted from all shift types in the requirement, it's infeasible
   - Example: Worker "Olinger" is restricted from both mvsc_day and mvsc_night, but has a frequency requirement for those shifts

2. **All referenced shift types exist**
   - Validate shift_type IDs in requirements exist in the schedule's shift types

3. **max_periods_between <= num_periods**
   - Requirement window can't be larger than the schedule period

## Error Messages

```
Infeasible: Worker 'Olinger' has frequency requirement for shift types
['mvsc_day', 'mvsc_night'] but is restricted from all of them.

Infeasible: Shift frequency requirement references unknown shift type 'invalid_shift'.

Infeasible: Worker 'Beckley' has max_periods_between=10 but schedule only
has 8 periods.
```

## Acceptance Criteria

- [ ] FeasibilityChecker.check_shift_frequency_requirements() method
- [ ] Clear error messages for each failure mode
- [ ] Unit tests for each validation case
