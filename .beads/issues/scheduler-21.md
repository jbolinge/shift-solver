---
id: scheduler-21
title: "Sequence constraints (soft)"
type: task
status: closed
priority: 2
created: 2026-01-22
updated: 2026-01-22
parent: scheduler-17
depends-on: scheduler-11
---

# Sequence constraints (soft)

Control consecutive assignments and shift patterns.

## Implementation
- [ ] SequenceNoConsecutiveConstraint class
  - Discourage consecutive periods at same shift category
- [ ] SequencePatternConstraint class (optional)
  - Bonus for preferred patterns (e.g., night before vacation)

## Configuration
```yaml
sequence_no_consecutive:
  enabled: true
  weight: 100
  parameters:
    categories: ["ambulatory"]
```
