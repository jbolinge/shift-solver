---
id: scheduler-9
title: "SolverVariables typed container"
type: task
status: open
priority: 1
created: 2026-01-22
updated: 2026-01-22
parent: scheduler-8
depends-on: scheduler-3
---

# SolverVariables typed container

Create strongly-typed container for OR-Tools CP-SAT variables.

## Implementation
- [ ] SolverVariables dataclass with assignment dict
- [ ] Type-safe accessor methods (get_assignment_var, etc.)
- [ ] Support for string worker IDs and shift type IDs
- [ ] Aggregate variables (totals per worker per shift type)

## Pattern Reference
See physician-scheduler: src/solver/types.py
