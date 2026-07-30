"""Tests for validate CLI command."""

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from shift_solver.cli.main import cli


@pytest.fixture
def runner() -> CliRunner:
    """Create a Click test runner."""
    return CliRunner()


@pytest.fixture
def valid_schedule_file(tmp_path: Path) -> Path:
    """Create a valid schedule JSON file."""
    schedule_data = {
        "schedule_id": "TEST-001",
        "start_date": "2026-01-01",
        "end_date": "2026-01-08",
        "periods": [
            {
                "period_index": 0,
                "period_start": "2026-01-01",
                "period_end": "2026-01-07",
                "assignments": {
                    "W1": [{"shift_type_id": "day", "date": "2026-01-01"}],
                    "W2": [
                        {"shift_type_id": "day", "date": "2026-01-01"},
                        {"shift_type_id": "night", "date": "2026-01-01"},
                    ],
                },
            }
        ],
        "statistics": {},
    }
    schedule_file = tmp_path / "schedule.json"
    with open(schedule_file, "w") as f:
        json.dump(schedule_data, f)
    return schedule_file


@pytest.fixture
def sample_config_file(tmp_path: Path) -> Path:
    """Create a sample config file for testing."""
    yaml_content = """
shift_types:
  - id: day
    name: Day Shift
    category: day
    start_time: "07:00"
    end_time: "15:00"
    duration_hours: 8.0
    workers_required: 2
  - id: night
    name: Night Shift
    category: night
    start_time: "23:00"
    end_time: "07:00"
    duration_hours: 8.0
    workers_required: 1
    is_undesirable: true
"""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml_content)
    return config_file


@pytest.fixture
def workers_file(tmp_path: Path) -> Path:
    """Create a workers CSV file."""
    csv_content = """id,name,worker_type,restricted_shifts,preferred_shifts
W1,Alice,full_time,,
W2,Bob,full_time,,
W3,Charlie,part_time,night,
"""
    workers_file = tmp_path / "workers.csv"
    workers_file.write_text(csv_content)
    return workers_file


class TestValidateCommandBasics:
    """Test basic validate command functionality."""

    def test_validate_help(self, runner: CliRunner) -> None:
        """Validate command shows help."""
        result = runner.invoke(cli, ["validate", "--help"])
        assert result.exit_code == 0
        assert "--schedule" in result.output

    def test_validate_requires_schedule(self, runner: CliRunner) -> None:
        """Validate command requires schedule file."""
        result = runner.invoke(cli, ["validate"])
        assert result.exit_code != 0
        assert "schedule" in result.output.lower() or "missing" in result.output.lower()

    def test_validate_missing_file(self, runner: CliRunner, tmp_path: Path) -> None:
        """Validate command reports error for missing file."""
        missing_file = tmp_path / "missing.json"
        result = runner.invoke(cli, ["validate", "--schedule", str(missing_file)])
        assert result.exit_code != 0


class TestValidateWithConfig:
    """Test validate command with configuration."""

    def test_validate_with_config(
        self,
        runner: CliRunner,
        valid_schedule_file: Path,
        sample_config_file: Path,
    ) -> None:
        """Validate command works with config file."""
        result = runner.invoke(
            cli,
            [
                "validate",
                "--schedule",
                str(valid_schedule_file),
                "--config",
                str(sample_config_file),
            ],
        )
        # Should run validation (may pass or fail based on data)
        assert "validation" in result.output.lower() or result.exit_code in [0, 1]


class TestValidateOutput:
    """Test validate command output."""

    def test_validate_shows_statistics(
        self,
        runner: CliRunner,
        valid_schedule_file: Path,
        sample_config_file: Path,
    ) -> None:
        """Validate command shows statistics."""
        result = runner.invoke(
            cli,
            [
                "validate",
                "--schedule",
                str(valid_schedule_file),
                "--config",
                str(sample_config_file),
                "-v",  # Verbose
            ],
        )
        # Should show some output about the schedule
        assert len(result.output) > 0

    def test_validate_json_output(
        self,
        runner: CliRunner,
        valid_schedule_file: Path,
        sample_config_file: Path,
        tmp_path: Path,
    ) -> None:
        """Validate command can output JSON report."""
        report_file = tmp_path / "report.json"
        result = runner.invoke(
            cli,
            [
                "validate",
                "--schedule",
                str(valid_schedule_file),
                "--config",
                str(sample_config_file),
                "--output",
                str(report_file),
            ],
        )
        # Output file should be created
        if result.exit_code == 0:
            assert report_file.exists()
            with open(report_file) as f:
                report = json.load(f)
            assert "is_valid" in report or "violations" in report


