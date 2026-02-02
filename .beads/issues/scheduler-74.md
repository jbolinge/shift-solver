---
id: scheduler-74
title: "Test JSON Round-Trip Data Integrity"
type: task
status: open
priority: 2
created: 2026-02-02T12:00:00Z
updated: 2026-02-02T12:00:00Z
labels: [testing, edge-case, io]
parent: scheduler-65
---

# Test JSON Round-Trip Data Integrity

## Problem

Several data structures use JSON serialization:
- Worker `restricted_shifts` and `preferred_shifts` stored as JSON lists in DB
- Worker `attributes` dict stored as JSON
- ShiftType `required_attributes` stored as JSON

**Risk**: No validation that shift IDs in JSON reference existing ShiftTypes after round-trip.

## Test Cases

1. **Frozenset round-trip**: `frozenset(["a", "b"])` -> JSON -> frozenset
2. **Empty frozenset**: `frozenset()` -> JSON -> frozenset (not `[""]`)
3. **Dict attributes**: Complex nested dict preservation
4. **Unicode in shift IDs**: Non-ASCII characters preserved
5. **Special characters**: Quotes, backslashes in values
6. **Large data**: Many shift IDs, deeply nested attributes
7. **Null vs empty**: JSON null vs empty list vs empty string

## Expected Behavior

- Data should be identical after round-trip
- Type preservation (frozenset, not list)
- No data loss or corruption
- Clear errors for invalid JSON

## Files to Modify

- `tests/test_db/test_json_roundtrip.py` (new file)
- `tests/test_io/test_data_integrity.py` (new file)

## Notes

