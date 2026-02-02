---
id: scheduler-88
title: "Test Configuration Validation and Loading"
type: task
status: open
priority: 2
created: 2026-02-02T12:00:00Z
updated: 2026-02-02T12:00:00Z
labels: [testing, integration, config]
parent: scheduler-65
---

# Test Configuration Validation and Loading

## Problem

Configuration loading needs comprehensive testing:
- Pydantic validation works correctly
- YAML parsing handles edge cases
- Defaults are applied properly
- Errors are user-friendly

## Test Cases

### Valid Configurations
1. **Minimal config**: Only required fields
2. **Full config**: All fields specified
3. **Default application**: Missing optional fields use defaults
4. **Constraint configs**: All constraint types configured

### Invalid Configurations
5. **Missing required field**: Clear error message
6. **Wrong type**: Integer where string expected
7. **Out of range**: Negative weight, priority > 4
8. **Invalid YAML**: Syntax errors
9. **Duplicate shift IDs**: Should be caught

### Edge Cases
10. **Empty file**: Valid? Error?
11. **Unicode in values**: Names, IDs
12. **Very long values**: 1000-char shift name
13. **Special YAML values**: `null`, `true`, `yes`

### Time Parsing
14. **Valid times**: "08:00", "23:59"
15. **Invalid times**: "25:00", "8:0", "noon"
16. **Edge times**: "00:00", "24:00"

### Constraint Parameters
17. **Unknown parameter**: Extra param in constraint config
18. **Missing required param**: Constraint needs param not provided
19. **Wrong param type**: String where list expected

## Expected Behavior

- Clear validation errors with path to invalid field
- Helpful suggestions for common mistakes
- Defaults documented and applied correctly

## Files to Modify

- `tests/test_config/test_validation.py`
- `tests/test_config/test_loading.py` (new file)

## Notes