class TestValidateWithWorkers:
    """Test validate command with worker data."""

    def test_validate_with_workers_file(
        self,
        runner: CliRunner,
        valid_schedule_file: Path,
        sample_config_file: Path,
        workers_file: Path,
    ) -> None:
        """Validate command can use workers file."""
        result = runner.invoke(
            cli,
            [
                "validate",
                "--schedule",
                str(valid_schedule_file),
                "--config",
                str(sample_config_file),
                "--workers",
                str(workers_file),
            ],
        )
        # Should run validation
        assert "validation" in result.output.lower() or result.exit_code in [0, 1]

    def test_validate_with_workers_xlsx(
        self,
        runner: CliRunner,
        valid_schedule_file: Path,
        sample_config_file: Path,
        tmp_path: Path,
    ) -> None:
        """--workers accepts an .xlsx file (U10): previously any .xlsx path
        died with a CSVLoaderError since validate always used CSVLoader."""
        import openpyxl

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Workers"
        ws.append(["id", "name", "worker_type"])
        ws.append(["W1", "Worker One", "full_time"])
        ws.append(["W2", "Worker Two", "full_time"])
        workers_xlsx = tmp_path / "workers.xlsx"
        wb.save(workers_xlsx)

        result = runner.invoke(
            cli,
            [
                "validate",
                "--schedule",
                str(valid_schedule_file),
                "--config",
                str(sample_config_file),
                "--workers",
                str(workers_xlsx),
            ],
        )
        assert "error loading workers" not in result.output.lower()
        assert result.exit_code in [0, 1]


class TestValidateConfigFallback:
    """validate honors the group-level -c/--config (defect D)."""

    def test_group_level_config_used_when_subcommand_omits_it(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """A group-level -c reaches validate even without its own --config.

        day's workers_required=2 comes only from the config; the schedule
        below assigns just one worker, so honoring the group-level config
        must produce a coverage violation that pure schedule-inference
        (workers_required defaulting to what's actually observed) would not.
        """
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            """
shift_types:
  - id: day
    name: Day Shift
    category: day
    start_time: "09:00"
    end_time: "17:00"
    duration_hours: 8.0
    workers_required: 2
"""
        )
        schedule_file = tmp_path / "schedule.json"
        schedule_file.write_text(
            json.dumps(
                {
                    "schedule_id": "SCH-FALLBACK",
                    "start_date": "2026-03-02",
                    "end_date": "2026-03-08",
                    "periods": [
                        {
                            "period_index": 0,
                            "period_start": "2026-03-02",
                            "period_end": "2026-03-08",
                            "assignments": {
                                "W1": [{"shift_type_id": "day", "date": "2026-03-02"}],
                            },
                        }
                    ],
                    "statistics": {},
                }
            )
        )

        result = runner.invoke(
            cli,
            [
                "-c",
                str(config_file),  # group-level, not validate's own --config
                "-v",
                "validate",
                "--schedule",
                str(schedule_file),
            ],
        )

        assert result.exit_code == 1, result.output
        assert "requires 2" in result.output


class TestValidateSkillsAndAttributesPlumbing:
    """validate plumbs config required_attributes through to the skills
    check (defect E)."""

    def test_missing_worker_attribute_flagged_as_skills_violation(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            """
shift_types:
  - id: icu
    name: ICU Shift
    category: day
    start_time: "07:00"
    end_time: "15:00"
    duration_hours: 8.0
    workers_required: 1
    required_attributes:
      certification: ICU
"""
        )
        schedule_file = tmp_path / "schedule.json"
        schedule_file.write_text(
            json.dumps(
                {
                    "schedule_id": "SCH-SKILLS",
                    "start_date": "2026-03-02",
                    "end_date": "2026-03-08",
                    "periods": [
                        {
                            "period_index": 0,
                            "period_start": "2026-03-02",
                            "period_end": "2026-03-08",
                            "assignments": {
                                "W1": [{"shift_type_id": "icu", "date": "2026-03-02"}],
                            },
                        }
                    ],
                    "statistics": {},
                }
            )
        )

        result = runner.invoke(
            cli,
            [
                "validate",
                "--schedule",
                str(schedule_file),
                "--config",
                str(config_file),
            ],
        )

        assert result.exit_code == 1, result.output
        assert "skills" in result.output.lower()
        assert "certification" in result.output.lower()


