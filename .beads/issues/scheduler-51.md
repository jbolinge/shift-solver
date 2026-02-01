---
id: scheduler-51
title: "Code Quality & Integration Hardening"
type: epic
status: open
priority: 1
created: 2026-02-01
updated: 2026-02-01
---

# Code Quality & Integration Hardening

Address API mismatches, integration test gaps, and runtime edge cases identified in deep-dive analysis. Improves code robustness, test coverage, and maintainability.

## Summary

Analysis revealed:
- **10 API mismatches/interface issues** (3 high, 5 medium, 2 low severity)
- **15+ integration test gaps** (missing module combinations and workflows)
- **11 runtime edge case risks** (3 high, 6 medium, 2 low severity)

## Child Issues

### High Priority (Priority 0) - COMPLETED
- **scheduler-52** ✓ Type coercion validation in IO layer
- **scheduler-53** ✓ Pre-solve feasibility check for coverage vs restrictions
- **scheduler-54** ✓ Refactor priority from variable names to metadata

### Medium Priority (Priority 1) - IN PROGRESS
- **scheduler-55** ✓ Unify soft constraint default config with registry
- **scheduler-56** ✓ Respect explicit constraint_configs for RequestConstraint
- **scheduler-57** ✓ Make Fairness-ObjectiveBuilder coupling explicit
- **scheduler-58** Unify CSV and Excel error handling
- **scheduler-59** Add date format configuration to avoid ambiguity

### Low Priority (Priority 2) - IN PROGRESS
- **scheduler-60** Derive period_type from period_dates
- **scheduler-61** ✓ Replace assertions with proper exception handling

### Integration Tests (Priority 1) - IN PROGRESS
- **scheduler-62** Add full DB persistence cycle integration test
- **scheduler-63** Add tests for request + restriction conflicts
- **scheduler-64** ✓ Add infeasibility detection and messaging tests

## Acceptance Criteria

- [x] All high priority issues resolved (3/3)
- [ ] All medium priority issues resolved (2/5)
- [ ] All low priority issues resolved (1/2)
- [ ] All integration test gaps addressed (1/3)
- [ ] Full test suite passes
- [ ] No new regressions introduced
