---
id: scheduler-44
title: "Fairness Edge Cases"
type: task
status: closed
priority: 1
created: 2026-01-25
updated: 2026-01-25
parent: scheduler-39
---

# Fairness Edge Cases

E2E tests for fairness constraint edge conditions.

**File:** `tests/test_e2e/test_fairness_edge_cases.py`

## Test Cases

1. **All shifts marked undesirable**
2. **Single worker available for undesirable shift**
3. **Fairness with varying worker restrictions**
4. **Long-term fairness across 12 weeks** - Quarterly tracking
5. **Fairness with category filter active**
6. **Zero undesirable shifts** - No-op verification
7. **Spread variable tracking**

## Implementation Notes

- Test fairness constraint with `categories` parameter
- Verify spread (max - min) minimization
- Check fairness with worker restrictions

## Acceptance Criteria

- [ ] All 7 test cases implemented
- [ ] Spread variable correctly calculated
- [ ] Category filtering works correctly
