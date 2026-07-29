"""
Tests for the strict/typed/single-source-of-truth config schema.

Covers the confirmed defects fixed in this pass:
  A) extra='forbid' rejects typo'd/unknown keys everywhere in the schema.
  B) Typed constraint parameter models reject unknown parameter keys.
  C) The ConstraintRegistry is the single source of truth for
     enabled/is_hard/weight defaults; ShiftSolverConfig.get_constraint_config
     resolves None fields against it.
  D) fairness/sequence categories and frequency/max_absence/shift_frequency
     shift_types are cross-validated against the shift_types declared in the
     same config.
  E) duration_hours is cross-checked against start_time/end_time (including
     overnight wraps).
  F) An empty config file raises a clear, actionable error instead of a raw
     Pydantic "Input should be a valid dictionary" message.
"""

from datetime import time
from pathlib import Path

import pytest
from pydantic import ValidationError

from shift_solver.config.schema import ShiftSolverConfig, ShiftTypeConfig
from shift_solver.solver.constraint_registry import (
    ConstraintRegistry,
    register_builtin_constraints,
)

BASE_SHIFT_TYPE = {
    "id": "day",
    "name": "Day",
    "category": "day",
    "start_time": "07:00",
    "end_time": "15:00",
    "duration_hours": 8.0,
}

NIGHT_SHIFT_TYPE = {
    "id": "night",
    "name": "Night",
    "category": "night",
    "start_time": "23:00",
    "end_time": "07:00",
    "duration_hours": 8.0,
}


def _config(**overrides: object) -> dict:
    """Build a minimal valid config dict, with overrides merged in."""
    data: dict = {"shift_types": [dict(BASE_SHIFT_TYPE)]}
    data.update(overrides)
    return data


class TestExtraForbidRejectsTypos:
    """Item A: extra='forbid' on every model catches typo'd/unknown keys."""

    def test_unknown_top_level_section_rejected(self) -> None:
        with pytest.raises(ValidationError, match="bogus_section"):
            ShiftSolverConfig.model_validate(
                _config(bogus_section={"anything": True})
            )

    def test_typo_in_solver_section_rejected(self) -> None:
        with pytest.raises(ValidationError, match="maxTimeSeconds"):
            ShiftSolverConfig.model_validate(
                _config(solver={"maxTimeSeconds": 100})
            )

    def test_typo_in_constraint_field_rejected(self) -> None:
        """'weigth' (typo of 'weight') must error, not be silently dropped."""
        with pytest.raises(ValidationError, match="weigth"):
            ShiftSolverConfig.model_validate(
                _config(constraints={"fairness": {"weigth": 500}})
            )

    def test_typo_in_shift_type_field_rejected(self) -> None:
        """'workers_requried' (typo of 'workers_required') must error."""
        shift_type = dict(BASE_SHIFT_TYPE)
        shift_type["workers_requried"] = 3
        with pytest.raises(ValidationError, match="workers_requried"):
            ShiftSolverConfig.model_validate({"shift_types": [shift_type]})

    def test_all_typos_together_do_not_validate(self) -> None:
        """A config with several typos at once must not print 'valid'."""
        shift_type = dict(BASE_SHIFT_TYPE)
        shift_type["workers_requried"] = 3
        with pytest.raises(ValidationError):
            ShiftSolverConfig.model_validate(
                {
                    "shift_types": [shift_type],
                    "constraints": {"fairness": {"weigth": 500}},
                    "bogus_top_level_section": {"x": 1},
                }
            )


