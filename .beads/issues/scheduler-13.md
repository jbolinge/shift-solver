---
id: scheduler-13
title: "Availability constraint (hard)"
type: task
status: closed
priority: 1
created: 2026-01-22
updated: 2026-01-22
parent: scheduler-8
depends-on: scheduler-11
---

# Availability constraint (hard)

Honor worker time-off and unavailability periods.

## Implementation
- [ ] AvailabilityConstraint class
- [ ] Map availability dates to periods
- [ ] Add constraint: assignment[w][p][*] == 0 for unavailable periods

## Test Cases
- Worker unavailable for specific period cannot be assigned
- Partial period unavailability
- Multiple unavailability periods per worker
