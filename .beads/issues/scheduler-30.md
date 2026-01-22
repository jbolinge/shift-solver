---
id: scheduler-30
title: "FeasibilityChecker (pre-solve validation)"
type: task
status: open
priority: 2
created: 2026-01-22
updated: 2026-01-22
parent: scheduler-29
depends-on: scheduler-3,scheduler-4
---

# FeasibilityChecker (pre-solve validation)

Validate input data before attempting to solve.

## Checks
- [ ] Sufficient workers for coverage requirements
- [ ] No conflicting availability (all workers unavailable same period)
- [ ] Worker restrictions don't make shifts unfillable
- [ ] Valid date ranges and periods
- [ ] Config consistency

## Implementation
- [ ] FeasibilityChecker class
- [ ] Return detailed FeasibilityResult with issues list
- [ ] Fail fast with clear error messages
