---
id: scheduler-94
title: "Implement ShiftFrequencyConstraint"
type: task
status: closed
priority: 1
created: 2026-02-04
updated: 2026-02-04
closed: 2026-02-04
parent: scheduler-91
depends-on: scheduler-93
---

# Implement ShiftFrequencyConstraint

Create `constraints/shift_frequency.py` with sliding window constraint logic.

## Files to Create

- `src/shift_solver/constraints/shift_frequency.py` - new constraint module

## Algorithm

For each requirement, create constraints for each sliding window:
```python
for req in requirements:
    for start in range(num_periods - req.max_periods_between + 1):
        window = range(start, start + req.max_periods_between)
        # Sum assignments to any of the required shift types in window
        # Soft: create violation var if sum == 0
        # Hard: enforce sum >= 1
```

## Implementation Details

- Support soft (violation variables) and hard modes
- Register with `@register_soft()` decorator
- Follow BaseConstraint pattern
- Violation variable naming: `freq_viol_{worker_id}_w{window_start}`

## Reference

Based on physician-scheduler's special_frequencies implementation:
- Config: `special_frequencies: [{physician, location, max_weeks_between}]`
- Sliding window approach: 4-week requirement = 49 constraint windows over 52 weeks
- Soft constraint with weight 500

## Acceptance Criteria

- [x] Constraint class following BaseConstraint pattern
- [x] Soft mode creates violation variables with proper naming
- [x] Hard mode enforces assignment in every window
- [x] Registered in ConstraintRegistry (manual registration, not decorator)

## Resolution

- Created `ShiftFrequencyConstraint` class in `constraints/shift_frequency.py`
- Soft mode: creates `sf_viol_{worker_id}_w{window_start}` violation variables
- Hard mode: adds `sum(window_assignments) >= 1` constraints
- Registered in `constraint_registry.py` with default weight=500, disabled by default
- Added to `constraints/__init__.py` exports
- 12 unit tests in `tests/test_constraints/test_shift_frequency.py`
