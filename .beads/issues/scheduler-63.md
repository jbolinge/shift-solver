---
id: scheduler-63
title: "Add tests for request + restriction conflicts"
type: task
status: open
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

- [ ] Test: positive request for restricted shift (soft request should be violated)
- [ ] Test: negative request for non-restricted shift
- [ ] Test: priority ordering when requests conflict with restrictions
- [ ] Verify solver behavior is correct and predictable
