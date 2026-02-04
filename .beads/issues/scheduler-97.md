---
id: scheduler-97
title: "Test suite for ShiftFrequencyConstraint"
type: task
status: closed
priority: 1
created: 2026-02-04
updated: 2026-02-04
closed: 2026-02-04
parent: scheduler-91
depends-on: scheduler-95
---

# Test suite for ShiftFrequencyConstraint

Comprehensive tests in `tests/test_constraints/test_shift_frequency.py`.

## Files to Create

- `tests/test_constraints/test_shift_frequency.py` - full test suite

## Unit Tests

- [ ] Single worker, single shift type requirement
- [ ] Single worker, multiple shift types (group)
- [ ] Multiple workers with different requirements
- [ ] Soft vs hard mode behavior
- [ ] Window boundary conditions

## Edge Cases

- [ ] max_periods_between = 1 (must work every period)
- [ ] max_periods_between = num_periods (only 1 window)
- [ ] Worker restricted from some but not all shift types in group
- [ ] Empty requirements list

## Integration Tests

- [ ] Combined with coverage, fairness, and request constraints
- [ ] E2E test with config file loading
- [ ] Verify violation variables appear in solution statistics (soft mode)
- [ ] Verify infeasible detection (hard mode with impossible requirements)

## Test Structure

```python
class TestShiftFrequencyConstraint:
    """Unit tests for ShiftFrequencyConstraint."""

    def test_single_worker_single_shift_type(self): ...
    def test_single_worker_multiple_shift_types(self): ...
    def test_multiple_workers_different_requirements(self): ...
    def test_soft_mode_creates_violation_variables(self): ...
    def test_hard_mode_enforces_assignment(self): ...
    def test_window_boundary_first_window(self): ...
    def test_window_boundary_last_window(self): ...

class TestShiftFrequencyEdgeCases:
    """Edge case tests."""

    def test_max_periods_between_equals_one(self): ...
    def test_max_periods_between_equals_num_periods(self): ...
    def test_worker_partially_restricted(self): ...
    def test_empty_requirements_list(self): ...

class TestShiftFrequencyIntegration:
    """Integration tests with other constraints."""

    def test_combined_with_coverage_constraint(self): ...
    def test_combined_with_fairness_constraint(self): ...
    def test_e2e_config_loading(self): ...
```

## Acceptance Criteria

- [x] All unit tests pass
- [x] All edge case tests pass
- [x] All integration tests pass
- [x] Test coverage comprehensive for shift_frequency.py

## Resolution

17 tests in `tests/test_constraints/test_shift_frequency.py`:

**Unit Tests (8):**
- 2 initialization tests
- 3 apply() behavior tests
- 1 multiple workers test
- 2 solve integration tests (soft/hard)

**Edge Cases (6):**
- Unknown worker/shift types handling
- Window boundary conditions
- Partial restrictions

**Integration Tests (3):**
- Combined with ShiftSolver
- E2E config loading from YAML
- Violation count verification
