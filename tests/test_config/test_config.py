"""Tests for configuration schema."""

from datetime import time
from pathlib import Path
from tempfile import NamedTemporaryFile

import pytest

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


class TestTimeParsingValidation:
    """Tests for time parsing validation (scheduler-52)."""

    def test_malformed_time_no_colon(self) -> None:
        """Test error on time without colon separator."""
        with pytest.raises(ValueError, match="Invalid time format.*14.*must be HH:MM"):
            ShiftTypeConfig(
                id="test",
                name="Test",
                category="day",
                start_time="14",  # type: ignore
                end_time="17:00",  # type: ignore
                duration_hours=8.0,
            )

    def test_malformed_time_invalid_hour(self) -> None:
        """Test error on time with invalid hour."""
        with pytest.raises(ValueError, match="Invalid time.*25:00"):
            ShiftTypeConfig(
                id="test",
                name="Test",
                category="day",
                start_time="25:00",  # type: ignore
                end_time="17:00",  # type: ignore
                duration_hours=8.0,
            )

    def test_malformed_time_text(self) -> None:
        """Test error on text time value."""
        with pytest.raises(ValueError, match="Invalid time format.*abc"):
            ShiftTypeConfig(
                id="test",
                name="Test",
                category="day",
                start_time="abc",  # type: ignore
                end_time="17:00",  # type: ignore
                duration_hours=8.0,
            )

    def test_malformed_time_invalid_minute(self) -> None:
        """Test error on time with invalid minute."""
        with pytest.raises(ValueError, match="Invalid time.*14:61"):
            ShiftTypeConfig(
                id="test",
                name="Test",
                category="day",
                start_time="14:61",  # type: ignore
                end_time="17:00",  # type: ignore
                duration_hours=8.0,
            )

    def test_valid_time_parsing(self) -> None:
        """Test valid time parsing works correctly."""
        config = ShiftTypeConfig(
            id="test",
            name="Test",
            category="day",
            start_time="09:30",  # type: ignore
            end_time="17:45",  # type: ignore
            duration_hours=8.0,
        )
        assert config.start_time == time(9, 30)
        assert config.end_time == time(17, 45)


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


class TestShiftFrequencyConfig:
    """Tests for shift_frequency constraint configuration (scheduler-93)."""

    def test_load_shift_frequency_config(self) -> None:
        """Load config with shift_frequency constraint parameters."""
        yaml_content = """
shift_types:
  - id: mvsc_day
    name: MVSC Day
    category: day
    start_time: "07:00"
    end_time: "15:00"
    duration_hours: 8.0
  - id: mvsc_night
    name: MVSC Night
    category: night
    start_time: "23:00"
    end_time: "07:00"
    duration_hours: 8.0

constraints:
  shift_frequency:
    enabled: true
    is_hard: false
    weight: 500
    parameters:
      requirements:
        - worker_id: "Olinger"
          shift_types: ["mvsc_day", "mvsc_night"]
          max_periods_between: 4
        - worker_id: "Beckley"
          shift_types: ["mvsc_day"]
          max_periods_between: 2
"""

        with NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()

            config = ShiftSolverConfig.load_from_yaml(Path(f.name))

        assert "shift_frequency" in config.constraints
        sf_config = config.constraints["shift_frequency"]
        assert sf_config.enabled is True
        assert sf_config.is_hard is False
        assert sf_config.weight == 500
        assert "requirements" in sf_config.parameters
        reqs = sf_config.parameters["requirements"]
        assert len(reqs) == 2
        assert reqs[0]["worker_id"] == "Olinger"
        assert reqs[0]["shift_types"] == ["mvsc_day", "mvsc_night"]
        assert reqs[0]["max_periods_between"] == 4

    def test_shift_frequency_parameters_model_valid(self) -> None:
        """Test ShiftFrequencyParametersConfig validation with valid data."""
        from shift_solver.config.schema import ShiftFrequencyParametersConfig

        params = ShiftFrequencyParametersConfig(
            requirements=[
                {
                    "worker_id": "W001",
                    "shift_types": ["day", "night"],
                    "max_periods_between": 4,
                }
            ]
        )
        assert len(params.requirements) == 1
        assert params.requirements[0].worker_id == "W001"
        assert params.requirements[0].shift_types == ["day", "night"]
        assert params.requirements[0].max_periods_between == 4

    def test_shift_frequency_requirement_config_validation(self) -> None:
        """Test validation of individual requirement config."""
        from shift_solver.config.schema import ShiftFrequencyRequirementConfig

        req = ShiftFrequencyRequirementConfig(
            worker_id="W001",
            shift_types=["day_shift"],
            max_periods_between=2,
        )
        assert req.worker_id == "W001"
        assert req.max_periods_between == 2

    def test_shift_frequency_requirement_max_periods_must_be_positive(self) -> None:
        """max_periods_between must be > 0."""
        from pydantic import ValidationError

        from shift_solver.config.schema import ShiftFrequencyRequirementConfig

        with pytest.raises(ValidationError):
            ShiftFrequencyRequirementConfig(
                worker_id="W001",
                shift_types=["day_shift"],
                max_periods_between=0,
            )

    def test_shift_frequency_requirement_shift_types_required(self) -> None:
        """shift_types must not be empty."""
        from pydantic import ValidationError

        from shift_solver.config.schema import ShiftFrequencyRequirementConfig

        with pytest.raises(ValidationError):
            ShiftFrequencyRequirementConfig(
                worker_id="W001",
                shift_types=[],
                max_periods_between=4,
            )

    def test_parse_shift_frequency_requirements(self) -> None:
        """Test parsing config dict to ShiftFrequencyRequirement objects."""
        from shift_solver.config.schema import parse_shift_frequency_requirements
        from shift_solver.models import ShiftFrequencyRequirement

        params = {
            "requirements": [
                {
                    "worker_id": "Olinger",
                    "shift_types": ["mvsc_day", "mvsc_night"],
                    "max_periods_between": 4,
                },
                {
                    "worker_id": "Beckley",
                    "shift_types": ["stf_day"],
                    "max_periods_between": 2,
                },
            ]
        }

        reqs = parse_shift_frequency_requirements(params)
        assert len(reqs) == 2
        assert all(isinstance(r, ShiftFrequencyRequirement) for r in reqs)
        assert reqs[0].worker_id == "Olinger"
        assert reqs[0].shift_types == frozenset(["mvsc_day", "mvsc_night"])
        assert reqs[0].max_periods_between == 4
        assert reqs[1].worker_id == "Beckley"

    def test_parse_shift_frequency_requirements_empty(self) -> None:
        """Return empty list when no requirements in parameters."""
        from shift_solver.config.schema import parse_shift_frequency_requirements

        assert parse_shift_frequency_requirements({}) == []
        assert parse_shift_frequency_requirements({"requirements": []}) == []
        assert parse_shift_frequency_requirements(None) == []


