---
id: scheduler-27
title: "Sample data generator"
type: task
status: closed
priority: 2
created: 2026-01-22
updated: 2026-01-22
closed: 2026-01-24
parent: scheduler-24
depends-on: scheduler-25
---

# Sample data generator

Generate sample input files for different industries.

## Implementation
- [ ] SampleGenerator class
- [ ] Industry presets: retail, healthcare, warehouse
- [ ] Configurable: num_workers, num_shifts, date_range
- [ ] Realistic availability patterns (weekends off, vacations)

## CLI Command
```bash
shift-solver generate-samples --industry retail --output ./samples/
```
