---
id: scheduler-22
title: "Max absence constraint (soft)"
type: task
status: open
priority: 2
created: 2026-01-22
updated: 2026-01-22
parent: scheduler-17
depends-on: scheduler-11
---

# Max absence constraint (soft)

Worker should not be absent from shift type for more than N periods.

## Implementation
- [ ] MaxAbsenceConstraint class
- [ ] Track last assignment to each shift type per worker
- [ ] Penalize gaps longer than max_periods_absent

## Configuration
```yaml
max_absence:
  enabled: true
  weight: 200
  parameters:
    max_periods_absent: 8
```
