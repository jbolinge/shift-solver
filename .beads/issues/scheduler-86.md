---
id: scheduler-86
title: "Test Database Persistence Integration"
type: task
status: closed
priority: 2
created: 2026-02-02T12:00:00Z
updated: 2026-02-03T12:00:00Z
labels: [testing, integration, db]
parent: scheduler-65
---

# Test Database Persistence Integration

## Problem

The database schema is defined but persistence integration is incomplete:
- `init-db` command doesn't create tables
- No SessionLocal or engine initialization
- Domain model to DB model mapping not tested

## Test Cases

### Schema Tests
1. **Table creation**: All tables created with correct columns
2. **Foreign keys**: FK constraints enforced
3. **Indexes**: Expected indexes exist
4. **Cascading deletes**: Assignment delete cascades correctly

### CRUD Operations
5. **Worker CRUD**: Create, read, update, delete
6. **ShiftType CRUD**: Including JSON column handling
7. **Schedule CRUD**: Complex nested structure
8. **Assignment CRUD**: FK relationships maintained

### Domain Model Mapping
9. **Worker -> DBWorker**: Frozenset to JSON
10. **DBWorker -> Worker**: JSON to frozenset
11. **Schedule -> DBSchedule + DBAssignments**: Decomposition
12. **Full reconstruction**: DB -> complete Schedule object

### Concurrency
13. **Concurrent writes**: Multiple schedulers writing
14. **Read during write**: Query during solve
15. **Transaction rollback**: Error recovery

## Expected Behavior

- Complete persistence layer working
- Round-trip preserves all data
- Proper error handling for DB issues

## Files to Modify

- `tests/test_db/test_persistence.py` (new file)
- `tests/test_integration/test_db_workflow.py` (new file)

## Notes

May require implementing missing persistence code first.

