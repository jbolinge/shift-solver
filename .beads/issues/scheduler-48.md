---
id: scheduler-48
title: "Real-World Scheduling Patterns"
type: task
status: closed
priority: 1
created: 2026-01-25
updated: 2026-01-25
parent: scheduler-39
---

# Real-World Scheduling Patterns

E2E tests for realistic industry patterns.

**File:** `tests/test_e2e/test_real_world_patterns.py`

## Test Cases

1. **Seasonal demand variations** - Varying workers_required by period
2. **Rotating schedules** - Day -> Night -> Weekend -> Off pattern
3. **Seniority-based preferences** - Priority multiplier via attributes
4. **Training/mentorship requirements** - Pairing constraints
5. **Part-time vs full-time distribution**
6. **On-call rotation patterns**

## Implementation Notes

- Use `Worker.attributes` for seniority modeling
- Test sequence constraint for rotation patterns
- Model pairing via custom constraints if needed

## Acceptance Criteria

- [ ] All 6 test cases implemented
- [ ] Industry patterns produce valid schedules
- [ ] Rotation and pairing work correctly
