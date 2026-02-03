"""Comprehensive tests for configuration loading and validation.

Tests edge cases in YAML parsing, time parsing, constraint parameters,
and default value application.
"""

from datetime import time
from pathlib import Path

import pytest
from pydantic import ValidationError

from shift_solver.config import ShiftSolverConfig


class TestMinimalConfiguration:
    """Test minimal configuration requirements."""

    def test_minimal_config_only_shift_types(self, tmp_path: Path) -> None:
        """Config with only shift_types should work with defaults."""
        config_content = """
shift_types:
  - id: day
    name: Day Shift
    category: day
    start_time: "09:00"
    end_time: "17:00"
    duration_hours: 8.0
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_content)

        cfg = ShiftSolverConfig.load_from_yaml(config_file)

        # Defaults should be applied
        assert cfg.solver.max_time_seconds == 3600
        assert cfg.solver.num_workers == 8
        assert cfg.schedule.period_type == "week"
        assert cfg.database.path == "shift_solver.db"
        assert len(cfg.shift_types) == 1

    def test_single_shift_type_config(self, tmp_path: Path) -> None:
        """Single shift type configuration should be valid."""
        config_content = """
shift_types:
  - id: shift1
    name: Single Shift
    category: any
    start_time: "08:00"
    end_time: "16:00"
    duration_hours: 8.0
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_content)

        cfg = ShiftSolverConfig.load_from_yaml(config_file)
        assert len(cfg.shift_types) == 1


class TestFullConfiguration:
    """Test full configuration with all fields."""

    def test_all_fields_specified(self, tmp_path: Path) -> None:
        """Configuration with all fields explicitly set."""
        config_content = """
solver:
  max_time_seconds: 7200
  num_workers: 16
  quick_solution_seconds: 120

schedule:
  period_type: biweek
  num_periods: 8

constraints:
  coverage:
    enabled: true
    is_hard: true
  restriction:
    enabled: true
    is_hard: true
  availability:
    enabled: true
    is_hard: true
  fairness:
    enabled: true
    is_hard: false
    weight: 200
    parameters:
      max_deviation: 2
  request:
    enabled: true
    is_hard: false
    weight: 150
  frequency:
    enabled: false
    weight: 50

shift_types:
  - id: morning
    name: Morning Shift
    category: day
    start_time: "06:00"
    end_time: "14:00"
    duration_hours: 8.0
    workers_required: 3
  - id: afternoon
    name: Afternoon Shift
    category: day
    start_time: "14:00"
    end_time: "22:00"
    duration_hours: 8.0
    workers_required: 2
  - id: night
    name: Night Shift
    category: night
    start_time: "22:00"
    end_time: "06:00"
    duration_hours: 8.0
    workers_required: 1
    is_undesirable: true

database:
  path: custom/path/scheduler.db

logging:
  level: DEBUG
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_content)

        cfg = ShiftSolverConfig.load_from_yaml(config_file)

        assert cfg.solver.max_time_seconds == 7200
        assert cfg.solver.num_workers == 16
        assert cfg.schedule.period_type == "biweek"
        assert cfg.schedule.num_periods == 8
        assert len(cfg.shift_types) == 3
        assert cfg.database.path == "custom/path/scheduler.db"
        assert cfg.logging.level == "DEBUG"

        # Check constraints
        assert cfg.constraints["fairness"].weight == 200
        assert cfg.constraints["fairness"].parameters.get("max_deviation") == 2
        assert cfg.constraints["frequency"].enabled is False


class TestDefaultApplication:
    """Test that defaults are properly applied for missing optional fields."""

    def test_default_constraint_config(self, tmp_path: Path) -> None:
        """Constraints not specified should get default config."""
        config_content = """
shift_types:
  - id: day
    name: Day
    category: day
    start_time: "09:00"
    end_time: "17:00"
    duration_hours: 8.0
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_content)

        cfg = ShiftSolverConfig.load_from_yaml(config_file)

        # Coverage should be enabled by default
        coverage = cfg.get_constraint_config("coverage")
        assert coverage.enabled is True
        assert coverage.is_hard is True

    def test_shift_type_defaults(self, tmp_path: Path) -> None:
        """Shift types should have proper defaults."""
        config_content = """
shift_types:
  - id: minimal
    name: Minimal
    category: day
    start_time: "09:00"
    end_time: "17:00"
    duration_hours: 8.0
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_content)

        cfg = ShiftSolverConfig.load_from_yaml(config_file)

        shift = cfg.shift_types[0]
        assert shift.workers_required == 1
        assert shift.is_undesirable is False


class TestInvalidConfigurations:
    """Test error handling for invalid configurations."""

    def test_missing_required_field_id(self, tmp_path: Path) -> None:
        """Shift type without id should fail."""
        config_content = """
