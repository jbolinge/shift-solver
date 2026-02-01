---
id: scheduler-53
title: "Add pre-solve feasibility check for coverage vs restrictions"
type: feature
status: closed
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

- [x] Add `check_coverage_vs_restrictions()` to FeasibilityChecker
- [x] For each shift type, verify available workers >= workers_required
- [x] Account for availability constraints reducing worker pool
- [x] Return clear error message identifying which shift types are infeasible
- [x] Add tests for: all workers restricted, partial restrictions, restrictions + unavailability combined

## Resolution

- FeasibilityChecker already had `_check_restrictions` and `_check_combined_feasibility` methods
- Added `_check_feasibility()` method to ShiftSolver that calls FeasibilityChecker before solving
- Added `feasibility_issues` field to SolverResult to expose issues to callers
- Added `INFEASIBLE_PRE_SOLVE` status for early detection of infeasible problems
- Added TestCoverageVsRestrictions test class with 3 tests
- Added TestShiftSolverPreSolveFeasibility test class with 2 tests