class TestRegistryIsSingleSourceOfDefaults:
    """Item C: get_constraint_config()/is_constraint_enabled() resolve None
    fields from the ConstraintRegistry, not from the pydantic model's own
    field defaults."""

    def test_bare_constraint_config_fields_are_none(self) -> None:
        """Unresolved ConstraintConfig carries None, not a baked-in default."""
        from shift_solver.config.schema import ConstraintConfig

        config = ConstraintConfig()
        assert config.enabled is None
        assert config.is_hard is None
        assert config.weight is None

    def test_omitted_constraint_resolves_to_registry_default(self) -> None:
        """A constraint never mentioned in the config resolves from the registry."""
        register_builtin_constraints()
        cfg = ShiftSolverConfig.model_validate(_config())

        registration = ConstraintRegistry.get_all_constraints()["sequence"]
        resolved = cfg.get_constraint_config("sequence")

        assert resolved.enabled == registration.default_config.enabled
        assert resolved.is_hard == registration.default_config.is_hard
        assert resolved.weight == registration.default_config.weight

    def test_is_constraint_enabled_no_longer_lies_for_omitted_block(self) -> None:
        """
        Before this fix, is_constraint_enabled('sequence') was True for an
        omitted sequence block (the bare model's field default), even though
        the registry disables sequence by default and the solver would never
        apply it. It must now match the registry.
        """
        register_builtin_constraints()
        cfg = ShiftSolverConfig.model_validate(_config())

        registration = ConstraintRegistry.get_all_constraints()["sequence"]
        assert registration.default_config.enabled is False
        assert cfg.is_constraint_enabled("sequence") is False

    def test_partial_override_fills_remaining_fields_from_registry(self) -> None:
        """Setting only `enabled` leaves is_hard/weight to inherit from the registry."""
        register_builtin_constraints()
        cfg = ShiftSolverConfig.model_validate(
            _config(constraints={"frequency": {"enabled": True}})
        )

        registration = ConstraintRegistry.get_all_constraints()["frequency"]
        resolved = cfg.get_constraint_config("frequency")

        assert resolved.enabled is True  # explicit override
        assert resolved.is_hard == registration.default_config.is_hard
        assert resolved.weight == registration.default_config.weight

    def test_explicit_override_wins_over_registry_default(self) -> None:
        register_builtin_constraints()
        cfg = ShiftSolverConfig.model_validate(
            _config(
                constraints={
                    "worker_shift_limit": {
                        "parameters": {"max_shifts_per_period": 2}
                    }
                }
            )
        )

        resolved = cfg.get_constraint_config("worker_shift_limit")
        assert resolved.enabled is True  # inherited (hard, enabled by default)
        assert resolved.is_hard is True  # inherited
        assert resolved.parameters == {"max_shifts_per_period": 2}  # overridden

    def test_omitted_worker_shift_limit_inherits_registry_parameters(self) -> None:
        register_builtin_constraints()
        cfg = ShiftSolverConfig.model_validate(_config())

        resolved = cfg.get_constraint_config("worker_shift_limit")
        assert resolved.enabled is True
        assert resolved.is_hard is True
        assert resolved.parameters == {"max_shifts_per_period": 1}


class TestNoSoftOverrideOnHardConstraints:
    """
    is_hard: false on a constraint ID registered as hard (coverage,
    restriction, availability, worker_shift_limit, skills) must be rejected
    at load time: ShiftSolver._apply_hard_constraints only ever checks
    `enabled` for these, never `is_hard`, so is_hard: false would be
    silently ignored and the constraint enforced hard regardless -
    contradicting what the config claims.
    """

    @pytest.mark.parametrize(
        "constraint_id",
        ["coverage", "restriction", "availability", "worker_shift_limit", "skills"],
    )
    def test_is_hard_false_rejected_for_hard_constraint(
        self, constraint_id: str
    ) -> None:
        with pytest.raises(ValidationError, match=constraint_id):
            ShiftSolverConfig.model_validate(
                _config(constraints={constraint_id: {"is_hard": False}})
            )

    def test_error_message_is_actionable(self) -> None:
        """The error explains why, and lists the soft-registered IDs that do
        accept is_hard."""
        with pytest.raises(ValidationError) as exc_info:
            ShiftSolverConfig.model_validate(
                _config(constraints={"coverage": {"is_hard": False}})
            )
        message = str(exc_info.value)
        assert "coverage" in message
        assert "structurally hard" in message
        assert "fairness" in message  # a soft-registered id, named as valid

    @pytest.mark.parametrize(
        "constraint_id",
        ["fairness", "frequency", "sequence", "max_absence", "request"],
    )
    def test_is_hard_false_accepted_for_soft_constraint(
        self, constraint_id: str
    ) -> None:
        cfg = ShiftSolverConfig.model_validate(
            _config(constraints={constraint_id: {"is_hard": False}})
        )
        assert cfg.constraints[constraint_id].is_hard is False

    @pytest.mark.parametrize(
        "constraint_id",
        ["coverage", "restriction", "availability", "worker_shift_limit", "skills"],
    )
    def test_is_hard_true_still_accepted_for_hard_constraint(
        self, constraint_id: str
    ) -> None:
        cfg = ShiftSolverConfig.model_validate(
            _config(constraints={constraint_id: {"is_hard": True}})
        )
        assert cfg.constraints[constraint_id].is_hard is True

    @pytest.mark.parametrize(
        "constraint_id",
        ["coverage", "restriction", "availability", "worker_shift_limit", "skills"],
    )
    def test_is_hard_omitted_still_accepted_for_hard_constraint(
        self, constraint_id: str
    ) -> None:
        """Omitting is_hard (None) is fine - it resolves from the registry."""
        cfg = ShiftSolverConfig.model_validate(
            _config(constraints={constraint_id: {"enabled": True}})
        )
        assert cfg.constraints[constraint_id].is_hard is None


