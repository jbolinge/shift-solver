---
id: scheduler-33
title: "Error handling and logging"
type: task
status: closed
priority: 2
created: 2026-01-22
updated: 2026-01-24
parent: scheduler-29
---

# Error handling and logging

Comprehensive error handling and logging infrastructure.

## Implementation
- [x] Custom exception hierarchy (ShiftSolverError, ValidationError, etc.)
- [x] Structured logging with configurable levels
- [x] Progress tracking for long-running solves
- [x] User-friendly error messages

## Logging
- [x] Log to file and console
- [x] Structured JSON option for production
- [x] Solver progress updates

## Implementation Notes
- `src/shift_solver/utils/exceptions.py` - Exception hierarchy
- `src/shift_solver/utils/logging.py` - Logging setup and progress callback
- Tests in `tests/test_utils/` (24 tests)
