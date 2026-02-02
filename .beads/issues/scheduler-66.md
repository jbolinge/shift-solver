---
id: scheduler-66
title: "Test Fairness Constraint Category Filter Validation"
type: task
status: open
priority: 2
created: 2026-02-02T12:00:00Z
updated: 2026-02-02T12:00:00Z
labels: [testing, api-mismatch, constraints]
parent: scheduler-65
---

# Test Fairness Constraint Category Filter Validation

## Problem

The fairness constraint accepts a `categories` parameter to filter which shift types count toward fairness calculations. However, category names are not validated against actual shift type category values.

**Location**: `src/shift_solver/constraints/fairness.py:109`

When categories filter is provided:
- New variables are created that shadow pre-built undesirable_totals
- No validation that category IDs match shift type categories
- Invalid categories are silently ignored

## Test Cases

1. **Valid category filter**: Verify fairness applies only to specified categories
2. **Invalid category name**: Verify behavior when config contains non-existent category
3. **Mixed valid/invalid categories**: Verify partial matches work correctly
4. **Category case sensitivity**: Test if "Day" vs "day" matters
5. **Empty categories list**: Verify behavior with `categories: []`

## Expected Behavior

- Invalid categories should either raise a validation error or log a warning
- Fairness should only consider shifts matching valid categories
- Clear error messages when misconfigured

## Files to Modify

- `tests/test_constraints/test_fairness.py`
- Potentially `src/shift_solver/constraints/fairness.py` (if validation needed)

## Notes

