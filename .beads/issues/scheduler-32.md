---
id: scheduler-32
title: "Validate CLI command"
type: task
status: closed
priority: 2
created: 2026-01-22
updated: 2026-01-24
parent: scheduler-29
depends-on: scheduler-31
---

# Validate CLI command

Implement the shift-solver validate command.

## Implementation
- [x] Add validate command to CLI
- [x] Load schedule from file or database
- [x] Run ScheduleValidator
- [x] Output validation report

## Usage
```bash
shift-solver validate --schedule schedule.json
shift-solver validate --schedule schedule.json --config config.yaml
shift-solver validate --schedule schedule.json --output report.json
```

## Implementation Notes
- Added to `src/shift_solver/cli/main.py`
- Supports --workers, --availability, --requests for full validation
- JSON report output with --output option
- Tests in `tests/test_cli/test_validate_command.py` (7 tests)
