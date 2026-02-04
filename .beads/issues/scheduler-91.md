---
id: scheduler-91
title: "Shift Frequency Constraints"
type: epic
status: open
priority: 1
created: 2026-02-04
updated: 2026-02-04
---

# Shift Frequency Constraints

Per-worker shift frequency requirements allowing configurations like "Worker X must work at least one of shift types [A, B, C] within every N periods" as either soft or hard constraints.

## Summary

This feature uses **shift type groups** rather than a separate "location" concept, following the existing pattern where `restricted_shifts` references shift type IDs directly. A "location" is implicitly defined by grouping shift types in the config.

### Design Decision

Use shift type IDs directly - no "location" field added to ShiftType:
```yaml
shift_types: ["mvsc_day", "mvsc_night"]  # Implicitly = MVSC location
```

### Algorithm

Sliding window approach: For each window of `max_periods_between` periods, worker must work at least one of the specified shift types.

```python
for req in requirements:
    for start in range(num_periods - req.max_periods_between + 1):
        window = range(start, start + req.max_periods_between)
        # Sum assignments to any of the required shift types in window
        # Soft: create violation var if sum == 0
        # Hard: enforce sum >= 1
```

## Child Issues

### Data Model & Config
- **scheduler-92** - Create ShiftFrequencyRequirement data model
- **scheduler-93** - Add shift_frequency to configuration schema (depends on scheduler-92)

### Constraint Implementation
- **scheduler-94** - Implement ShiftFrequencyConstraint (depends on scheduler-92, scheduler-93)
- **scheduler-95** - Integrate shift_frequency into solver context (depends on scheduler-94)

### Validation & Testing
- **scheduler-96** - Pre-solve feasibility validation (depends on scheduler-92)
- **scheduler-97** - Test suite for ShiftFrequencyConstraint (depends on scheduler-94, scheduler-95)

## Acceptance Criteria

- [ ] Per-worker configurable frequency requirements
- [ ] References groups of shift type IDs (no new "location" concept)
- [ ] Soft/hard constraint support
- [ ] Sliding window enforcement
- [ ] All tests pass
- [ ] No regressions in existing functionality
