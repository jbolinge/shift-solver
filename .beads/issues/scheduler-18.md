---
id: scheduler-18
title: "Fairness constraint (soft)"
type: task
status: open
priority: 2
created: 2026-01-22
updated: 2026-01-22
parent: scheduler-17
depends-on: scheduler-11
---

# Fairness constraint (soft)

Even distribution of undesirable shifts across workers.

## Implementation
- [ ] FairnessConstraint class
- [ ] Count total undesirable shift assignments per worker
- [ ] Minimize max - min across workers
- [ ] Configurable: which shift categories to balance

## Objective Terms
- Create violation variables for max deviation
- Weight from config (default: 1000)
