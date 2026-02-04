---
id: scheduler-92
title: "Create ShiftFrequencyRequirement data model"
type: task
status: open
priority: 1
created: 2026-02-04
updated: 2026-02-04
parent: scheduler-91
---

# Create ShiftFrequencyRequirement data model

Create new dataclass in `models/data_models.py` for per-worker shift frequency requirements.

## Implementation

```python
@dataclass
class ShiftFrequencyRequirement:
    worker_id: str
    shift_types: frozenset[str]  # Shift type IDs worker must work
    max_periods_between: int     # Maximum periods between assignments
```

## Files to Modify

- `src/shift_solver/models/data_models.py` - add ShiftFrequencyRequirement dataclass

## Requirements

- Validation: `max_periods_between > 0`
- Validation: `shift_types` non-empty
- Follow pattern of Availability and SchedulingRequest dataclasses
- Use `frozenset[str]` for shift_types to match existing patterns

## Acceptance Criteria

- [ ] Dataclass with validation (max_periods_between > 0, shift_types non-empty)
- [ ] Follows pattern of Availability and SchedulingRequest
- [ ] Unit tests for validation
