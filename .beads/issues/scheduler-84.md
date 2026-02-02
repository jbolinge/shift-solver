---
id: scheduler-84
title: "Test Industry-Specific Complex Scenarios"
type: task
status: open
priority: 2
created: 2026-02-02T12:00:00Z
updated: 2026-02-02T12:00:00Z
labels: [testing, complex-scheduling, e2e]
parent: scheduler-65
---

# Test Industry-Specific Complex Scenarios

## Problem

Different industries have unique scheduling challenges that combine constraints in specific ways. These need dedicated test scenarios.

## Test Cases

### Healthcare
1. **24/7 coverage**: Day, evening, night shifts all periods
2. **Skill matching**: RN vs LPN requirements per shift
3. **Overtime limits**: Max 40 hours/week hard constraint
4. **Weekend rotation**: Fair weekend distribution
5. **On-call scheduling**: Standby shifts with constraints

### Retail
6. **Variable demand**: More coverage on weekends
7. **Part-time mix**: Full-time + part-time workers
8. **Availability patterns**: Students available evenings only
9. **Holiday coverage**: Special requirements for holidays

### Warehouse
10. **Shift handoff**: Overlapping shifts for transitions
11. **Equipment certification**: Forklift operators required
12. **Break compliance**: Required break scheduling
13. **Overtime control**: Minimize overtime costs

### Logistics
14. **Route coverage**: Drivers for specific routes
15. **Hours of service**: DOT compliance limits
16. **Delivery windows**: Time-sensitive requirements

## Expected Behavior

- Each industry scenario should solve successfully
- Solution should respect industry-specific constraints
- Performance should be acceptable for typical sizes

## Files to Modify

- `tests/test_e2e/test_healthcare_scenarios.py`
- `tests/test_e2e/test_retail_scenarios.py`
- `tests/test_e2e/test_warehouse_scenarios.py`
- `tests/test_e2e/test_logistics_scenarios.py` (new file)

## Notes

Some scenarios may require new constraint types not yet implemented.

