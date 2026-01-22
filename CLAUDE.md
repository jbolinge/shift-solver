# shift-solver

General-purpose shift scheduling optimization using constraint programming.

## Project Overview

This is a configurable shift scheduling application that uses Google OR-Tools CP-SAT solver to generate optimal schedules. It generalizes the physician-scheduler project into a tool usable by any industry.

## Technology Stack

- **Python 3.12+** with modern type hints
- **uv** for package management
- **OR-Tools** for constraint programming
- **SQLite + SQLAlchemy 2.0** for persistence
- **Pydantic v2** for configuration validation
- **Click** for CLI
- **pytest + hypothesis** for TDD

## Key Concepts

- **Worker**: A schedulable resource (employee, contractor, etc.)
- **ShiftType**: A type of shift with time, duration, and requirements
- **Constraint**: Rules that schedules must satisfy (hard) or prefer (soft)
- **Schedule**: Complete assignment of workers to shifts over a time period

## Project Structure

```
src/shift_solver/
├── models/          # Core domain models (Worker, ShiftType, Schedule)
├── constraints/     # Constraint library (coverage, fairness, etc.)
├── solver/          # OR-Tools integration
├── db/              # SQLite persistence
├── io/              # CSV/Excel import/export
├── validation/      # Pre/post-solve validation
├── cli/             # Click CLI commands
└── utils/           # Logging, dates, progress
```

## Development Workflow

1. **TDD**: Write tests first, then implementation
2. **Beads tracking**: Use `/bd` commands to track issues
3. **Feature branches**: `feature/<epic-name>` merged to main when complete
4. **Frequent commits**: Small, focused commits with clear messages

## Running Commands

```bash
# Run tests
uv run pytest

# Run specific test file
uv run pytest tests/test_models/test_worker.py

# Run with coverage
uv run pytest --cov=src/shift_solver

# Type checking
uv run mypy src/

# Linting
uv run ruff check src/

# CLI (after implementation)
uv run shift-solver --help
```

## Configuration

Main config file: `config/config.yaml`

Constraints are configured with:
- `enabled`: true/false
- `is_hard`: true = must satisfy, false = soft with penalty
- `weight`: penalty weight for soft constraints
- `parameters`: constraint-specific settings

## Reference

Based on patterns from: `/home/me/workspace/python/physician-scheduler/`
