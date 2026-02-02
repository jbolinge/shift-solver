---
id: scheduler-73
title: "Test Overlapping Availability and Request Constraints"
type: task
status: closed
priority: 2
created: 2026-02-02T12:00:00Z
updated: 2026-02-02T12:00:00Z
labels: [testing, edge-case, constraints]
parent: scheduler-65
---

# Test Overlapping Availability and Request Constraints

## Problem

A worker could have:
- Unavailable period: 2026-01-01 to 2026-01-07
- Positive shift request: 2026-01-05 (within unavailable period)

This conflict is not validated pre-solve and could lead to infeasible problems or unexpected behavior.

## Test Cases

1. **Request during unavailability**: Positive request for day worker is unavailable
2. **Partial overlap**: Request spans into unavailable period
3. **Negative request + unavailability**: Redundant but valid
4. **Same day boundaries**: Request end == availability start
5. **Multiple overlapping constraints**: Complex conflict scenarios
6. **Pre-solve detection**: Verify FeasibilityChecker catches conflicts

## Expected Behavior

- FeasibilityChecker should detect and report conflicts
- Clear error message indicating which constraints conflict
- Soft request during hard unavailability should be skipped or warned

## Files to Modify

- `tests/test_validation/test_feasibility_checker.py`
- `tests/test_constraints/test_availability_request_overlap.py` (new file)

## Notes

