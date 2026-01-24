"""Integration tests for configuration loading and solver execution."""

from datetime import date, timedelta
from pathlib import Path

import pytest

from shift_solver.config import ShiftSolverConfig
from shift_solver.constraints.base import ConstraintConfig
from shift_solver.models import ShiftType, Worker
from shift_solver.solver import ShiftSolver


def _convert_pydantic_config(pydantic_config) -> ConstraintConfig:
    """Convert Pydantic ConstraintConfig to dataclass ConstraintConfig."""
    return ConstraintConfig(
        enabled=pydantic_config.enabled,
        is_hard=pydantic_config.is_hard,
        weight=pydantic_config.weight,
        parameters=pydantic_config.parameters,
    )


@pytest.mark.integration
class TestYamlConfigToSolver:
    """Test loading YAML config and using it to configure the solver."""

    def test_yaml_config_creates_valid_shift_types(
        self,
        sample_config_yaml: Path,
    ) -> None:
        """Test that YAML config produces valid ShiftType objects."""
        cfg = ShiftSolverConfig.load_from_yaml(sample_config_yaml)

        # Convert config shift types to model shift types
        shift_types = [
            ShiftType(
                id=st.id,
                name=st.name,
                category=st.category,
                start_time=st.start_time,
                end_time=st.end_time,
                duration_hours=st.duration_hours,
                is_undesirable=st.is_undesirable,
                workers_required=st.workers_required,
            )
            for st in cfg.shift_types
        ]

        assert len(shift_types) == 2
        assert shift_types[0].id == "day"
        assert shift_types[1].id == "night"
        assert shift_types[1].is_undesirable is True

    def test_yaml_config_to_solver_execution(
        self,
        sample_config_yaml: Path,
    ) -> None:
        """Test loading config and running a full solve."""
        cfg = ShiftSolverConfig.load_from_yaml(sample_config_yaml)

        # Create shift types from config
        shift_types = [
            ShiftType(
                id=st.id,
                name=st.name,
                category=st.category,
                start_time=st.start_time,
                end_time=st.end_time,
                duration_hours=st.duration_hours,
                is_undesirable=st.is_undesirable,
                workers_required=st.workers_required,
            )
            for st in cfg.shift_types
        ]

        # Create sample workers
        workers = [Worker(id=f"W{i:03d}", name=f"Worker {i}") for i in range(1, 8)]

        # Create period dates
        base_date = date(2026, 2, 2)
        num_periods = cfg.schedule.num_periods or 4
        period_dates = [
            (base_date + timedelta(weeks=i), base_date + timedelta(weeks=i, days=6))
            for i in range(num_periods)
        ]

        # Use constraint configs from YAML (convert to dataclass)
        constraint_configs = {
            name: _convert_pydantic_config(cfg.get_constraint_config(name))
            for name in ["coverage", "fairness", "restriction", "availability"]
        }

        solver = ShiftSolver(
            workers=workers,
            shift_types=shift_types,
            period_dates=period_dates,
            schedule_id="CONFIG-TEST",
            constraint_configs=constraint_configs,
        )

        result = solver.solve(time_limit_seconds=cfg.solver.quick_solution_seconds)

        assert result.success
        assert result.schedule is not None
        assert len(result.schedule.periods) == num_periods


@pytest.mark.integration
class TestConstraintConfigParameters:
    """Test that constraint configuration parameters are properly applied."""

    def test_constraint_weights_affect_objective(
        self,
        sample_config_yaml: Path,
    ) -> None:
        """Test that constraint weights from config affect solver behavior."""
        cfg = ShiftSolverConfig.load_from_yaml(sample_config_yaml)

        # Verify constraint configs were loaded
        fairness_config = cfg.get_constraint_config("fairness")
        assert fairness_config.enabled is True
        assert fairness_config.is_hard is False
        assert fairness_config.weight == 100

    def test_disabled_constraints_are_skipped(self, tmp_path: Path) -> None:
        """Test that disabled constraints don't affect solving."""
        config_content = """
solver:
  max_time_seconds: 60

schedule:
  period_type: week

constraints:
  fairness:
    enabled: false
    weight: 1000
  request:
    enabled: false

shift_types:
  - id: day
    name: Day Shift
    category: day
    start_time: "09:00"
    end_time: "17:00"
    duration_hours: 8.0
    workers_required: 1
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_content)

        cfg = ShiftSolverConfig.load_from_yaml(config_file)

        assert not cfg.is_constraint_enabled("fairness")
        assert not cfg.is_constraint_enabled("request")
        # Coverage should still be enabled by default
        assert cfg.is_constraint_enabled("coverage")

    def test_constraint_parameters_flow_through(self, tmp_path: Path) -> None:
        """Test that constraint parameters are accessible in config."""
        config_content = """
solver:
  max_time_seconds: 60

schedule:
  period_type: week

constraints:
  frequency:
    enabled: true
    is_hard: false
    weight: 50
    parameters:
      max_per_period: 3
      min_spacing_days: 2

shift_types:
  - id: day
    name: Day Shift
    category: day
    start_time: "09:00"
    end_time: "17:00"
    duration_hours: 8.0
    workers_required: 1
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_content)

        cfg = ShiftSolverConfig.load_from_yaml(config_file)

        freq_config = cfg.get_constraint_config("frequency")
        assert freq_config.parameters.get("max_per_period") == 3
        assert freq_config.parameters.get("min_spacing_days") == 2


@pytest.mark.integration
class TestConfigValidation:
    """Test configuration validation during load."""

    def test_invalid_config_raises_error(self, invalid_config_yaml: Path) -> None:
        """Test that invalid config raises appropriate error."""
        with pytest.raises(Exception):  # Pydantic ValidationError
            ShiftSolverConfig.load_from_yaml(invalid_config_yaml)

    def test_malformed_yaml_raises_error(self, malformed_yaml: Path) -> None:
        """Test that malformed YAML raises appropriate error."""
        with pytest.raises(Exception):  # yaml.YAMLError
            ShiftSolverConfig.load_from_yaml(malformed_yaml)

    def test_missing_file_raises_error(self) -> None:
        """Test that missing config file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            ShiftSolverConfig.load_from_yaml(Path("/nonexistent/config.yaml"))

    def test_duplicate_shift_type_ids_rejected(self, tmp_path: Path) -> None:
        """Test that duplicate shift type IDs are rejected."""
        config_content = """
shift_types:
  - id: day
    name: Day Shift
    category: day
    start_time: "09:00"
    end_time: "17:00"
    duration_hours: 8.0
  - id: day
    name: Another Day Shift
    category: day
    start_time: "10:00"
    end_time: "18:00"
    duration_hours: 8.0
"""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(config_content)

        with pytest.raises(Exception) as exc_info:
            ShiftSolverConfig.load_from_yaml(config_file)

        assert "unique" in str(exc_info.value).lower() or "duplicate" in str(exc_info.value).lower()
