---
id: scheduler-87
title: "Test CLI Command Integration"
type: task
status: open
priority: 2
created: 2026-02-02T12:00:00Z
updated: 2026-02-02T12:00:00Z
labels: [testing, integration, cli]
parent: scheduler-65
---

# Test CLI Command Integration

## Problem

CLI commands need integration testing to verify:
- Commands work end-to-end
- Error handling is user-friendly
- Configuration is loaded correctly
- Output formats are correct

## Test Cases

### Generate Command
1. **Basic solve**: `shift-solver generate --config config.yaml`
2. **Output formats**: `--output schedule.json`, `--output schedule.xlsx`
3. **Time limit**: `--time-limit 60`
4. **Invalid config**: Missing file, invalid YAML
5. **Infeasible input**: Verify error message

### Import Command
6. **CSV import**: `import-data --workers workers.csv`
7. **Excel import**: `import-data --excel data.xlsx`
8. **Missing file**: Verify error handling
9. **Invalid format**: Wrong columns, bad data

### Export Command
10. **Excel export**: `export --schedule schedule.json --format excel`
11. **JSON export**: `export --schedule schedule.json --format json`
12. **Missing schedule**: Verify error handling

### Validate Command
13. **Valid schedule**: No errors reported
14. **Invalid schedule**: Constraint violations reported
15. **Partial validation**: Specific constraints only

### Config Check
16. **Valid config**: `check-config --config valid.yaml`
17. **Invalid config**: Missing fields, wrong types

### Verbosity
18. **Silent mode**: No output except errors
19. **Verbose mode**: `-v`, `-vv`, `-vvv` levels

## Expected Behavior

- All commands work end-to-end
- Clear error messages for user errors
- Consistent exit codes

## Files to Modify

- `tests/test_cli/test_generate.py`
- `tests/test_cli/test_import.py`
- `tests/test_cli/test_export.py`
- `tests/test_cli/test_integration.py` (new file)

## Notes

