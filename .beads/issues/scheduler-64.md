---
id: scheduler-64
title: "Add infeasibility detection and messaging tests"
type: task
status: open
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

- [ ] Test: known infeasible scenario returns clear message
- [ ] Test: pre-solve feasibility check catches issue before CP-SAT
- [ ] Test: CLI displays infeasibility reason to user
- [ ] Verify error messages are actionable (tell user what to fix)
