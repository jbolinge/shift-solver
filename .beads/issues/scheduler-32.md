---
id: scheduler-32
title: "Validate CLI command"
type: task
status: open
priority: 2
created: 2026-01-22
updated: 2026-01-22
parent: scheduler-29
depends-on: scheduler-31
---

# Validate CLI command

Implement the shift-solver validate command.

## Implementation
- [ ] Add validate command to CLI
- [ ] Load schedule from file or database
- [ ] Run ScheduleValidator
- [ ] Output validation report

## Usage
```bash
shift-solver validate --schedule schedule.json
shift-solver validate --schedule-id scheduler-123
```
