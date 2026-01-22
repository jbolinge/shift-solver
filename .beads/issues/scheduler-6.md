---
id: scheduler-6
title: "CLI scaffolding with Click"
type: task
status: open
priority: 1
created: 2026-01-22
updated: 2026-01-22
parent: scheduler-1
depends-on: scheduler-3,scheduler-4
---

# CLI scaffolding with Click

Create the command-line interface structure using Click.

## Commands to Scaffold
- [ ] shift-solver (main group)
- [ ] shift-solver version
- [ ] shift-solver init-db
- [ ] shift-solver check-config
- [ ] shift-solver list-workers (placeholder)
- [ ] shift-solver list-shifts (placeholder)
- [ ] shift-solver generate (placeholder)

## Requirements
- Click command group with --config and --verbose options
- Consistent error handling and exit codes
- Help text for all commands
- Entry point in pyproject.toml

## TDD Approach
Write CLI tests using Click's CliRunner before implementation.
