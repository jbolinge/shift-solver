---
id: scheduler-43
title: "Request Conflicts"
type: task
status: open
priority: 1
created: 2026-01-25
updated: 2026-01-25
parent: scheduler-39
---

# Request Conflicts

E2E tests for conflicting scheduling requests.

**File:** `tests/test_e2e/test_request_conflicts.py`

## Test Cases

1. **Multiple workers requesting same shift off** - 5 workers, coverage requires 2
2. **Worker requesting shift they're restricted from**
3. **Priority conflicts** - High priority conflicting requests
4. **Positive and negative requests for same period**
5. **Cascading request dependencies**
6. **Request violation counting accuracy**

## Implementation Notes

- Use `ScenarioBuilder.with_request()` for setup
- Test request constraint weight competition
- Verify violation variables track correctly

## Acceptance Criteria

- [ ] All 6 test cases implemented
- [ ] Request priorities properly honored
- [ ] Violation counts match expected
