---
id: scheduler-62
title: "Add full DB persistence cycle integration test"
type: task
status: open
priority: 1
created: 2026-02-01
updated: 2026-02-01
parent: scheduler-51
---

# Add full DB persistence cycle integration test

## Problem

No integration test covers the complete database workflow: init DB → load workers/shifts → solve → persist schedule → reload.

## Files to Create

- `tests/test_integration/test_db_persistence.py`

## Acceptance Criteria

- [ ] Test: init DB → load workers/shifts → solve → persist schedule → reload
- [ ] Verify round-trip data integrity
- [ ] Test with various schedule sizes
