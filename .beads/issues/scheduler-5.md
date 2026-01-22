---
id: scheduler-5
title: "SQLite database schema and repository layer"
type: task
status: open
priority: 1
created: 2026-01-22
updated: 2026-01-22
parent: scheduler-1
depends-on: scheduler-3
---

# SQLite database schema and repository layer

Create SQLite persistence layer using SQLAlchemy 2.0.

## Tables
- [ ] workers - worker definitions
- [ ] shift_types - shift type definitions
- [ ] schedules - schedule metadata
- [ ] assignments - worker-shift assignments
- [ ] availabilities - time-off records
- [ ] requests - scheduling preferences
- [ ] constraint_configs - per-schedule constraint settings

## Repository Pattern
- [ ] WorkerRepository - CRUD for workers
- [ ] ShiftTypeRepository - CRUD for shift types
- [ ] ScheduleRepository - CRUD for schedules with assignments
- [ ] Base repository with common operations

## Requirements
- SQLAlchemy 2.0 with type hints
- Async support for future web API
- Migration support (alembic or manual)
- Connection pooling

## TDD Approach
Write repository tests with in-memory SQLite before implementation.
