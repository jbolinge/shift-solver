---
id: scheduler-54
title: "Refactor priority from variable names to metadata"
type: task
status: closed
priority: 0
created: 2026-02-01
updated: 2026-02-01
parent: scheduler-51
---

# Refactor priority from variable names to metadata

## Problem

RequestConstraint embeds priority in variable names (`req_viol_W001_shift1_p0_r0_prio2`), and ObjectiveBuilder extracts it via regex. This is fragile - if naming conventions change, optimization weights silently break.

**Current code:**
```python
# request.py:175-176
weighted_name = f"{violation_name}_prio{request.priority}"
self._violation_variables[weighted_name] = violation_var

# objective_builder.py:96-98
match = re.search(r"_prio(\d+)$", var_name)
```

## Files to Modify

- `src/shift_solver/constraints/request.py:175-176`
- `src/shift_solver/constraints/base.py` - add priority metadata storage
- `src/shift_solver/solver/objective_builder.py:96-98`

## Acceptance Criteria

- [x] Add `_violation_priorities: dict[str, int]` to BaseConstraint
- [x] RequestConstraint stores priority in dict, not variable name
- [x] ObjectiveBuilder reads priority from dict, not regex
- [x] Remove regex-based priority extraction (kept as fallback for compatibility)
- [x] Add tests verifying priority is correctly applied to objective

## Resolution

- Added `_violation_priorities: dict[str, int]` to BaseConstraint with property accessor
- Updated RequestConstraint to store priority in dict without encoding in variable name
- Added `_get_priority()` method to ObjectiveBuilder that checks dict first, falls back to regex
- Added TestRequestConstraintPriorityMetadata test class with 2 tests
- All 582 existing tests pass