class TestShiftOrderPreferenceConfig:
    """Tests for shift_order_preference constraint configuration."""

    def test_valid_rule_config(self) -> None:
        """Test valid ShiftOrderRuleConfig creation."""
        from shift_solver.config.schema import ShiftOrderRuleConfig

        rule = ShiftOrderRuleConfig(
            rule_id="weekend_then_night",
            trigger_type="category",
            trigger_value="weekend",
            direction="after",
            preferred_type="category",
            preferred_value="night",
            priority=2,
        )
        assert rule.rule_id == "weekend_then_night"
        assert rule.trigger_type == "category"
        assert rule.trigger_value == "weekend"
        assert rule.direction == "after"
        assert rule.preferred_type == "category"
        assert rule.preferred_value == "night"
        assert rule.priority == 2
        assert rule.worker_ids is None

    def test_unavailability_rule_config(self) -> None:
        """Test unavailability trigger (trigger_value optional)."""
        from shift_solver.config.schema import ShiftOrderRuleConfig

        rule = ShiftOrderRuleConfig(
            rule_id="night_before_vacation",
            trigger_type="unavailability",
            direction="before",
            preferred_type="shift_type",
            preferred_value="night_shift",
        )
        assert rule.trigger_type == "unavailability"
        assert rule.trigger_value is None

    def test_trigger_value_required_for_shift_type(self) -> None:
        """trigger_value is required for shift_type trigger."""
        from pydantic import ValidationError

        from shift_solver.config.schema import ShiftOrderRuleConfig

        with pytest.raises(ValidationError, match="trigger_value"):
            ShiftOrderRuleConfig(
                rule_id="test",
                trigger_type="shift_type",
                trigger_value=None,
                direction="after",
                preferred_type="shift_type",
                preferred_value="night_shift",
            )

    def test_trigger_value_required_for_category(self) -> None:
        """trigger_value is required for category trigger."""
        from pydantic import ValidationError

        from shift_solver.config.schema import ShiftOrderRuleConfig

        with pytest.raises(ValidationError, match="trigger_value"):
            ShiftOrderRuleConfig(
                rule_id="test",
                trigger_type="category",
                trigger_value=None,
                direction="after",
                preferred_type="shift_type",
                preferred_value="night_shift",
            )

    def test_rule_with_worker_ids(self) -> None:
        """Test rule scoped to specific workers."""
        from shift_solver.config.schema import ShiftOrderRuleConfig

        rule = ShiftOrderRuleConfig(
            rule_id="test",
            trigger_type="shift_type",
            trigger_value="day_shift",
            direction="after",
            preferred_type="shift_type",
            preferred_value="night_shift",
            worker_ids=["W001", "W002"],
        )
        assert rule.worker_ids == ["W001", "W002"]

    def test_parameters_config(self) -> None:
        """Test ShiftOrderPreferenceParametersConfig with rules."""
        from shift_solver.config.schema import ShiftOrderPreferenceParametersConfig

        params = ShiftOrderPreferenceParametersConfig(
            rules=[
                {
                    "rule_id": "weekend_then_night",
                    "trigger_type": "category",
                    "trigger_value": "weekend",
                    "direction": "after",
                    "preferred_type": "category",
                    "preferred_value": "night",
                }
            ]
        )
        assert len(params.rules) == 1
        assert params.rules[0].rule_id == "weekend_then_night"

    def test_parse_shift_order_preferences(self) -> None:
        """Test parsing config dict to ShiftOrderPreference objects."""
        from shift_solver.config.schema import parse_shift_order_preferences
        from shift_solver.models import ShiftOrderPreference

        params = {
            "rules": [
                {
                    "rule_id": "weekend_then_night",
                    "trigger_type": "category",
                    "trigger_value": "weekend",
                    "direction": "after",
                    "preferred_type": "category",
                    "preferred_value": "night",
                    "priority": 2,
                },
                {
                    "rule_id": "night_before_vacation",
                    "trigger_type": "unavailability",
                    "direction": "before",
                    "preferred_type": "shift_type",
                    "preferred_value": "night_shift",
                },
            ]
        }

        prefs = parse_shift_order_preferences(params)
        assert len(prefs) == 2
        assert all(isinstance(p, ShiftOrderPreference) for p in prefs)
        assert prefs[0].rule_id == "weekend_then_night"
        assert prefs[0].trigger_type == "category"
        assert prefs[0].priority == 2
        assert prefs[0].worker_ids is None
        assert prefs[1].rule_id == "night_before_vacation"
        assert prefs[1].trigger_type == "unavailability"
        assert prefs[1].trigger_value is None

    def test_parse_shift_order_preferences_with_worker_ids(self) -> None:
        """Test parsing with worker_ids."""
        from shift_solver.config.schema import parse_shift_order_preferences

        params = {
            "rules": [
                {
                    "rule_id": "test",
                    "trigger_type": "shift_type",
                    "trigger_value": "day_shift",
                    "direction": "after",
                    "preferred_type": "shift_type",
                    "preferred_value": "night_shift",
                    "worker_ids": ["W001", "W002"],
                },
            ]
        }

        prefs = parse_shift_order_preferences(params)
        assert len(prefs) == 1
        assert prefs[0].worker_ids == frozenset(["W001", "W002"])

    def test_parse_shift_order_preferences_empty(self) -> None:
        """Return empty list when no rules in parameters."""
        from shift_solver.config.schema import parse_shift_order_preferences

        assert parse_shift_order_preferences({}) == []
        assert parse_shift_order_preferences({"rules": []}) == []
        assert parse_shift_order_preferences(None) == []

    def test_load_shift_order_preference_from_yaml(self) -> None:
        """Load config with shift_order_preference constraint from YAML."""
        yaml_content = """
shift_types:
  - id: day_shift
    name: Day Shift
    category: day
    start_time: "07:00"
    end_time: "15:00"
    duration_hours: 8.0
  - id: night_shift
    name: Night Shift
    category: night
    start_time: "23:00"
    end_time: "07:00"
    duration_hours: 8.0

constraints:
  shift_order_preference:
    enabled: true
    is_hard: false
    weight: 200
    parameters:
      rules:
        - rule_id: weekend_then_night
          trigger_type: category
          trigger_value: weekend
          direction: after
          preferred_type: category
          preferred_value: night
          priority: 2
        - rule_id: night_before_vacation
          trigger_type: unavailability
          direction: before
          preferred_type: shift_type
          preferred_value: night_shift
"""

        with NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()

            config = ShiftSolverConfig.load_from_yaml(Path(f.name))

        assert "shift_order_preference" in config.constraints
        sop_config = config.constraints["shift_order_preference"]
        assert sop_config.enabled is True
        assert sop_config.is_hard is False
        assert sop_config.weight == 200
        assert "rules" in sop_config.parameters
        rules = sop_config.parameters["rules"]
        assert len(rules) == 2
        assert rules[0]["rule_id"] == "weekend_then_night"
