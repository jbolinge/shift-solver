---
id: scheduler-40
title: "Vacation & Availability Edge Cases"
type: task
status: open
priority: 1
created: 2026-01-25
updated: 2026-01-25
parent: scheduler-39
---

# Vacation & Availability Edge Cases

E2E tests for complex availability and vacation scenarios.

**File:** `tests/test_e2e/test_availability_edge_cases.py`

## Test Cases

1. **Overlapping vacation requests** - 2-3 workers with cascading overlaps
2. **Last-minute availability changes** - Mid-period submissions
3. **Partial/shift-specific unavailability** - Night-only, category-based restrictions
4. **Edge date boundaries** - Vacation starts/ends on period boundaries
5. **Single-day unavailability on period boundary**
6. **Unavailability just before/after period** - Should not affect schedule

## Implementation Notes

- Use `ScenarioBuilder.with_unavailability()` for test setup
- Test both hard and soft availability constraint modes
- Verify FeasibilityChecker accuracy for availability conflicts

## Acceptance Criteria

- [ ] All 6 test cases implemented
- [ ] Tests pass with `@pytest.mark.e2e`
- [ ] Edge cases properly exercise availability constraint