class TestTypedConstraintParameters:
    """Item B: typed parameter models reject unknown/mistyped keys."""

    @pytest.mark.parametrize(
        "constraint_id,parameters",
        [
            ("fairness", {"categories": ["day"]}),
            ("frequency", {"max_periods_between": 4, "shift_types": ["day"]}),
            ("sequence", {"categories": ["day"]}),
            ("max_absence", {"max_periods_absent": 8, "shift_types": ["day"]}),
            ("worker_shift_limit", {"max_shifts_per_period": 2}),
            ("workload", {"min_total_shifts": 1, "max_total_shifts": 5}),
            ("skills", {}),
        ],
    )
    def test_valid_parameters_accepted(
        self, constraint_id: str, parameters: dict
    ) -> None:
        cfg = ShiftSolverConfig.model_validate(
            _config(constraints={constraint_id: {"parameters": parameters}})
        )
        assert cfg.constraints[constraint_id].parameters == parameters

    @pytest.mark.parametrize(
        "constraint_id,parameters",
        [
            ("fairness", {"default_categories": ["day"]}),
            ("frequency", {"default_max_periods_between": 4}),
            ("sequence", {"category": "day"}),  # singular typo of 'categories'
            ("max_absence", {"max_period_absent": 8}),  # typo
            ("worker_shift_limit", {"max_shift_per_period": 2}),  # typo
            ("workload", {"min_shifts": 1}),  # typo
            ("skills", {"required": True}),  # skills takes no parameters at all
        ],
    )
    def test_unknown_parameter_key_rejected(
        self, constraint_id: str, parameters: dict
    ) -> None:
        with pytest.raises(ValidationError) as exc_info:
            ShiftSolverConfig.model_validate(
                _config(constraints={constraint_id: {"parameters": parameters}})
            )
        message = str(exc_info.value)
        assert constraint_id in message
        # The offending key must be named in the error.
        bad_key = next(iter(parameters))
        assert bad_key in message

    def test_frequency_max_periods_between_must_be_ge_one(self) -> None:
        with pytest.raises(ValidationError):
            ShiftSolverConfig.model_validate(
                _config(
                    constraints={
                        "frequency": {"parameters": {"max_periods_between": 0}}
                    }
                )
            )

    def test_worker_shift_limit_max_shifts_must_be_ge_one(self) -> None:
        with pytest.raises(ValidationError):
            ShiftSolverConfig.model_validate(
                _config(
                    constraints={
                        "worker_shift_limit": {
                            "parameters": {"max_shifts_per_period": 0}
                        }
                    }
                )
            )

    def test_workload_min_greater_than_max_rejected(self) -> None:
        with pytest.raises(ValidationError, match="min_total_shifts"):
            ShiftSolverConfig.model_validate(
                _config(
                    constraints={
                        "workload": {
                            "parameters": {
                                "min_total_shifts": 10,
                                "max_total_shifts": 5,
                            }
                        }
                    }
                )
            )

    def test_workload_min_equal_max_allowed(self) -> None:
        cfg = ShiftSolverConfig.model_validate(
            _config(
                constraints={
                    "workload": {
                        "parameters": {
                            "min_total_shifts": 5,
                            "max_total_shifts": 5,
                        }
                    }
                }
            )
        )
        assert cfg.constraints["workload"].parameters["min_total_shifts"] == 5


class TestConstraintFilterCrossValidation:
    """Item D: category/shift_type filters must reference declared values."""

    def test_fairness_unknown_category_rejected(self) -> None:
        with pytest.raises(ValidationError, match="unknown"):
            ShiftSolverConfig.model_validate(
                _config(
                    constraints={
                        "fairness": {"parameters": {"categories": ["ambulatory"]}}
                    }
                )
            )

    def test_fairness_error_lists_valid_categories(self) -> None:
        with pytest.raises(ValidationError, match="day"):
            ShiftSolverConfig.model_validate(
                _config(
                    constraints={
                        "fairness": {"parameters": {"categories": ["ambulatory"]}}
                    }
                )
            )

    def test_fairness_known_category_accepted(self) -> None:
        cfg = ShiftSolverConfig.model_validate(
            _config(
                constraints={"fairness": {"parameters": {"categories": ["day"]}}}
            )
        )
        assert cfg.constraints["fairness"].parameters["categories"] == ["day"]

    def test_sequence_unknown_category_rejected(self) -> None:
        with pytest.raises(ValidationError, match="unknown"):
            ShiftSolverConfig.model_validate(
                _config(
                    constraints={
                        "sequence": {"parameters": {"categories": ["weekend"]}}
                    }
                )
            )

    def test_frequency_unknown_shift_type_rejected(self) -> None:
        with pytest.raises(ValidationError, match="unknown"):
            ShiftSolverConfig.model_validate(
                _config(
                    constraints={
                        "frequency": {
                            "parameters": {"shift_types": ["nonexistent_shift"]}
                        }
                    }
                )
            )

    def test_frequency_known_shift_type_accepted(self) -> None:
        cfg = ShiftSolverConfig.model_validate(
            _config(
                constraints={"frequency": {"parameters": {"shift_types": ["day"]}}}
            )
        )
        assert cfg.constraints["frequency"].parameters["shift_types"] == ["day"]

    def test_max_absence_unknown_shift_type_rejected(self) -> None:
        with pytest.raises(ValidationError, match="unknown"):
            ShiftSolverConfig.model_validate(
                _config(
                    constraints={
                        "max_absence": {
                            "parameters": {"shift_types": ["nonexistent_shift"]}
                        }
                    }
                )
            )

    def test_shift_frequency_unknown_shift_type_in_requirement_rejected(self) -> None:
        with pytest.raises(ValidationError, match="unknown"):
            ShiftSolverConfig.model_validate(
                _config(
                    constraints={
                        "shift_frequency": {
                            "parameters": {
                                "requirements": [
                                    {
                                        "worker_id": "w1",
                                        "shift_types": ["nonexistent_shift"],
                                        "max_periods_between": 4,
                                    }
                                ]
                            }
                        }
                    }
                )
            )

    def test_shift_frequency_known_shift_type_in_requirement_accepted(self) -> None:
        cfg = ShiftSolverConfig.model_validate(
            _config(
                constraints={
                    "shift_frequency": {
                        "parameters": {
                            "requirements": [
                                {
                                    "worker_id": "w1",
                                    "shift_types": ["day"],
                                    "max_periods_between": 4,
                                }
                            ]
                        }
                    }
                }
            )
        )
        req = cfg.constraints["shift_frequency"].parameters["requirements"][0]
        assert req["shift_types"] == ["day"]


