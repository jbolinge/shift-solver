---
id: scheduler-83
title: "Test Barely Feasible and Boundary Scenarios"
type: task
status: open
priority: 2
created: 2026-02-02T12:00:00Z
updated: 2026-02-02T12:00:00Z
labels: [testing, complex-scheduling, solver]
parent: scheduler-65
---

# Test Barely Feasible and Boundary Scenarios

## Problem

Some scheduling scenarios are on the boundary of feasibility:
- Exactly enough workers for coverage
- Availability windows just barely overlap with requirements
- Restrictions leave exactly one valid assignment

These test the solver's ability to find solutions in constrained spaces.

## Test Cases

### Exact Fit
1. **Coverage = Workers**: 3 workers, 3 required per shift
2. **Single valid assignment**: Restrictions leave only one option
3. **Availability window**: Worker available exactly when needed

### One-Off Feasibility
4. **Add 1 worker**: Infeasible -> feasible with +1 worker
5. **Remove 1 restriction**: Infeasible -> feasible with -1 restriction
6. **Extend availability**: Infeasible -> feasible with +1 day

### Boundary Arithmetic
7. **Coverage boundary**: Verify solver finds solution at exact boundary
8. **Frequency boundary**: max_periods_between exactly matches schedule
9. **Fairness boundary**: Spread of 0 (perfect equality) when possible

### Randomized Boundaries
10. **Property-based**: Use hypothesis to generate boundary scenarios
11. **Fuzzing**: Randomly perturb feasible scenarios toward infeasibility

## Expected Behavior

- Solver should find solutions at feasibility boundaries
- Clear distinction between "tight but feasible" and "infeasible"
- Good heuristics for near-boundary problems

## Files to Modify

- `tests/test_e2e/test_boundary_scenarios.py` (new file)
- `tests/strategies.py` (add hypothesis strategies)

## Notes

