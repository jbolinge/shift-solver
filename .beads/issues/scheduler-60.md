---
id: scheduler-60
title: "Derive period_type from period_dates"
type: bug
status: open
priority: 2
created: 2026-02-01
updated: 2026-02-01
parent: scheduler-51
---

# Derive period_type from period_dates

## Problem

SolutionExtractor always sets `period_type="week"` regardless of actual period length.

**Current code:**
```python
# solution_extractor.py:88
schedule = Schedule(
    ...
    period_type="week",  # Hardcoded!
    ...
)
```

## Files to Modify

- `src/shift_solver/solver/solution_extractor.py:88`

## Acceptance Criteria

- [ ] Infer period_type from period_dates duration (1 day = "day", 7 days = "week", etc.)
- [ ] Add test verifying period_type matches actual period length
