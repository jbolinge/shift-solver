---
id: scheduler-82
title: "Test Solver Stress with Tight Constraints"
type: task
status: closed
priority: 2
created: 2026-02-02T12:00:00Z
updated: 2026-02-02T18:30:00Z
closed: 2026-02-02T18:30:00Z
labels: [testing, complex-scheduling, solver, slow]
parent: scheduler-65
---

# Test Solver Stress with Tight Constraints

## Problem

Scheduling problems with tight constraints can be:
- Very slow to solve
- Infeasible without clear reason
- Prone to timeout without finding solutions

## Test Cases

### Scale Tests
1. **50 workers, 52 periods**: Large-scale annual schedule
2. **100 workers, 12 periods**: Many workers, quarterly
3. **20 workers, 104 periods**: 2-year schedule

### Tight Constraint Tests
4. **Exact coverage**: Workers required == workers available
5. **Many restrictions**: 50% of workers restricted from 50% of shifts
6. **Dense requests**: Every worker has requests for every period
7. **Tight fairness**: Spread must be <= 1 shift

### Timeout Behavior
8. **Timeout with partial solution**: Verify best-so-far returned
9. **Timeout without solution**: Verify graceful failure
10. **Quick solution mode**: 60-second quick solve, then continue

### Memory/Performance
11. **Variable count tracking**: Log total variables created
12. **Constraint count tracking**: Log total constraints added
13. **Memory usage**: Monitor memory during large solves

## Expected Behavior

- Reasonable solve times for common scenarios
- Graceful degradation under stress
- Clear timeout reporting

## Files to Modify

- `tests/test_e2e/test_solver_stress.py` (new file)

## Notes

Mark as `@pytest.mark.slow` - these tests may take minutes to run.

### Resolution (2026-02-02)

**Note:** Existing test files `test_performance.py` and `test_tight_constraints.py` already cover many scenarios. Created `test_solver_stress.py` to add remaining coverage.

**Tests Added:** Created `tests/test_e2e/test_solver_stress.py` with 12 tests:

- `TestExtendedTimeHorizon` (2 tests): 104-period 2-year schedules, 52-period with restrictions
- `TestDenseRequests` (2 tests): Every worker with requests for every period, conflicting positive requests
- `TestTightFairness` (2 tests): Spread minimization, fairness with restrictions
- `TestVariableConstraintCounts` (2 tests): Variable/constraint count tracking and scaling
- `TestExactCoverage` (2 tests): Workers required == available, unavailability breaks exact coverage
- `TestTimeoutWithPartialSolution` (2 tests): Short timeout behavior, adequate timeout succeeds

**Key Test Scenarios:**
| Scenario | Workers | Periods | Result |
|----------|---------|---------|--------|
| 2-year schedule | 20 | 104 | Feasible |
| Dense requests | 10 | 8 | 80 requests, feasible |
| Exact coverage | 6 | 4 | All workers assigned |
| Tight fairness | 6 | 6 | Spread ≤ 1 |
