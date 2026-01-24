---
id: scheduler-25
title: "CSV import handler"
type: task
status: closed
priority: 2
created: 2026-01-22
updated: 2026-01-22
closed: 2026-01-24
parent: scheduler-24
depends-on: scheduler-3
---

# CSV import handler

Import workers, shifts, availability, and requests from CSV files.

## Implementation
- [ ] CSVLoader class
- [ ] workers.csv: id, name, worker_type, restricted_shifts
- [ ] availability.csv: worker_id, start_date, end_date, type
- [ ] requests.csv: worker_id, dates, request_type, shift_type_id
- [ ] Validation and error reporting

## Requirements
- Clear error messages for malformed data
- Support for optional columns
- Date parsing with multiple formats
