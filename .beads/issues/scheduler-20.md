---
id: scheduler-20
title: "Request constraint (soft)"
type: task
status: closed
priority: 2
created: 2026-01-22
updated: 2026-01-22
parent: scheduler-17
depends-on: scheduler-11
---

# Request constraint (soft)

Honor worker scheduling preferences (positive/negative).

## Implementation
- [ ] RequestConstraint class
- [ ] Positive request: prefer to work shift
- [ ] Negative request: prefer to avoid shift
- [ ] Violation variables for unfulfilled requests
- [ ] Priority levels for requests

## Configuration
```yaml
request:
  enabled: true
  weight: 150
  parameters:
    max_requests_per_worker: 8
```
