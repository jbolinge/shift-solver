---
id: scheduler-45
title: "Worker Restriction Complexity"
type: task
status: closed
priority: 1
created: 2026-01-25
updated: 2026-01-25
parent: scheduler-39
---

# Worker Restriction Complexity

E2E tests for complex worker restriction scenarios.

**File:** `tests/test_e2e/test_restriction_complexity.py`

## Test Cases

1. **Workers with 5+ restricted shift types**
2. **Restriction bottlenecks** - Single worker for critical shift
3. **Pyramid restrictions** - Increasing restrictions per worker
4. **Dynamic restrictions varying by period** - Modeled via availability
5. **Circular restriction dependencies**

## Implementation Notes

- Use `Worker.restricted_shifts` frozenset
- Test restriction constraint as hard constraint
- Verify FeasibilityChecker catches restriction-based infeasibility

## Acceptance Criteria

- [x] All 5 test cases implemented
- [x] Restriction constraint enforced correctly
- [x] Bottleneck scenarios handled properly
