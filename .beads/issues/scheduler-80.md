---
id: scheduler-80
title: "Test Objective Scaling with Large Request Volumes"
type: task
status: open
priority: 2
created: 2026-02-02T12:00:00Z
updated: 2026-02-02T12:00:00Z
labels: [testing, complex-scheduling, solver]
parent: scheduler-65
---

# Test Objective Scaling with Large Request Volumes

## Problem

Each request creates violation variables added to the objective with weight (default 150). With many requests:
- 100 requests × 52 weeks = 5,200+ violation variables
- Total weight could dominate other soft constraints
- Fairness weight (1000) may be overwhelmed

**Risk**: Solver prioritizes request satisfaction over fairness when many requests exist.

## Test Cases

1. **Small request volume**: 10 requests, verify balanced objective
2. **Medium volume**: 100 requests across 10 workers
3. **Large volume**: 1000+ requests, verify solver behavior
4. **Request vs fairness**: Many requests conflicting with fairness
5. **Priority scaling**: High priority requests (priority=3) vs low (priority=1)
6. **Objective coefficient analysis**: Extract and verify coefficients
7. **Solve time impact**: Measure solve time vs request count
8. **Solution quality**: Verify requests don't completely dominate

## Expected Behavior

- Objective should remain balanced regardless of request count
- Consider per-worker or per-period normalization
- Document expected tradeoffs at high volumes

## Files to Modify

- `tests/test_solver/test_objective_scaling.py` (new file)
- `tests/test_e2e/test_large_request_scenarios.py` (new file)

## Notes

