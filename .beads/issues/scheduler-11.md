---
id: scheduler-11
title: "Coverage constraint (hard)"
type: task
status: closed
priority: 1
created: 2026-01-22
updated: 2026-01-22
parent: scheduler-8
depends-on: scheduler-10
---

# Coverage constraint (hard)

Ensure minimum/maximum worker coverage per shift per period.

## Implementation
- [ ] BaseConstraint abstract class
- [ ] ConstraintRegistry for dynamic loading
- [ ] CoverageConstraint implementation
- [ ] Support for per-period coverage overrides

## Constraint Logic
- Sum of assignments for shift S in period P == workers_required
- Hard constraint: must be satisfied exactly