shift_types:
  - name: No ID Shift
    category: day
    start_time: "09:00"
    end_time: "17:00"
    duration_hours: 8.0
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_content)

        with pytest.raises(ValidationError):
            ShiftSolverConfig.load_from_yaml(config_file)

    def test_wrong_type_integer_for_string(self, tmp_path: Path) -> None:
        """Integer where string expected should fail validation."""
        config_content = """
shift_types:
  - id: 123
    name: Numeric ID
    category: day
    start_time: "09:00"
    end_time: "17:00"
    duration_hours: 8.0
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_content)

        # Pydantic requires strings, not integers
        with pytest.raises(ValidationError):
            ShiftSolverConfig.load_from_yaml(config_file)

    def test_negative_weight(self, tmp_path: Path) -> None:
        """Negative weight should fail validation."""
        config_content = """
constraints:
  fairness:
    enabled: true
    weight: -100

shift_types:
  - id: day
    name: Day
    category: day
    start_time: "09:00"
    end_time: "17:00"
    duration_hours: 8.0
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_content)

        with pytest.raises(ValidationError):
            ShiftSolverConfig.load_from_yaml(config_file)

    def test_negative_duration(self, tmp_path: Path) -> None:
        """Negative duration should fail."""
        config_content = """
shift_types:
  - id: day
    name: Day
    category: day
    start_time: "09:00"
    end_time: "17:00"
    duration_hours: -8.0
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_content)

        with pytest.raises(ValidationError):
            ShiftSolverConfig.load_from_yaml(config_file)

    def test_zero_workers_required(self, tmp_path: Path) -> None:
        """Zero workers required should fail."""
        config_content = """
shift_types:
  - id: day
    name: Day
    category: day
    start_time: "09:00"
    end_time: "17:00"
    duration_hours: 8.0
    workers_required: 0
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_content)

        with pytest.raises(ValidationError):
            ShiftSolverConfig.load_from_yaml(config_file)


class TestYamlEdgeCases:
    """Test edge cases in YAML parsing."""

    def test_empty_file(self, tmp_path: Path) -> None:
        """Empty YAML file should fail validation."""
        config_file = tmp_path / "empty.yaml"
        config_file.write_text("")

        with pytest.raises((ValidationError, TypeError)):
            ShiftSolverConfig.load_from_yaml(config_file)

    def test_yaml_with_comments(self, tmp_path: Path) -> None:
        """YAML comments should be ignored."""
        config_content = """
# Main configuration
shift_types:
  # Day shift configuration
  - id: day  # Shift identifier
    name: Day Shift
    category: day
    start_time: "09:00"  # Start at 9 AM
    end_time: "17:00"
    duration_hours: 8.0
"""
        config_file = tmp_path / "commented.yaml"
        config_file.write_text(config_content)

        cfg = ShiftSolverConfig.load_from_yaml(config_file)
        assert len(cfg.shift_types) == 1

    def test_unicode_in_names(self, tmp_path: Path) -> None:
        """Unicode characters in names should be supported."""
        config_content = """
shift_types:
  - id: day
    name: "日勤シフト"  # Japanese: Day shift
    category: day
    start_time: "09:00"
    end_time: "17:00"
    duration_hours: 8.0
"""
        config_file = tmp_path / "unicode.yaml"
        config_file.write_text(config_content)

        cfg = ShiftSolverConfig.load_from_yaml(config_file)
        assert cfg.shift_types[0].name == "日勤シフト"

    def test_special_yaml_values_null(self, tmp_path: Path) -> None:
        """YAML null values should be handled."""
        config_content = """
shift_types:
  - id: day
    name: Day Shift
    category: day
    start_time: "09:00"
    end_time: "17:00"
    duration_hours: 8.0

database:
  path: null  # Should use default
"""
        config_file = tmp_path / "null_values.yaml"
        config_file.write_text(config_content)

        # Should either use default or fail gracefully
        try:
            cfg = ShiftSolverConfig.load_from_yaml(config_file)
            # If it loads, check path is either null or default
            assert cfg.database.path is None or cfg.database.path == "shift_solver.db"
        except ValidationError:
            pass  # Also acceptable

    def test_yaml_boolean_variations(self, tmp_path: Path) -> None:
        """YAML boolean variations (true, yes, on) should work."""
        config_content = """
constraints:
  coverage:
    enabled: yes
    is_hard: true
  fairness:
    enabled: on
    is_hard: false

shift_types:
  - id: day
    name: Day
    category: day
    start_time: "09:00"
    end_time: "17:00"
    duration_hours: 8.0
    is_undesirable: no
"""
        config_file = tmp_path / "bools.yaml"
        config_file.write_text(config_content)

        cfg = ShiftSolverConfig.load_from_yaml(config_file)
        assert cfg.constraints["coverage"].enabled is True
        assert cfg.constraints["fairness"].enabled is True
        assert cfg.shift_types[0].is_undesirable is False


