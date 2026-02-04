---
id: scheduler-93
title: "Add shift_frequency to configuration schema"
type: task
status: closed
priority: 1
created: 2026-02-04
updated: 2026-02-04
closed: 2026-02-04
parent: scheduler-91
depends-on: scheduler-92
---

# Add shift_frequency to configuration schema

Update `config/schema.py` with Pydantic validation for shift frequency constraint configuration.

## Config Format

```yaml
constraints:
  shift_frequency:
    enabled: true
    is_hard: false
    weight: 500
    parameters:
      requirements:
        - worker_id: "Olinger"
          shift_types: ["mvsc_day", "mvsc_night"]
          max_periods_between: 4
        - worker_id: "Beckley"
          shift_types: ["stf_day"]
          max_periods_between: 4
```

## Files to Modify

- `src/shift_solver/config/schema.py` - add Pydantic model for shift_frequency constraint
- `src/shift_solver/config/loader.py` - parse requirements into ShiftFrequencyRequirement objects (if needed)

## Implementation

Add Pydantic model for requirement list:
```python
class ShiftFrequencyRequirementConfig(BaseModel):
    worker_id: str
    shift_types: list[str]
    max_periods_between: int = Field(gt=0)

class ShiftFrequencyParameters(BaseModel):
    requirements: list[ShiftFrequencyRequirementConfig] = []
```

## Acceptance Criteria

- [x] Pydantic model for requirement list
- [x] Validation: worker_id exists, shift_types exist, max_periods_between valid
- [x] Config loader parses requirements into ShiftFrequencyRequirement objects

## Resolution

- Added `ShiftFrequencyRequirementConfig` Pydantic model with validation
- Added `ShiftFrequencyParametersConfig` Pydantic model for parameters.requirements
- Added `parse_shift_frequency_requirements()` function to convert config to domain objects
- Added 7 tests in `tests/test_config/test_config.py`
