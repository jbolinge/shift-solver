---
id: scheduler-68
title: "Test SolverVariables Accessor Error Handling"
type: task
status: closed
priority: 2
created: 2026-02-02T12:00:00Z
updated: 2026-02-02T15:00:00Z
labels: [testing, api-mismatch, solver]
parent: scheduler-65
---

# Test SolverVariables Accessor Error Handling

## Problem

Constraints access variables via `SolverVariables` type-safe accessors. However, when KeyErrors occur (e.g., invalid worker_id, period, or shift_type_id), they are often caught and silently ignored in constraint apply() methods.

**Risk**: If a constraint config references a non-existent shift type or worker, it's silently skipped. Configuration errors cascade without trace.

## Test Cases

1. **Invalid worker_id**: Verify informative error message
2. **Invalid period index**: Verify error for out-of-range period
3. **Invalid shift_type_id**: Verify error for non-existent shift type
4. **Off-by-one period**: Test `period = num_periods` (common error)
5. **Error propagation**: Verify constraint errors bubble up appropriately
6. **Logging verification**: Confirm silent skips are logged at debug level

## Expected Behavior

- KeyErrors should include the specific key that failed
- Silent skips should log at WARNING or DEBUG level
- Configuration mismatches should be detectable

## Files to Modify

- `tests/test_solver/test_variable_builder.py`
- `tests/test_constraints/test_constraint_error_handling.py` (new file)

## Notes

