---
id: scheduler-94
title: "Implement ShiftFrequencyConstraint"
type: task
status: open
priority: 1
created: 2026-02-04
updated: 2026-02-04
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

- [ ] Constraint class following BaseConstraint pattern
- [ ] Soft mode creates violation variables with proper naming
- [ ] Hard mode enforces assignment in every window
- [ ] Registered via @register_soft() decorator
