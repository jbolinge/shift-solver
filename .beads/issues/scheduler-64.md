---
id: scheduler-64
title: "Add infeasibility detection and messaging tests"
type: task
status: closed
priority: 1
created: 2026-02-01
updated: 2026-02-01
parent: scheduler-51
---

# Add infeasibility detection and messaging tests

## Problem

No tests verify that infeasibility is detected early and communicated clearly to users.

## Files to Create/Modify

- `tests/test_validation/test_feasibility.py`
- `tests/test_e2e/` - add infeasibility messaging tests

## Acceptance Criteria

- [x] Test: known infeasible scenario returns clear message
- [x] Test: pre-solve feasibility check catches issue before CP-SAT
- [ ] Test: CLI displays infeasibility reason to user (deferred - CLI not implemented)
- [x] Verify error messages are actionable (tell user what to fix)

## Resolution

Comprehensive tests were added as part of scheduler-53:
- TestCoverageVsRestrictions: 3 tests for coverage vs restrictions infeasibility
- TestShiftSolverPreSolveFeasibility: 2 tests for pre-solve detection with clear messages
- Tests verify messages include shift type name and worker counts
- 20 total feasibility-related tests now in the test suite
