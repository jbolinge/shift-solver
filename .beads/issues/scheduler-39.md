---
id: scheduler-39
title: "Commercial-Grade E2E Test Suite"
type: epic
status: closed
priority: 1
created: 2026-01-25
updated: 2026-01-25
---

# Commercial-Grade E2E Test Suite

Comprehensive end-to-end tests to validate the shift solver at commercial-level quality. Tests cover complex real-world scenarios, edge cases, and stress conditions.

## Scope

This epic contains 11 child issues covering distinct test domains:

1. **scheduler-40** - Vacation & Availability Edge Cases
2. **scheduler-41** - Holiday Coverage Scenarios
3. **scheduler-42** - Tight Constraint Situations
4. **scheduler-43** - Request Conflicts
5. **scheduler-44** - Fairness Edge Cases
6. **scheduler-45** - Worker Restriction Complexity
7. **scheduler-46** - Multi-Constraint Interactions
8. **scheduler-47** - Boundary Conditions
9. **scheduler-48** - Real-World Scheduling Patterns
10. **scheduler-49** - Performance & Stress Testing
11. **scheduler-50** - Regression & Known Edge Cases

## File Structure

```
tests/test_e2e/
    test_availability_edge_cases.py  # scheduler-40
    test_holiday_coverage.py         # scheduler-41
    test_tight_constraints.py        # scheduler-42
    test_request_conflicts.py        # scheduler-43
    test_fairness_edge_cases.py      # scheduler-44
    test_restriction_complexity.py   # scheduler-45
    test_constraint_interactions.py  # scheduler-46
    test_boundary_conditions.py      # scheduler-47
    test_real_world_patterns.py      # scheduler-48
    test_performance.py              # scheduler-49
    test_regression.py               # scheduler-50
```

## Critical Files to Reference

- `tests/factories.py` - ScenarioBuilder, WorkerFactory, ShiftTypeFactory
- `tests/conftest.py` - Shared fixtures
- `src/shift_solver/constraints/` - All 8 constraint implementations
- `src/shift_solver/solver/shift_solver.py` - Main solver orchestrator
- `src/shift_solver/validation/feasibility.py` - Pre-solve validation

## Implementation Notes

- Use `@pytest.mark.e2e` for all tests
- Use `@pytest.mark.slow` for performance tests (>30s)
- Extend `ScenarioBuilder` with new helper methods as needed
- Add new fixtures to `tests/test_e2e/conftest.py`
- Target >90% line coverage for constraint code paths

## Acceptance Criteria

- [ ] All 11 test files implemented
- [ ] `uv run pytest tests/test_e2e/ -v` passes
- [ ] `uv run pytest tests/test_e2e/ -m slow` runs performance tests
- [ ] Coverage >90% for constraint code paths
