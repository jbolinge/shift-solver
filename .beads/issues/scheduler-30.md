---
id: scheduler-30
title: "FeasibilityChecker (pre-solve validation)"
type: task
status: closed
priority: 2
created: 2026-01-22
updated: 2026-01-24
parent: scheduler-29
depends-on: scheduler-3,scheduler-4
---

# FeasibilityChecker (pre-solve validation)

Validate input data before attempting to solve.

## Checks
- [x] Sufficient workers for coverage requirements
- [x] No conflicting availability (all workers unavailable same period)
- [x] Worker restrictions don't make shifts unfillable
- [x] Valid date ranges and periods
- [x] Config consistency

## Implementation
- [x] FeasibilityChecker class
- [x] Return detailed FeasibilityResult with issues list
- [x] Fail fast with clear error messages

## Implementation Notes
- `src/shift_solver/validation/feasibility.py` - FeasibilityChecker class
- Tests in `tests/test_validation/test_feasibility.py` (15 tests)
