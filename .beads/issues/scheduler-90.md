---
id: scheduler-90
title: "Test Solution Validation and Post-Solve Checks"
type: task
status: open
priority: 2
created: 2026-02-02T12:00:00Z
updated: 2026-02-02T12:00:00Z
labels: [testing, integration, validation]
parent: scheduler-65
---

# Test Solution Validation and Post-Solve Checks

## Problem

After the solver finds a solution, it needs validation:
- All hard constraints satisfied
- Soft constraint violations match expected
- Solution can be reconstructed correctly

## Test Cases

### Hard Constraint Validation
1. **Coverage check**: Every period has required workers
2. **Availability check**: No worker assigned when unavailable
3. **Restriction check**: No worker assigned to restricted shift

### Soft Constraint Validation
4. **Request satisfaction**: Count honored vs violated requests
5. **Fairness metric**: Calculate actual spread
6. **Frequency compliance**: Verify sliding window requirements
7. **Sequence analysis**: Count consecutive same-category shifts

### Solution Extraction
8. **Variable extraction**: Assignment vars correctly read
9. **Schedule building**: PeriodAssignment objects correct
10. **Statistics calculation**: Metrics match solution
11. **Missing assignments**: Handle unassigned shifts

### Edge Cases
12. **Partial solution**: Timeout with incomplete solution
13. **Optimal vs feasible**: First solution vs optimized
14. **Multiple solutions**: Different valid assignments

## Expected Behavior

- Validation should catch any solver bugs
- Clear reporting of constraint satisfaction
- Statistics should match actual solution

## Files to Modify

- `tests/test_validation/test_schedule_validator.py`
- `tests/test_solver/test_solution_extraction.py`
- `tests/test_integration/test_post_solve_validation.py` (new file)

## Notes

