---
id: scheduler-8
title: "Basic Solver"
type: epic
status: closed
priority: 1
created: 2026-01-22
updated: 2026-01-22
depends-on: scheduler-1
---

# Basic Solver

Working OR-Tools solver with hard constraints only.

## Scope
- SolverVariables typed container
- VariableBuilder implementation
- Hard constraints: coverage, restriction, availability
- SolutionExtractor implementation
- Basic `generate` CLI command

## Acceptance Criteria
- [ ] Solver finds valid schedule for 10 workers, 4 shift types, 4 weeks
- [ ] All hard constraints enforced
- [ ] Schedule can be extracted and viewed
- [ ] `shift-solver generate` command works
