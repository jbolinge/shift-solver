---
id: scheduler-23
title: "ObjectiveBuilder with weighted penalties"
type: task
status: open
priority: 2
created: 2026-01-22
updated: 2026-01-22
parent: scheduler-17
depends-on: scheduler-18,scheduler-19,scheduler-20,scheduler-21,scheduler-22
---

# ObjectiveBuilder with weighted penalties

Build objective function from all soft constraint violations.

## Implementation
- [ ] ObjectiveBuilder class
- [ ] Collect violation variables from all soft constraints
- [ ] Apply weights from config
- [ ] Build minimization objective
- [ ] model.Minimize(sum of weighted violations)

## Requirements
- Support multiple objectives (lexicographic if needed)
- Log objective breakdown for debugging
