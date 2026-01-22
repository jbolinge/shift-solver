---
id: scheduler-2
title: "Project setup with uv and pyproject.toml"
type: task
status: closed
priority: 1
created: 2026-01-22
updated: 2026-01-22
parent: scheduler-1
---

# Project setup with uv and pyproject.toml

Set up the shift-solver project using uv with modern Python 3.12+ best practices.

## Tasks
- [ ] Initialize uv project
- [ ] Create pyproject.toml with all dependencies
- [ ] Set up src layout (src/shift_solver/)
- [ ] Create .python-version file
- [ ] Add .gitignore
- [ ] Create CLAUDE.md with project context
- [ ] Create initial README.md

## Dependencies
- ortools>=9.7.0
- pyyaml>=6.0
- click>=8.0.0
- pydantic>=2.0.0
- sqlalchemy>=2.0.0

## Dev Dependencies
- pytest>=8.0.0
- pytest-cov>=4.0.0
- hypothesis>=6.0.0
- ruff>=0.1.0
