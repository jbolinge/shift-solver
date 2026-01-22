"""Tests for configuration schema."""

from datetime import time
from pathlib import Path
from tempfile import NamedTemporaryFile

import pytest
import yaml

from shift_solver.config.schema import (
    ConstraintConfig,
    ShiftSolverConfig,
    ShiftTypeConfig,
    SolverConfig,
)


class TestSolverConfig:
    """Tests for SolverConfig."""

    def test_default_values(self) -> None:
        """SolverConfig has sensible defaults."""
        config = SolverConfig()

        assert config.max_time_seconds == 3600
        assert config.num_workers == 8
        assert config.quick_solution_seconds == 60

    def test_custom_values(self) -> None:
        """SolverConfig accepts custom values."""
        config = SolverConfig(
            max_time_seconds=7200,
            num_workers=4,
            quick_solution_seconds=30,
        )

        assert config.max_time_seconds == 7200
        assert config.num_workers == 4
        assert config.quick_solution_seconds == 30


class TestSolverConfigValidation:
    """Tests for SolverConfig validation."""

    def test_max_time_must_be_positive(self) -> None:
        """max_time_seconds must be > 0."""
        with pytest.raises(ValueError):
            SolverConfig(max_time_seconds=0)

    def test_num_workers_must_be_positive(self) -> None:
        """num_workers must be >= 1."""
        with pytest.raises(ValueError):
            SolverConfig(num_workers=0)


class TestConstraintConfig:
    """Tests for ConstraintConfig."""

    def test_default_values(self) -> None:
        """ConstraintConfig has sensible defaults."""
        config = ConstraintConfig()

        assert config.enabled is True
        assert config.is_hard is True
        assert config.weight == 100
        assert config.parameters == {}

    def test_soft_constraint_config(self) -> None:
        """Configure a soft constraint with custom weight."""
        config = ConstraintConfig(
            enabled=True,
            is_hard=False,
            weight=500,
            parameters={"max_deviation": 2},
        )

        assert config.is_hard is False
        assert config.weight == 500
        assert config.parameters["max_deviation"] == 2


class TestConstraintConfigValidation:
    """Tests for ConstraintConfig validation."""

    def test_weight_must_be_non_negative(self) -> None:
        """weight must be >= 0."""
        with pytest.raises(ValueError):
            ConstraintConfig(weight=-1)


class TestShiftTypeConfig:
    """Tests for ShiftTypeConfig."""

    def test_create_shift_type_config(self) -> None:
        """Create a shift type configuration."""
        config = ShiftTypeConfig(
            id="day_shift",
            name="Day Shift",
            category="day",
            start_time=time(7, 0),
            end_time=time(15, 0),
            duration_hours=8.0,
        )

        assert config.id == "day_shift"
        assert config.name == "Day Shift"
        assert config.start_time == time(7, 0)
        assert config.workers_required == 1  # Default

    def test_undesirable_shift_config(self) -> None:
        """Configure an undesirable shift type."""
        config = ShiftTypeConfig(
            id="night_shift",
            name="Night Shift",
            category="night",
            start_time=time(23, 0),
            end_time=time(7, 0),
            duration_hours=8.0,
            is_undesirable=True,
            workers_required=2,
        )

        assert config.is_undesirable is True
        assert config.workers_required == 2


class TestShiftTypeConfigValidation:
    """Tests for ShiftTypeConfig validation."""

    def test_id_cannot_be_empty(self) -> None:
        """Shift type id cannot be empty."""
        with pytest.raises(ValueError):
            ShiftTypeConfig(
                id="",
                name="Test",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
            )

    def test_duration_must_be_positive(self) -> None:
        """duration_hours must be > 0."""
        with pytest.raises(ValueError):
            ShiftTypeConfig(
                id="test",
                name="Test",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=0,
            )


class TestShiftSolverConfig:
    """Tests for ShiftSolverConfig (main config)."""

    def test_create_minimal_config(self) -> None:
        """Create config with minimal required fields."""
        shift_types = [
            ShiftTypeConfig(
                id="day",
                name="Day",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
            )
        ]

        config = ShiftSolverConfig(shift_types=shift_types)

        assert config.solver.max_time_seconds == 3600
        assert config.schedule.period_type == "week"
        assert len(config.shift_types) == 1
        assert config.database.path == "shift_solver.db"

    def test_create_full_config(self) -> None:
        """Create config with all fields."""
        shift_types = [
            ShiftTypeConfig(
                id="day",
                name="Day",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
            )
        ]

        constraints = {
            "coverage": ConstraintConfig(enabled=True, is_hard=True),
            "fairness": ConstraintConfig(enabled=True, is_hard=False, weight=1000),
        }

        config = ShiftSolverConfig(
            shift_types=shift_types,
            solver=SolverConfig(max_time_seconds=7200),
            constraints=constraints,
        )

        assert config.solver.max_time_seconds == 7200
        assert config.constraints["coverage"].is_hard is True
        assert config.constraints["fairness"].weight == 1000


class TestShiftSolverConfigValidation:
    """Tests for ShiftSolverConfig validation."""

    def test_shift_types_must_have_unique_ids(self) -> None:
        """Shift type IDs must be unique."""
        shift_types = [
            ShiftTypeConfig(
                id="day",
                name="Day 1",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
            ),
            ShiftTypeConfig(
                id="day",  # Duplicate ID
                name="Day 2",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),
                duration_hours=8.0,
            ),
        ]

        with pytest.raises(ValueError, match="unique"):
            ShiftSolverConfig(shift_types=shift_types)


class TestConfigLoading:
    """Tests for loading config from YAML."""

    def test_load_from_yaml(self) -> None:
        """Load config from YAML file."""
        yaml_content = """
solver:
  max_time_seconds: 1800
  num_workers: 4

schedule:
  period_type: week

constraints:
  coverage:
    enabled: true
    is_hard: true
  fairness:
    enabled: true
    is_hard: false
    weight: 500

shift_types:
  - id: day_shift
    name: Day Shift
    category: day
    start_time: "07:00"
    end_time: "15:00"
    duration_hours: 8.0
    workers_required: 2
  - id: night_shift
    name: Night Shift
    category: night
    start_time: "23:00"
    end_time: "07:00"
    duration_hours: 8.0
    is_undesirable: true

database:
  path: custom.db
"""

        with NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()

            config = ShiftSolverConfig.load_from_yaml(Path(f.name))

        assert config.solver.max_time_seconds == 1800
        assert config.solver.num_workers == 4
        assert len(config.shift_types) == 2
        assert config.shift_types[0].id == "day_shift"
        assert config.shift_types[1].is_undesirable is True
        assert config.constraints["fairness"].weight == 500
        assert config.database.path == "custom.db"

    def test_load_with_defaults(self) -> None:
        """Load minimal config and verify defaults are applied."""
        yaml_content = """
shift_types:
  - id: day
    name: Day
    category: day
    start_time: "09:00"
    end_time: "17:00"
    duration_hours: 8.0
"""

        with NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()

            config = ShiftSolverConfig.load_from_yaml(Path(f.name))

        # Defaults should be applied
        assert config.solver.max_time_seconds == 3600
        assert config.schedule.period_type == "week"
        assert config.database.path == "shift_solver.db"
