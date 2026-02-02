---
id: scheduler-89
title: "Expand Hypothesis Property-Based Testing"
type: task
status: open
priority: 2
created: 2026-02-02T12:00:00Z
updated: 2026-02-02T12:00:00Z
labels: [testing, integration, hypothesis]
parent: scheduler-65
---

# Expand Hypothesis Property-Based Testing

## Problem

The `tests/strategies.py` file exists but is empty. Property-based testing with Hypothesis could catch edge cases that example-based tests miss.

## Test Cases

### Model Strategies
1. **Worker strategy**: Generate valid workers with random attributes
2. **ShiftType strategy**: Generate valid shift types
3. **Availability strategy**: Generate valid availability periods
4. **Request strategy**: Generate valid scheduling requests

### Property Tests
5. **Worker equality**: Two workers with same ID should be equal
6. **Schedule validity**: Generated schedules should validate
7. **Date range containment**: Availability.contains_date should be correct
8. **Frozenset immutability**: Modifications should fail

### Solver Properties
9. **Feasible implies solution**: If FeasibilityChecker passes, solver should find solution
10. **Solution validity**: Any solution should pass ScheduleValidator
11. **Coverage satisfaction**: Solution should meet coverage requirements
12. **Restriction respect**: No worker assigned to restricted shift

### I/O Properties
13. **Round-trip identity**: Import(Export(data)) == data
14. **Date parsing inverse**: format(parse(date)) == date
15. **JSON serialization**: loads(dumps(obj)) == obj

## Expected Behavior

- Strategies should generate valid domain objects
- Properties should hold for all generated inputs
- Edge cases discovered should become regression tests

## Files to Modify

- `tests/strategies.py` (implement strategies)
- `tests/test_models/test_worker.py` (add property tests)
- `tests/test_models/test_shift.py` (add property tests)
- `tests/test_solver/test_properties.py` (new file)

## Notes

