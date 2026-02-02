---
id: scheduler-78
title: "Test Date Ambiguity Handling"
type: task
status: open
priority: 2
created: 2026-02-02T12:00:00Z
updated: 2026-02-02T12:00:00Z
labels: [testing, edge-case, io]
parent: scheduler-65
---

# Test Date Ambiguity Handling

## Problem

The date parser in AUTO mode tries formats in order: ISO, US, EU. Ambiguous dates like "01/02/2026" could be:
- January 2nd (US format)
- February 1st (EU format)

**Location**: `src/shift_solver/io/date_utils.py`

A warning is logged but parsing continues with the first match (US format).

## Test Cases

1. **Unambiguous ISO**: "2026-01-15" -> Jan 15
2. **Unambiguous US**: "01/15/2026" -> Jan 15 (day > 12)
3. **Unambiguous EU**: "15/01/2026" -> Jan 15 (day > 12)
4. **Ambiguous**: "01/02/2026" -> Jan 2 (US wins) + warning
5. **Mixed file formats**: Some dates ambiguous, some not
6. **Config override**: DateFormat.EU should force EU interpretation
7. **Warning deduplication**: Same date shouldn't warn twice
8. **Batch validation**: Report all ambiguous dates in file

## Expected Behavior

- Ambiguous dates should always log warnings
- Config can force specific format interpretation
- Clear documentation of format precedence

## Files to Modify

- `tests/test_io/test_date_utils.py`
- `tests/test_io/test_date_ambiguity.py` (new file)

## Notes

