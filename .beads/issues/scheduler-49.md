---
id: scheduler-49
title: "Performance & Stress Testing"
type: task
status: open
priority: 0
created: 2026-01-25
updated: 2026-01-25
parent: scheduler-39
---

# Performance & Stress Testing

E2E tests for solver performance and scalability.

**File:** `tests/test_e2e/test_performance.py`

## Test Cases

1. **50+ workers, 12+ weeks** - Assert solve time < 180s
2. **High constraint density** - Every worker has availability + requests + restrictions
3. **Solver timeout behavior** - time_limit_seconds=5 for complex problem
4. **Memory usage patterns** - 100 workers, 52 periods
5. **Incremental scaling tests** - 10, 20, 30, 40, 50 workers
6. **Parallel solver workers configuration**

## Implementation Notes

- Use `@pytest.mark.slow` for tests >30s
- Monitor solve time and memory usage
- Test solver timeout returns UNKNOWN status

## Acceptance Criteria

- [ ] All 6 test cases implemented
- [ ] Performance benchmarks documented
- [ ] Timeout behavior verified
