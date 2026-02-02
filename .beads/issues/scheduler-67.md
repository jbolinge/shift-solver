---
id: scheduler-67
title: "Test Request Constraint Violation Variable Coupling"
type: task
status: open
priority: 2
created: 2026-02-02T12:00:00Z
updated: 2026-02-02T12:00:00Z
labels: [testing, api-mismatch, constraints]
parent: scheduler-65
---

# Test Request Constraint Violation Variable Coupling

## Problem

The request constraint uses `only_enforce_if` to create bidirectional indicator constraints linking violation variables to assignment variables.

**Location**: `src/shift_solver/constraints/request.py:159-176`

```python
if request.is_positive:
    # violation = (assignment == 0)
    self.model.add(assignment_var == 0).only_enforce_if(violation_var)
    self.model.add(assignment_var >= 1).only_enforce_if(violation_var.negated())
```

**Concern**: The `only_enforce_if` pattern creates implications, not strict equivalence. There's risk that violation_var might not accurately reflect the actual assignment state in the solution.

## Test Cases

1. **Positive request honored**: Verify violation_var=0 when assignment is made
2. **Positive request violated**: Verify violation_var=1 when no assignment
3. **Negative request honored**: Verify violation_var=0 when worker NOT assigned
4. **Negative request violated**: Verify violation_var=1 when worker IS assigned
5. **Multiple conflicting requests**: Worker with positive and negative for same period
6. **Post-solve validation**: Extract violation vars from solution, verify they match assignments

## Expected Behavior

- Violation variables must exactly reflect the satisfaction state of each request
- Bidirectional implications should be sound (no solver relaxation issues)

## Files to Modify

- `tests/test_constraints/test_request.py`

## Notes

