---
id: scheduler-77
title: "Test Circular Restriction/Preference Logic"
type: task
status: closed
priority: 2
created: 2026-02-02T12:00:00Z
updated: 2026-02-02T17:00:00Z
closed: 2026-02-02T17:00:00Z
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

### Resolution (2026-02-02)

**Decision:** Error at Worker creation time (fail-fast approach)

**Rationale:** Having a shift in both `restricted_shifts` and `preferred_shifts` is a logical contradiction - you can't prefer something you're not allowed to do. This should be caught as early as possible (at data entry/import) rather than silently failing or causing confusing solver behavior.

**Changes Made:**
1. Added validation to `Worker.__post_init__()` in `src/shift_solver/models/worker.py`:
   - Checks for intersection between `restricted_shifts` and `preferred_shifts`
   - Raises `ValueError` with clear message listing conflicting shift IDs

2. Created `tests/test_models/test_worker_validation.py` with 9 tests:
   - Tests for single and multiple conflicting shifts
   - Tests for partial overlap between sets
   - Tests for valid disjoint sets
   - Tests for empty sets
   - Tests for error message content

**Error Message Format:**
```
ValueError: Shifts cannot be both restricted and preferred: day, night
```
