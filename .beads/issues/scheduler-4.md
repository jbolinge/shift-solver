---
id: scheduler-4
title: "Configuration schema with Pydantic validation"
type: task
status: closed
priority: 1
created: 2026-01-22
updated: 2026-01-22
parent: scheduler-1
blocks: scheduler-6
---

# Configuration schema with Pydantic validation

Create YAML configuration schema with Pydantic v2 validation.

## Config Sections
- [ ] ScheduleConfig - period_type, num_periods
- [ ] SolverConfig - max_time_seconds, num_workers
- [ ] ConstraintConfig - enabled, is_hard, weight, parameters
- [ ] ShiftTypeConfig - id, name, category, times, workers_required
- [ ] DatabaseConfig - path, backup settings
- [ ] LoggingConfig - level, file path

## Requirements
- Pydantic v2 BaseModel for all configs
- YAML loading with PyYAML
- Validation with clear error messages
- Default values for optional settings
- Example config files for different industries

## TDD Approach
Write tests for config loading and validation before implementation.
