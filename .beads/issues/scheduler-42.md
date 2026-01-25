---
id: scheduler-42
title: "Tight Constraint Situations"
type: task
status: open
priority: 0
created: 2026-01-25
updated: 2026-01-25
parent: scheduler-39
---

# Tight Constraint Situations

E2E tests for near-feasibility boundary conditions.

**File:** `tests/test_e2e/test_tight_constraints.py`

## Test Cases

1. **Barely feasible** - Exactly enough workers for total requirements
2. **Near-infeasible with single worker slack**
3. **High restriction count** - 50% restricted from night, 30% from weekend
4. **Conflicting hard constraints leading to INFEASIBLE**
5. **Feasibility boundary detection** - Binary search for exact threshold
6. **FeasibilityChecker accuracy** - Compare vs actual solver result

## Implementation Notes

- Test both OPTIMAL and INFEASIBLE status codes
- Use FeasibilityChecker for pre-solve validation
- Verify solver correctly identifies infeasible problems

## Acceptance Criteria

- [ ] All 6 test cases implemented
- [ ] INFEASIBLE status correctly detected
- [ ] FeasibilityChecker matches solver results
