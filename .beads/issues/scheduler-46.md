---
id: scheduler-46
title: "Multi-Constraint Interactions"
type: task
status: open
priority: 0
created: 2026-01-25
updated: 2026-01-25
parent: scheduler-39
---

# Multi-Constraint Interactions

E2E tests for constraint interaction and competition.

**File:** `tests/test_e2e/test_constraint_interactions.py`

## Test Cases

1. **Fairness vs Request conflicts** - Weight competition
2. **Coverage vs Availability tension**
3. **Frequency vs MaxAbsence interaction**
4. **Sequence vs Fairness**
5. **All 5 soft constraints enabled simultaneously** - 20 workers, 5 shifts, 12 periods
6. **Weight sensitivity analysis** - Same scenario, different weights

## Implementation Notes

- Test soft constraint weight balancing
- Verify objective function combines constraints correctly
- Use parametrized tests for weight sensitivity

## Acceptance Criteria

- [ ] All 6 test cases implemented
- [ ] Constraint weights properly balanced
- [ ] Complex multi-constraint scenarios solve correctly
