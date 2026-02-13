---
id: scheduler-107
title: "CLI integration: extend export command with plotly format"
type: task
status: open
priority: 1
created: 2026-02-13
updated: 2026-02-13
parent: scheduler-98
depends-on: scheduler-106
labels: [io, visualization, cli]
---

# CLI integration: extend export command with plotly format

Add `"plotly"` as a format option to the existing `shift-solver export` CLI command.

## Files to Modify

- `src/shift_solver/cli/commands/io_commands.py` - Add plotly format handling

## Implementation

### Changes to export_schedule command

1. Add `"plotly"` to format choices:
```python
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["excel", "json", "plotly"]),
    default="excel",
    help="Output format",
)
```

2. Add plotly handling branch:
```python
elif output_format == "plotly":
    from shift_solver.io import PlotlyVisualizer

    visualizer = PlotlyVisualizer()
    visualizer.export_all(schedule_obj, output)

    # Count generated files
    chart_count = len(list(output.glob("*.html"))) - 1  # Exclude index
    click.echo(f"Exported {chart_count} charts + index to: {output}/")
```

Note: When format is `"plotly"`, `--output` is treated as a **directory** path (unlike excel/json which are file paths). This should be documented in the help text.

3. Update `--output` help text or add a note:
```python
help="Output file path (or directory for plotly format)"
```

## Tests (write first)

```python
class TestCLIPlotlyExport:
    def test_cli_export_plotly_format_accepted(self, runner):
        """'plotly' is accepted as a format choice."""

    def test_cli_export_plotly_creates_chart_directory(self, runner, tmp_path, sample_schedule_json):
        """Export with --format plotly creates output directory with HTML files."""

    def test_cli_export_plotly_with_real_schedule_json(self, runner, tmp_path):
        """Full round-trip: load schedule JSON, export plotly, verify files."""
```

Use Click's `CliRunner` for testing. Create a sample schedule JSON file as a fixture.

## Acceptance Criteria

- [ ] `shift-solver export --format plotly` is accepted without error
- [ ] Output directory is created with all chart HTML files + index.html
- [ ] CLI prints summary message with chart count and output path
- [ ] Existing excel and json formats are not affected
- [ ] All 3 tests pass