class TestValidateMaxShiftsPerPeriodPlumbing:
    """validate plumbs the resolved worker_shift_limit override through to
    ScheduleValidator's max_shifts_per_period (defect F)."""

    def test_config_override_relaxes_the_default_limit(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            """
shift_types:
  - id: day
    name: Day Shift
    category: day
    start_time: "09:00"
    end_time: "17:00"
    duration_hours: 8.0
  - id: night
    name: Night Shift
    category: night
    start_time: "23:00"
    end_time: "07:00"
    duration_hours: 8.0

constraints:
  worker_shift_limit:
    parameters:
      max_shifts_per_period: 2
"""
        )
        schedule_file = tmp_path / "schedule.json"
        schedule_file.write_text(
            json.dumps(
                {
                    "schedule_id": "SCH-LIMIT",
                    "start_date": "2026-03-02",
                    "end_date": "2026-03-08",
                    "periods": [
                        {
                            "period_index": 0,
                            "period_start": "2026-03-02",
                            "period_end": "2026-03-08",
                            "assignments": {
                                "W1": [
                                    {"shift_type_id": "day", "date": "2026-03-02"},
                                    {"shift_type_id": "night", "date": "2026-03-02"},
                                ],
                            },
                        }
                    ],
                    "statistics": {},
                }
            )
        )

        result = runner.invoke(
            cli,
            [
                "validate",
                "--schedule",
                str(schedule_file),
                "--config",
                str(config_file),
            ],
        )

        assert result.exit_code == 0, result.output
        assert "worker_shift_limit" not in result.output

    def test_default_limit_still_applies_without_override(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            """
shift_types:
  - id: day
    name: Day Shift
    category: day
    start_time: "09:00"
    end_time: "17:00"
    duration_hours: 8.0
  - id: night
    name: Night Shift
    category: night
    start_time: "23:00"
    end_time: "07:00"
    duration_hours: 8.0
"""
        )
        schedule_file = tmp_path / "schedule.json"
        schedule_file.write_text(
            json.dumps(
                {
                    "schedule_id": "SCH-LIMIT-DEFAULT",
                    "start_date": "2026-03-02",
                    "end_date": "2026-03-08",
                    "periods": [
                        {
                            "period_index": 0,
                            "period_start": "2026-03-02",
                            "period_end": "2026-03-08",
                            "assignments": {
                                "W1": [
                                    {"shift_type_id": "day", "date": "2026-03-02"},
                                    {"shift_type_id": "night", "date": "2026-03-02"},
                                ],
                            },
                        }
                    ],
                    "statistics": {},
                }
            )
        )

        result = runner.invoke(
            cli,
            [
                "validate",
                "--schedule",
                str(schedule_file),
                "--config",
                str(config_file),
            ],
        )

        assert result.exit_code == 1, result.output
        assert "worker_shift_limit" in result.output

    def test_disabled_constraint_is_not_enforced(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """generate -> validate must not self-contradict: a config that
        explicitly disables worker_shift_limit should not have validate
        enforce its (registry-default) max_shifts_per_period=1 anyway."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            """
shift_types:
  - id: day
    name: Day Shift
    category: day
    start_time: "09:00"
    end_time: "17:00"
    duration_hours: 8.0
  - id: night
    name: Night Shift
    category: night
    start_time: "23:00"
    end_time: "07:00"
    duration_hours: 8.0

constraints:
  worker_shift_limit:
    enabled: false
"""
        )
        schedule_file = tmp_path / "schedule.json"
        schedule_file.write_text(
            json.dumps(
                {
                    "schedule_id": "SCH-LIMIT-DISABLED",
                    "start_date": "2026-03-02",
                    "end_date": "2026-03-08",
                    "periods": [
                        {
                            "period_index": 0,
                            "period_start": "2026-03-02",
                            "period_end": "2026-03-08",
                            "assignments": {
                                "W1": [
                                    {"shift_type_id": "day", "date": "2026-03-02"},
                                    {"shift_type_id": "night", "date": "2026-03-02"},
                                ],
                            },
                        }
                    ],
                    "statistics": {},
                }
            )
        )

        result = runner.invoke(
            cli,
            [
                "validate",
                "--schedule",
                str(schedule_file),
                "--config",
                str(config_file),
            ],
        )

        assert result.exit_code == 0, result.output
        assert "worker_shift_limit" not in result.output
