---
id: scheduler-19
title: "Frequency constraint (soft)"
type: task
status: closed
priority: 2
created: 2026-01-22
updated: 2026-01-22
parent: scheduler-17
depends-on: scheduler-11
---

# Frequency constraint (soft)

Worker must work certain shift at least every N periods.

## Implementation
- [ ] FrequencyConstraint class
- [ ] Sliding window check over N periods
- [ ] At least one assignment in each window
- [ ] Configurable per worker or global default

## Configuration
```yaml
frequency:
  enabled: true
  weight: 500
  parameters:
    default_max_periods_between: 4
```
