---
id: scheduler-79
title: "Test Infeasible Coverage + Restriction Combinations"
type: task
status: closed
priority: 1
created: 2026-02-02T12:00:00Z
updated: 2026-02-02T14:30:00Z
labels: [testing, complex-scheduling, solver]
parent: scheduler-65
---

# Test Infeasible Coverage + Restriction Combinations

## Problem

When coverage requires N workers but fewer than N workers are eligible (due to restrictions), the problem becomes infeasible. This may not be caught by FeasibilityChecker.

**Example**:
- Coverage requires 3 workers for "night" shift
- Only 2 workers can work "night" (3rd is restricted)
- Problem is infeasible but not detected pre-solve

## Test Cases

1. **Exact infeasibility**: 3 required, 2 eligible
2. **Marginal feasibility**: 3 required, 3 eligible (tight)
3. **Multiple shift types**: Some feasible, some not
4. **Combined restrictions**: Worker restricted from multiple shifts
5. **All workers restricted**: No one can work shift X
6. **Partial period infeasibility**: Feasible for some periods, not others
7. **FeasibilityChecker detection**: Verify pre-solve catch
8. **Error message quality**: Clear explanation of conflict

## Expected Behavior

- FeasibilityChecker should detect coverage/restriction conflicts
- Clear error message: "Shift 'night' requires 3 workers but only 2 are eligible"
- List which workers are restricted and why

## Files to Modify

- `tests/test_validation/test_feasibility_checker.py`
- `tests/test_e2e/test_infeasible_scenarios.py` (new file)

## Notes

