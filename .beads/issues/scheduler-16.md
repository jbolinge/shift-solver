---
id: scheduler-16
title: "Generate CLI command"
type: task
status: open
priority: 1
created: 2026-01-22
updated: 2026-01-22
parent: scheduler-8
depends-on: scheduler-15,scheduler-6
---

# Generate CLI command

Implement the shift-solver generate command.

## Implementation
- [ ] Add generate command to CLI
- [ ] Options: --start-date, --end-date, --output, --quick-solve, --time-limit
- [ ] Load config and input data
- [ ] Run solver
- [ ] Output schedule to file or stdout

## Usage
```bash
shift-solver generate --start-date 2026-01-01 --end-date 2026-12-31 --output schedule.json
```
