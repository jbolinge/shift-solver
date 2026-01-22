---
id: scheduler-17
title: "Soft Constraints"
type: epic
status: open
priority: 2
created: 2026-01-22
updated: 2026-01-22
depends-on: scheduler-8
---

# Soft Constraints

Full constraint library with soft constraints and weighted objective.

## Scope
- Fairness constraint (even distribution)
- Frequency constraint (work shift every N periods)
- Request constraint (positive/negative preferences)
- Sequence constraints (no consecutive, patterns)
- Max absence constraint
- ObjectiveBuilder with weighted penalties

## Acceptance Criteria
- [ ] All 8+ constraint types implemented
- [ ] Constraints can be enabled/disabled via config
- [ ] Weights affect solution optimization
- [ ] Integration tests pass with multiple constraints
