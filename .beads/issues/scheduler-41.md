---
id: scheduler-41
title: "Holiday Coverage Scenarios"
type: task
status: closed
priority: 1
created: 2026-01-25
updated: 2026-01-25
parent: scheduler-39
---

# Holiday Coverage Scenarios

E2E tests for holiday scheduling complexity.

**File:** `tests/test_e2e/test_holiday_coverage.py`

## Test Cases

1. **Skeleton crew during holidays** - Reduced workers_required
2. **Holiday premium shifts** - All workers submit negative requests
3. **Year-end scheduling** - Christmas + New Year clustering
4. **Fair rotation of holiday assignments**
5. **Mixed normal/holiday periods** - In same schedule
6. **Multi-quarter holiday fairness tracking**

## Implementation Notes

- Create shift types with varying `workers_required` per period
- Use negative requests to model holiday aversion
- Test fairness constraint with holiday-specific categories

## Acceptance Criteria

- [ ] All 6 test cases implemented
- [ ] Holiday fairness validated over multiple periods
- [ ] Coverage constraint handles reduced requirements
