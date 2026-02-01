---
id: scheduler-53
title: "Add pre-solve feasibility check for coverage vs restrictions"
type: feature
status: open
priority: 0
created: 2026-02-01
updated: 2026-02-01
parent: scheduler-51
---

# Add pre-solve feasibility check for coverage vs restrictions

## Problem

If all workers are restricted from a shift type but coverage requires workers, the problem becomes INFEASIBLE with no warning. Users get a cryptic "INFEASIBLE" status with no explanation.

**Example scenario:**
- 3 workers, all restricted from "night_shift"
- Coverage requires 2 "night_shift" workers
- Result: INFEASIBLE (no explanation)

## Files to Modify

- `src/shift_solver/validation/feasibility.py` - add new check
- `src/shift_solver/solver/shift_solver.py` - call check before solve

## Acceptance Criteria

- [ ] Add `check_coverage_vs_restrictions()` to FeasibilityChecker
- [ ] For each shift type, verify available workers >= workers_required
- [ ] Account for availability constraints reducing worker pool
- [ ] Return clear error message identifying which shift types are infeasible
- [ ] Add tests for: all workers restricted, partial restrictions, restrictions + unavailability combined
