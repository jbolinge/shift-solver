---
id: scheduler-63
title: "Add tests for request + restriction conflicts"
type: task
status: closed
priority: 1
created: 2026-02-01
updated: 2026-02-01
parent: scheduler-51
---

# Add tests for request + restriction conflicts

## Problem

No tests cover the interaction between scheduling requests and worker restrictions. A worker might request a shift they're restricted from.

## Files to Create/Modify

- `tests/test_e2e/test_request_conflicts.py` or new file

## Acceptance Criteria

- [x] Test: positive request for restricted shift (soft request should be violated)
- [x] Test: negative request for non-restricted shift
- [x] Test: priority ordering when requests conflict with restrictions
- [x] Verify solver behavior is correct and predictable

## Resolution

Tests already exist in `tests/test_e2e/test_request_conflicts.py` (13 tests):
- `TestRestrictedShiftRequests`: Tests positive requests for restricted shifts
- `TestMultipleWorkersRequestSameShiftOff`: Tests negative requests
- `TestPriorityConflicts`: Tests priority ordering in conflict scenarios
- `TestRequestViolationCounting`: Verifies solver behavior is predictable

These tests were implemented as part of scheduler-43.
