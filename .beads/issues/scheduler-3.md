---
id: scheduler-3
title: "Core domain models (Worker, ShiftType, Schedule)"
type: task
status: closed
priority: 1
created: 2026-01-22
updated: 2026-01-22
parent: scheduler-1
blocks: scheduler-5,scheduler-6
---

# Core domain models (Worker, ShiftType, Schedule)

Create the core domain models using frozen dataclasses with full type hints.

## Models to Create
- [ ] Worker - represents a schedulable resource
- [ ] ShiftType - defines a type of shift
- [ ] ShiftInstance - a concrete shift occurrence
- [ ] PeriodAssignment - assignments for one scheduling period
- [ ] Schedule - complete schedule for entire horizon
- [ ] Availability - worker availability/unavailability
- [ ] SchedulingRequest - worker preferences

## Requirements
- Use @dataclass(frozen=True) for immutable models
- Full type hints with Python 3.12+ syntax
- Validation methods where appropriate
- String IDs (not integers) for flexibility

## TDD Approach
Write tests first for each model before implementation.
