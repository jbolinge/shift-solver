---
id: scheduler-31
title: "ScheduleValidator (post-solve validation)"
type: task
status: open
priority: 2
created: 2026-01-22
updated: 2026-01-22
parent: scheduler-29
depends-on: scheduler-15
---

# ScheduleValidator (post-solve validation)

Validate generated schedules against all constraints.

## Checks
- [ ] All hard constraints satisfied
- [ ] Coverage requirements met
- [ ] No restricted assignments
- [ ] Availability honored
- [ ] Soft constraint violation report

## Implementation
- [ ] ScheduleValidator class
- [ ] ValidationResult with violations and warnings
- [ ] Statistics: fairness metrics, request fulfillment rate
