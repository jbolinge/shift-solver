---
id: scheduler-50
title: "Regression & Known Edge Cases"
type: task
status: open
priority: 0
created: 2026-01-25
updated: 2026-01-25
parent: scheduler-39
---

# Regression & Known Edge Cases

E2E tests for regression prevention and documented edge cases.

**File:** `tests/test_e2e/test_regression.py`

## Test Cases

1. **Infeasibility detection accuracy** - Known infeasible scenarios
2. **Soft constraint violation tracking**
3. **Date range boundary bugs** - Year boundary, leap year, DST
4. **ID collision handling** - Duplicate worker/shift IDs
5. **Empty data handling** - Empty availability/requests lists
6. **Unicode and special characters in names**

## Implementation Notes

- Document any bugs found and add regression tests
- Test edge cases in date handling
- Verify ID uniqueness validation

## Acceptance Criteria

- [ ] All 6 test cases implemented
- [ ] Known edge cases documented in test docstrings
- [ ] Date handling works across boundaries
