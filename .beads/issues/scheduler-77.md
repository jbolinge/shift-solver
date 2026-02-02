---
id: scheduler-77
title: "Test Circular Restriction/Preference Logic"
type: task
status: open
priority: 2
created: 2026-02-02T12:00:00Z
updated: 2026-02-02T12:00:00Z
labels: [testing, edge-case, validation]
parent: scheduler-65
---

# Test Circular Restriction/Preference Logic

## Problem

A Worker can have a shift in both `restricted_shifts` AND `preferred_shifts`:
- Restriction: Worker cannot work this shift
- Preference: Worker prefers this shift

This is a logical contradiction not validated by the system.

## Test Cases

1. **Same shift in both**: restricted_shifts={"day"}, preferred_shifts={"day"}
2. **Validation detection**: Should model creation raise error?
3. **Solver behavior**: What happens if this reaches the solver?
4. **Pre-solve check**: Does FeasibilityChecker catch this?
5. **CSV import validation**: Should loader reject this data?
6. **Config validation**: Should Pydantic catch this?

## Expected Behavior

- Validation should catch this contradiction at creation time
- Clear error message indicating the conflict
- Decision: Restriction wins? Preference wins? Error?

## Files to Modify

- `tests/test_models/test_worker.py`
- `tests/test_validation/test_worker_validation.py`
- Potentially `src/shift_solver/models/worker.py` (if validation added)

## Notes

