---
id: scheduler-31
title: "ScheduleValidator (post-solve validation)"
type: task
status: closed
priority: 2
created: 2026-01-22
updated: 2026-01-24
parent: scheduler-29
depends-on: scheduler-15
---

# ScheduleValidator (post-solve validation)

Validate generated schedules against all constraints.

## Checks
- [x] All hard constraints satisfied
- [x] Coverage requirements met
- [x] No restricted assignments
- [x] Availability honored
- [x] Soft constraint violation report

## Implementation
- [x] ScheduleValidator class
- [x] ValidationResult with violations and warnings
- [x] Statistics: fairness metrics, request fulfillment rate

## Implementation Notes
- `src/shift_solver/validation/schedule_validator.py` - ScheduleValidator class
- Tests in `tests/test_validation/test_schedule_validator.py` (11 tests)
