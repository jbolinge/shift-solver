---
id: scheduler-59
title: "Add date format configuration to avoid ambiguity"
type: feature
status: closed
priority: 1
created: 2026-02-01
updated: 2026-02-01
parent: scheduler-51
---

# Add date format configuration to avoid ambiguity

## Problem

Dates like "01/02/2026" are ambiguous (US: Jan 2 vs EU: Feb 1). Code always tries US first, so EU dates where day ≤ 12 parse incorrectly.

**Current code:**
```python
DATE_FORMATS = [
    "%Y-%m-%d",  # ISO
    "%m/%d/%Y",  # US - tried first!
    "%d/%m/%Y",  # EU - only tried if US fails
]
```

## Files to Modify

- `src/shift_solver/io/date_utils.py:7-11`
- `src/shift_solver/config/schema.py` - add date_format config option

## Acceptance Criteria

- [x] Add `date_format` config option (ISO, US, EU, or auto)
- [x] When format specified, use only that format
- [x] When auto, use current behavior with warning for ambiguous dates
- [x] Add tests for explicit format selection

## Resolution

Added DateFormat enum and date_format config option to ScheduleConfig.
Updated parse_date() to accept date_format parameter. In auto mode,
ambiguous dates (both values <= 12) trigger a warning with guidance.
Added 18 comprehensive tests in TestDateFormatDetection,
TestParseDateWithFormat, TestAmbiguousDateWarning, and
TestDateFormatErrorMessages classes.
