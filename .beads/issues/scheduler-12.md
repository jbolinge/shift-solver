---
id: scheduler-12
title: "Worker restriction constraint (hard)"
type: task
status: open
priority: 1
created: 2026-01-22
updated: 2026-01-22
parent: scheduler-8
depends-on: scheduler-11
---

# Worker restriction constraint (hard)

Prevent workers from being assigned to restricted shifts.

## Implementation
- [ ] WorkerRestrictionConstraint class
- [ ] Read restricted_shifts from Worker model
- [ ] Add constraint: assignment[w][p][s] == 0 for restricted shifts

## Test Cases
- Worker with no restrictions can work any shift
- Worker with restriction cannot be assigned to that shift
- Multiple restrictions per worker