class TestTimeParsing:
    """Test time parsing edge cases."""

    def test_valid_time_formats(self, tmp_path: Path) -> None:
        """Test various valid time formats."""
        config_content = """
shift_types:
  - id: early
    name: Early
    category: day
    start_time: "00:00"
    end_time: "08:00"
    duration_hours: 8.0
  - id: late
    name: Late
    category: night
    start_time: "23:59"
    end_time: "07:59"
    duration_hours: 8.0
"""
        config_file = tmp_path / "times.yaml"
        config_file.write_text(config_content)

        cfg = ShiftSolverConfig.load_from_yaml(config_file)
        assert cfg.shift_types[0].start_time == time(0, 0)
        assert cfg.shift_types[1].start_time == time(23, 59)

    def test_invalid_time_hour_25(self, tmp_path: Path) -> None:
        """Hour 25 should fail."""
        config_content = """
shift_types:
  - id: bad
    name: Bad
    category: day
    start_time: "25:00"
    end_time: "17:00"
    duration_hours: 8.0
"""
        config_file = tmp_path / "bad_time.yaml"
        config_file.write_text(config_content)

        with pytest.raises(ValueError, match="Invalid time"):
            ShiftSolverConfig.load_from_yaml(config_file)

    def test_invalid_time_minute_60(self, tmp_path: Path) -> None:
        """Minute 60 should fail."""
        config_content = """
shift_types:
  - id: bad
    name: Bad
    category: day
    start_time: "12:60"
    end_time: "17:00"
    duration_hours: 8.0
"""
        config_file = tmp_path / "bad_minute.yaml"
        config_file.write_text(config_content)

        with pytest.raises(ValueError, match="Invalid time"):
            ShiftSolverConfig.load_from_yaml(config_file)

    def test_invalid_time_format_no_colon(self, tmp_path: Path) -> None:
        """Time without colon should fail."""
        config_content = """
shift_types:
  - id: bad
    name: Bad
    category: day
    start_time: "1200"
    end_time: "17:00"
    duration_hours: 8.0
"""
        config_file = tmp_path / "no_colon.yaml"
        config_file.write_text(config_content)

        with pytest.raises(ValueError, match="Invalid time"):
            ShiftSolverConfig.load_from_yaml(config_file)

    def test_invalid_time_text_noon(self, tmp_path: Path) -> None:
        """Text 'noon' should fail."""
        config_content = """
shift_types:
  - id: bad
    name: Bad
    category: day
    start_time: "noon"
    end_time: "17:00"
    duration_hours: 8.0
"""
        config_file = tmp_path / "noon.yaml"
        config_file.write_text(config_content)

        with pytest.raises(ValueError, match="Invalid time"):
            ShiftSolverConfig.load_from_yaml(config_file)


class TestConstraintParameters:
    """Test constraint parameter handling."""

    def test_unknown_parameter_accepted(self, tmp_path: Path) -> None:
        """Extra parameters in constraint config should be stored."""
        config_content = """
constraints:
  fairness:
    enabled: true
    is_hard: false
    weight: 100
    parameters:
      custom_param: 42
      another_param: "value"

shift_types:
  - id: day
    name: Day
    category: day
    start_time: "09:00"
    end_time: "17:00"
    duration_hours: 8.0
"""
        config_file = tmp_path / "params.yaml"
        config_file.write_text(config_content)

        cfg = ShiftSolverConfig.load_from_yaml(config_file)
        params = cfg.constraints["fairness"].parameters

        assert params.get("custom_param") == 42
        assert params.get("another_param") == "value"

    def test_nested_parameters(self, tmp_path: Path) -> None:
        """Nested parameter structures should be preserved."""
        config_content = """
constraints:
  frequency:
    enabled: true
    parameters:
      limits:
        day: 3
        night: 2
      windows:
        short: 7
        long: 14

shift_types:
  - id: day
    name: Day
    category: day
    start_time: "09:00"
    end_time: "17:00"
    duration_hours: 8.0
"""
        config_file = tmp_path / "nested.yaml"
        config_file.write_text(config_content)

        cfg = ShiftSolverConfig.load_from_yaml(config_file)
        params = cfg.constraints["frequency"].parameters

        assert params["limits"]["day"] == 3
        assert params["windows"]["long"] == 14


class TestDuplicateShiftTypes:
    """Test duplicate shift type ID detection."""

    def test_duplicate_ids_rejected(self, tmp_path: Path) -> None:
        """Duplicate shift type IDs should be rejected."""
        config_content = """
shift_types:
  - id: day
    name: Day 1
    category: day
    start_time: "09:00"
    end_time: "17:00"
    duration_hours: 8.0
  - id: day
    name: Day 2
    category: day
    start_time: "10:00"
    end_time: "18:00"
    duration_hours: 8.0
"""
        config_file = tmp_path / "dupes.yaml"
        config_file.write_text(config_content)

        with pytest.raises(Exception) as exc_info:
            ShiftSolverConfig.load_from_yaml(config_file)

        # Should mention uniqueness
        assert "unique" in str(exc_info.value).lower() or "duplicate" in str(exc_info.value).lower()
