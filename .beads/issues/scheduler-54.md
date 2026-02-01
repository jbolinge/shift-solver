---
id: scheduler-54
title: "Refactor priority from variable names to metadata"
type: task
status: open
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

- [ ] Add `_violation_priorities: dict[str, int]` to BaseConstraint
- [ ] RequestConstraint stores priority in dict, not variable name
- [ ] ObjectiveBuilder reads priority from dict, not regex
- [ ] Remove regex-based priority extraction
- [ ] Add tests verifying priority is correctly applied to objective
