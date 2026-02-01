---
id: scheduler-62
title: "Add full DB persistence cycle integration test"
type: task
status: closed
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

- [x] Test: init DB → load workers/shifts → solve → persist schedule → reload
- [x] Verify round-trip data integrity
- [x] Test with various schedule sizes

## Resolution

Created `tests/test_integration/test_db_persistence.py` with 4 tests:
- `test_full_persistence_cycle`: Complete workflow from DB init to reload
- `test_round_trip_data_integrity`: Verify all worker fields survive round-trip
- `test_persistence_with_various_schedule_sizes`: Test with 1, 4, 8 periods
- `test_cascade_delete_on_schedule`: Verify cascade delete works correctly
