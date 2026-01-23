---
id: scheduler-15
title: "ShiftSolver main orchestrator"
type: task
status: closed
priority: 1
created: 2026-01-22
updated: 2026-01-22
parent: scheduler-8
depends-on: scheduler-11,scheduler-12,scheduler-13,scheduler-14
---

# ShiftSolver main orchestrator

Main solver class orchestrating the entire optimization.

## Implementation
- [ ] ShiftSolver class with solve() method
- [ ] Create model and variables
- [ ] Apply all enabled constraints from registry
- [ ] Configure solver parameters from config
- [ ] Return (success, Schedule) tuple

## Solver Configuration
- max_time_seconds
- num_workers (CPU threads)
- quick_solution_seconds for fast mode
