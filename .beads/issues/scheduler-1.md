---
id: scheduler-1
title: "Foundation"
type: epic
status: open
priority: 1
created: 2026-01-22
updated: 2026-01-22
---

# Foundation

Core infrastructure: project setup, models, database, CLI scaffold, test infrastructure

## Scope
- Project setup with uv and pyproject.toml
- Core domain models (Worker, ShiftType, Schedule)
- Configuration schema with Pydantic validation
- SQLite database schema and repository layer
- Basic CLI scaffolding with Click
- Unit test infrastructure with pytest + hypothesis

## Acceptance Criteria
- [ ] `uv run shift-solver --version` works
- [ ] `uv run shift-solver init-db` creates database
- [ ] Models have >90% test coverage
- [ ] Config loading and validation works