class TestDurationMatchesTimes:
    """Item E: duration_hours must agree with the start_time/end_time span."""

    def test_mismatched_same_day_shift_rejected(self) -> None:
        with pytest.raises(ValidationError, match="duration_hours"):
            ShiftTypeConfig(
                id="day",
                name="Day",
                category="day",
                start_time=time(9, 0),
                end_time=time(17, 0),  # 8h span
                duration_hours=6.0,  # wrong
            )

    def test_mismatched_overnight_shift_rejected(self) -> None:
        with pytest.raises(ValidationError, match="duration_hours"):
            ShiftTypeConfig(
                id="night",
                name="Night",
                category="night",
                start_time=time(23, 0),
                end_time=time(7, 0),  # wraps midnight -> 8h span
                duration_hours=10.0,  # wrong
            )

    def test_correct_overnight_shift_accepted(self) -> None:
        config = ShiftTypeConfig(
            id="night",
            name="Night",
            category="night",
            start_time=time(23, 0),
            end_time=time(7, 0),
            duration_hours=8.0,
        )
        assert config.duration_hours == 8.0

    def test_correct_same_day_shift_accepted(self) -> None:
        config = ShiftTypeConfig(
            id="day",
            name="Day",
            category="day",
            start_time=time(9, 0),
            end_time=time(17, 0),
            duration_hours=8.0,
        )
        assert config.duration_hours == 8.0

    def test_full_day_wrap_accepted(self) -> None:
        """start_time == end_time is treated as a full 24h shift."""
        config = ShiftTypeConfig(
            id="full_day",
            name="Full Day",
            category="day",
            start_time=time(0, 0),
            end_time=time(0, 0),
            duration_hours=24.0,
        )
        assert config.duration_hours == 24.0

    def test_config_validate_surfaces_duration_mismatch(self) -> None:
        """The mismatch is also caught when loading a full ShiftSolverConfig."""
        shift_type = dict(BASE_SHIFT_TYPE)
        shift_type["duration_hours"] = 2.0  # actual span is 8h
        with pytest.raises(ValidationError, match="duration_hours"):
            ShiftSolverConfig.model_validate({"shift_types": [shift_type]})


class TestEmptyConfigFile:
    """Item F: an empty config file must raise a clear, actionable error."""

    def test_empty_file_raises_clear_error(self, tmp_path: Path) -> None:
        config_file = tmp_path / "empty.yaml"
        config_file.write_text("")

        with pytest.raises(ValueError, match="empty"):
            ShiftSolverConfig.load_from_yaml(config_file)

    def test_whitespace_only_file_raises_clear_error(self, tmp_path: Path) -> None:
        """A file with only whitespace/comments also parses to None via YAML."""
        config_file = tmp_path / "blank.yaml"
        config_file.write_text("\n  \n# just a comment\n")

        with pytest.raises(ValueError, match="empty"):
            ShiftSolverConfig.load_from_yaml(config_file)

    def test_error_message_includes_path(self, tmp_path: Path) -> None:
        config_file = tmp_path / "empty.yaml"
        config_file.write_text("")

        with pytest.raises(ValueError, match=str(config_file)):
            ShiftSolverConfig.load_from_yaml(config_file)
