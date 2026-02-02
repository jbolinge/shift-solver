---
id: scheduler-69
title: "Test Hard vs Soft Request Constraint Enforcement Semantics"
type: task
status: open
priority: 2
created: 2026-02-02T12:00:00Z
updated: 2026-02-02T12:00:00Z
labels: [testing, api-mismatch, constraints]
parent: scheduler-65
---

# Test Hard vs Soft Request Constraint Enforcement Semantics

## Problem

Hard request constraints use `>=` for positive requests:
```python
if self.is_hard:
    if request.is_positive:
        self.model.add(assignment_var >= 1)  # Allows multiple!
```

But coverage constraint expects exactly 1 worker per shift. This mismatch could cause:
- A worker satisfying both coverage AND hard positive request in same period
- Unexpected scheduling when a single worker must fill multiple slots

**Location**: `src/shift_solver/constraints/request.py:139-147`

## Test Cases

1. **Single worker, hard positive request**: Can they satisfy coverage requirement?
2. **Multiple hard positive requests same period**: Verify behavior
3. **Hard positive + coverage conflict**: What happens when request period has limited slots?
4. **Hard negative with coverage**: Verify worker exclusion works with coverage
5. **Compare hard vs soft semantics**: Same scenario, different is_hard settings

## Expected Behavior

- Hard constraints should be mutually compatible
- Clear documentation of interaction between request and coverage
- No silent over-assignment

## Files to Modify

- `tests/test_constraints/test_request.py`
- `tests/test_integration/test_constraint_interactions.py`

## Notes

