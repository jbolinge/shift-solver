"""Configuration schema for shift-solver using Pydantic v2."""

from datetime import time
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

if TYPE_CHECKING:
    from shift_solver.models import ShiftFrequencyRequirement, ShiftOrderPreference


class DateFormat(str, Enum):
    """Date format options for parsing."""

    ISO = "iso"  # YYYY-MM-DD (unambiguous)
    US = "us"  # MM/DD/YYYY
    EU = "eu"  # DD/MM/YYYY
    AUTO = "auto"  # Try all formats (default, warns on ambiguous)


class SolverConfig(BaseModel):
    """Configuration for the OR-Tools solver."""

    model_config = ConfigDict(extra="forbid")

    max_time_seconds: int = Field(default=3600, gt=0)
    num_workers: int = Field(default=8, ge=1)
    quick_solution_seconds: int = Field(default=60, gt=0)
    save_interval_seconds: int = Field(default=300, gt=0)


class ScheduleConfig(BaseModel):
    """Configuration for schedule parameters."""

    model_config = ConfigDict(extra="forbid")

    period_type: str = Field(default="week")
    num_periods: int | None = Field(default=None, ge=1)
    date_format: DateFormat = Field(default=DateFormat.AUTO)


class ConstraintConfig(BaseModel):
    """
    Configuration for a single constraint.

    enabled/is_hard/weight default to None, meaning "inherit whatever the
    ConstraintRegistry registration declares for this constraint id". The
    registry is the single source of truth for defaults; this model only
    carries explicit overrides. Use ShiftSolverConfig.get_constraint_config()
    to resolve None fields against the registry.
    """

    model_config = ConfigDict(extra="forbid")

    enabled: bool | None = Field(default=None)
    is_hard: bool | None = Field(default=None)
    weight: int | None = Field(default=None, ge=0)
    parameters: dict[str, Any] = Field(default_factory=dict)


class FairnessParametersConfig(BaseModel):
    """Typed parameters for the fairness constraint."""

    model_config = ConfigDict(extra="forbid")

    categories: list[str] | None = Field(default=None)


class FrequencyParametersConfig(BaseModel):
    """Typed parameters for the frequency constraint."""

    model_config = ConfigDict(extra="forbid")

    max_periods_between: int | None = Field(default=None, ge=1)
    shift_types: list[str] | None = Field(default=None)


class SequenceParametersConfig(BaseModel):
    """Typed parameters for the sequence constraint."""

    model_config = ConfigDict(extra="forbid")

    categories: list[str] | None = Field(default=None)


class MaxAbsenceParametersConfig(BaseModel):
    """Typed parameters for the max_absence constraint."""

    model_config = ConfigDict(extra="forbid")

    max_periods_absent: int | None = Field(default=None, ge=1)
    shift_types: list[str] | None = Field(default=None)


class WorkerShiftLimitParametersConfig(BaseModel):
    """Typed parameters for the worker_shift_limit constraint."""

    model_config = ConfigDict(extra="forbid")

    max_shifts_per_period: int | None = Field(default=None, ge=1)


class WorkloadParametersConfig(BaseModel):
    """Typed parameters for the workload constraint."""

    model_config = ConfigDict(extra="forbid")

    min_total_shifts: int = Field(default=0, ge=0)
    max_total_shifts: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_min_le_max(self) -> "WorkloadParametersConfig":
        """Ensure min_total_shifts does not exceed max_total_shifts."""
        if (
            self.max_total_shifts is not None
            and self.min_total_shifts > self.max_total_shifts
        ):
            raise ValueError(
                f"min_total_shifts ({self.min_total_shifts}) must be <= "
                f"max_total_shifts ({self.max_total_shifts})"
            )
        return self


class SkillsParametersConfig(BaseModel):
    """Typed parameters for the skills constraint (accepts none)."""

    model_config = ConfigDict(extra="forbid")


class ShiftFrequencyRequirementConfig(BaseModel):
    """Configuration for a single shift frequency requirement."""

    model_config = ConfigDict(extra="forbid")

    worker_id: str = Field(min_length=1)
    shift_types: list[str] = Field(min_length=1)
    max_periods_between: int = Field(gt=0)


class ShiftFrequencyParametersConfig(BaseModel):
    """Configuration for shift_frequency constraint parameters."""

    model_config = ConfigDict(extra="forbid")

    requirements: list[ShiftFrequencyRequirementConfig] = Field(default_factory=list)


def parse_shift_frequency_requirements(
    parameters: dict[str, Any] | None,
) -> list["ShiftFrequencyRequirement"]:
    """
    Parse shift_frequency constraint parameters into ShiftFrequencyRequirement objects.

    Args:
        parameters: The constraint parameters dict from config

    Returns:
        List of ShiftFrequencyRequirement objects
    """
    from shift_solver.models import ShiftFrequencyRequirement

    if not parameters:
        return []

    requirements_data = parameters.get("requirements", [])
    if not requirements_data:
        return []

    # Validate using Pydantic model
    validated = ShiftFrequencyParametersConfig(requirements=requirements_data)

    return [
        ShiftFrequencyRequirement(
            worker_id=req.worker_id,
            shift_types=frozenset(req.shift_types),
            max_periods_between=req.max_periods_between,
        )
        for req in validated.requirements
    ]


class ShiftOrderRuleConfig(BaseModel):
    """Configuration for a single shift order preference rule."""

    model_config = ConfigDict(extra="forbid")

    rule_id: str = Field(min_length=1)
    trigger_type: str = Field(pattern=r"^(shift_type|category|unavailability)$")
    trigger_value: str | None = Field(default=None)
    direction: str = Field(pattern=r"^(after|before)$")
    preferred_type: str = Field(pattern=r"^(shift_type|category)$")
    preferred_value: str = Field(min_length=1)
    priority: int = Field(default=1, ge=1)
    worker_ids: list[str] | None = Field(default=None)

    @model_validator(mode="after")
    def validate_trigger_value(self) -> "ShiftOrderRuleConfig":
        """Ensure trigger_value is set for shift_type and category triggers."""
        if self.trigger_type in ("shift_type", "category") and not self.trigger_value:
            raise ValueError(
                f"trigger_value is required for trigger_type '{self.trigger_type}'"
            )
        return self


class ShiftOrderPreferenceParametersConfig(BaseModel):
    """Configuration for shift_order_preference constraint parameters."""

    model_config = ConfigDict(extra="forbid")

    rules: list[ShiftOrderRuleConfig] = Field(default_factory=list)


def parse_shift_order_preferences(
    parameters: dict[str, Any] | None,
) -> list["ShiftOrderPreference"]:
    """
    Parse shift_order_preference constraint parameters into ShiftOrderPreference objects.

    Args:
        parameters: The constraint parameters dict from config

    Returns:
        List of ShiftOrderPreference objects
    """
    from shift_solver.models import ShiftOrderPreference

    if not parameters:
        return []

    rules_data = parameters.get("rules", [])
    if not rules_data:
        return []

    validated = ShiftOrderPreferenceParametersConfig(rules=rules_data)

    return [
        ShiftOrderPreference(
            rule_id=rule.rule_id,
            trigger_type=rule.trigger_type,  # type: ignore[arg-type]
            trigger_value=rule.trigger_value,
            direction=rule.direction,  # type: ignore[arg-type]
            preferred_type=rule.preferred_type,  # type: ignore[arg-type]
            preferred_value=rule.preferred_value,
            priority=rule.priority,
            worker_ids=frozenset(rule.worker_ids) if rule.worker_ids else None,
        )
        for rule in validated.rules
    ]


# Dispatch table used by ShiftSolverConfig.validate_constraint_parameter_shapes to
# validate each constraint's `parameters` dict against a typed model, by
# constraint id. Constraint ids with no entry here (coverage, restriction,
# availability, request) currently take no parameters recognized by their
# constraint implementation.
CONSTRAINT_PARAMETER_MODELS: dict[str, type[BaseModel]] = {
    "fairness": FairnessParametersConfig,
    "frequency": FrequencyParametersConfig,
    "sequence": SequenceParametersConfig,
    "max_absence": MaxAbsenceParametersConfig,
    "worker_shift_limit": WorkerShiftLimitParametersConfig,
    "workload": WorkloadParametersConfig,
    "skills": SkillsParametersConfig,
    "shift_frequency": ShiftFrequencyParametersConfig,
    "shift_order_preference": ShiftOrderPreferenceParametersConfig,
}


def _validate_constraint_parameters(
    constraint_id: str, parameters: dict[str, Any], model_cls: type[BaseModel]
) -> None:
    """Validate a constraint's parameters dict against its typed parameter model."""
    try:
        model_cls.model_validate(parameters)
    except ValidationError as e:
        valid_keys = sorted(model_cls.model_fields)
        errors = "; ".join(
            f"{'.'.join(str(p) for p in err['loc']) or '<parameters>'}: {err['msg']}"
            for err in e.errors()
        )
        raise ValueError(
            f"Invalid parameters for constraint '{constraint_id}': {errors}. "
            f"Valid keys: {valid_keys}"
        ) from e


class ShiftTypeConfig(BaseModel):
    """Configuration for a shift type."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    category: str
    start_time: time
    end_time: time
    duration_hours: float = Field(gt=0, le=24)
    is_undesirable: bool = Field(default=False)
    workers_required: int = Field(default=1, ge=1)
    required_attributes: dict[str, str] = Field(default_factory=dict)
    applicable_days: list[int] | None = Field(default=None)

    @field_validator("required_attributes", mode="before")
    @classmethod
    def coerce_attribute_values(cls, v: Any) -> Any:
        """Coerce attribute values to strings.

        Worker attributes loaded from CSV are always strings, and the skills
        constraint matches with plain equality - a YAML `level: 3` (int)
        could never match a CSV `level=3` without this coercion. YAML bools
        are lowercased ("true"/"false") to match their YAML spelling.
        """
        if isinstance(v, dict):
            return {
                key: (str(value).lower() if isinstance(value, bool) else str(value))
                for key, value in v.items()
            }
        return v

    @field_validator("applicable_days")
    @classmethod
    def validate_applicable_days(cls, v: list[int] | None) -> list[int] | None:
        """Validate that applicable_days contains valid day numbers (0-6)."""
        if v is not None:
            for day in v:
                if not 0 <= day <= 6:
                    raise ValueError(f"Day must be 0-6, got: {day}")
        return v

    @field_validator("start_time", "end_time", mode="before")
    @classmethod
    def parse_time(cls, v: Any) -> time:
        """Parse time from string if needed."""
        if isinstance(v, str):
            if ":" not in v:
                raise ValueError(
                    f"Invalid time format '{v}': must be HH:MM format"
                )
            parts = v.split(":")
            if len(parts) < 2:
                raise ValueError(
                    f"Invalid time format '{v}': must be HH:MM format"
                )
            try:
                hour = int(parts[0])
                minute = int(parts[1])
            except ValueError as e:
                raise ValueError(
                    f"Invalid time format '{v}': hour and minute must be integers"
                ) from e
            if not (0 <= hour <= 23):
                raise ValueError(
                    f"Invalid time '{v}': hour must be 0-23"
                )
            if not (0 <= minute <= 59):
                raise ValueError(
                    f"Invalid time '{v}': minute must be 0-59"
                )
            return time(hour, minute)
        if isinstance(v, time):
            return v
        raise ValueError(f"Cannot parse time from {type(v).__name__}")

    @model_validator(mode="after")
    def validate_duration_matches_times(self) -> "ShiftTypeConfig":
        """
        Ensure duration_hours agrees with the start_time/end_time span.

        Overnight shifts (end_time <= start_time) wrap past midnight, so the
        span is measured through midnight rather than treated as negative.
        """
        start_minutes = self.start_time.hour * 60 + self.start_time.minute
        end_minutes = self.end_time.hour * 60 + self.end_time.minute
        if end_minutes <= start_minutes:
            span_minutes = (24 * 60 - start_minutes) + end_minutes
        else:
            span_minutes = end_minutes - start_minutes
        expected_hours = span_minutes / 60
        if abs(self.duration_hours - expected_hours) > 1e-6:
            raise ValueError(
                f"Shift type '{self.id}': duration_hours ({self.duration_hours}) "
                f"does not match the start_time/end_time span "
                f"({expected_hours:g}h from {self.start_time} to {self.end_time}). "
                f"If this shift wraps past midnight, end_time must be earlier "
                f"than start_time to signal that."
            )
        return self


class LoggingConfig(BaseModel):
    """Configuration for logging."""

    model_config = ConfigDict(extra="forbid")

    level: str = Field(default="INFO")
    file: str | None = Field(default=None)


class ShiftSolverConfig(BaseModel):
    """Main configuration for shift-solver."""

    model_config = ConfigDict(extra="forbid")

    solver: SolverConfig = Field(default_factory=SolverConfig)
    schedule: ScheduleConfig = Field(default_factory=ScheduleConfig)
    constraints: dict[str, ConstraintConfig] = Field(default_factory=dict)
    shift_types: list[ShiftTypeConfig] = Field(min_length=1)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    @model_validator(mode="after")
    def validate_unique_shift_type_ids(self) -> "ShiftSolverConfig":
        """Ensure all shift type IDs are unique."""
        ids = [st.id for st in self.shift_types]
        if len(ids) != len(set(ids)):
            duplicates = [id for id in ids if ids.count(id) > 1]
            raise ValueError(
                f"Shift type IDs must be unique. Duplicates: {set(duplicates)}"
            )
        return self

    @model_validator(mode="after")
    def validate_known_constraint_ids(self) -> "ShiftSolverConfig":
        """Reject constraint IDs that no registered constraint will ever read."""
        # Imported lazily: the solver package imports this module at load time,
        # and the registry is only needed once a config is actually validated.
        from shift_solver.solver.constraint_registry import (
            ConstraintRegistry,
            register_builtin_constraints,
        )

        register_builtin_constraints()
        known = set(ConstraintRegistry.get_all_constraints())
        unknown = set(self.constraints) - known
        if unknown:
            raise ValueError(
                f"Unknown constraint IDs (the solver would silently ignore them): "
                f"{sorted(unknown)}. Valid IDs: {sorted(known)}"
            )
        return self

    @model_validator(mode="after")
    def validate_no_soft_override_on_hard_constraints(self) -> "ShiftSolverConfig":
        """
        Reject is_hard: false on constraint IDs that are structurally hard.

        ShiftSolver._apply_hard_constraints only checks a hard-registered
        constraint's `enabled` flag - it never reads `is_hard` - so
        `is_hard: false` on coverage/restriction/availability/
        worker_shift_limit/skills is silently ignored: the constraint keeps
        being enforced as hard, contradicting what the config claims. Fail
        fast at load time instead of shipping a config that lies about its
        own behavior.
        """
        # Imported lazily, matching validate_known_constraint_ids above.
        from shift_solver.solver.constraint_registry import (
            ConstraintRegistry,
            register_builtin_constraints,
        )

        register_builtin_constraints()
        hard_ids = set(ConstraintRegistry.get_hard_constraints())
        soft_ids = sorted(ConstraintRegistry.get_soft_constraints())

        for constraint_id, constraint_config in self.constraints.items():
            if constraint_id in hard_ids and constraint_config.is_hard is False:
                raise ValueError(
                    f"constraints.{constraint_id}.is_hard: false is not "
                    f"supported: '{constraint_id}' is structurally hard "
                    f"(ShiftSolver always enforces it as a hard constraint "
                    f"when enabled, regardless of is_hard) so is_hard: false "
                    f"would be silently ignored. Remove 'is_hard' (or set it "
                    f"to true) for '{constraint_id}'; to disable it entirely "
                    f"use 'enabled: false' instead. Constraint IDs that do "
                    f"accept is_hard: false: {soft_ids}"
                )
        return self

    @model_validator(mode="after")
    def validate_constraint_parameter_shapes(self) -> "ShiftSolverConfig":
        """Validate each constraint's parameters dict against its typed model."""
        for constraint_id, constraint_config in self.constraints.items():
            model_cls = CONSTRAINT_PARAMETER_MODELS.get(constraint_id)
            if model_cls is not None:
                _validate_constraint_parameters(
                    constraint_id, constraint_config.parameters, model_cls
                )
        return self

    @model_validator(mode="after")
    def validate_constraint_filter_references(self) -> "ShiftSolverConfig":
        """
        Ensure category/shift-type filters reference values declared under
        shift_types in this same config (catches stale/typo'd filter values
        the solver would otherwise silently match nothing against).
        """
        declared_categories = {st.category for st in self.shift_types}
        declared_shift_type_ids = {st.id for st in self.shift_types}

        def _check_filter(constraint_id: str, key: str, valid: set[str]) -> None:
            config = self.constraints.get(constraint_id)
            if config is None:
                return
            values = config.parameters.get(key)
            if not values:
                return
            unknown = [v for v in values if v not in valid]
            if unknown:
                raise ValueError(
                    f"constraints.{constraint_id}.parameters.{key} references "
                    f"unknown values {unknown}. Valid values: {sorted(valid)}"
                )

        _check_filter("fairness", "categories", declared_categories)
        _check_filter("sequence", "categories", declared_categories)
        _check_filter("frequency", "shift_types", declared_shift_type_ids)
        _check_filter("max_absence", "shift_types", declared_shift_type_ids)

        sf_config = self.constraints.get("shift_frequency")
        if sf_config is not None:
            requirements = sf_config.parameters.get("requirements") or []
            for i, req in enumerate(requirements):
                shift_types = req.get("shift_types") or []
                unknown = [s for s in shift_types if s not in declared_shift_type_ids]
                if unknown:
                    raise ValueError(
                        f"constraints.shift_frequency.parameters.requirements[{i}]"
                        f".shift_types references unknown values {unknown}. "
                        f"Valid shift type ids: {sorted(declared_shift_type_ids)}"
                    )

        return self

    @classmethod
    def load_from_yaml(cls, path: Path) -> "ShiftSolverConfig":
        """
        Load configuration from a YAML file.

        Args:
            path: Path to the YAML configuration file

        Returns:
            Validated ShiftSolverConfig instance

        Raises:
            FileNotFoundError: If the file doesn't exist
            ValueError: If the file is empty
            ValidationError: If the configuration is invalid
        """
        with open(path) as f:
            data = yaml.safe_load(f)
        if data is None:
            raise ValueError(f"Config file is empty: {path}")
        return cls.model_validate(data)

    def get_constraint_config(self, constraint_id: str) -> ConstraintConfig:
        """
        Get the resolved configuration for a specific constraint.

        Any of enabled/is_hard/weight left unset (None) in this config are
        filled in from the ConstraintRegistry registration's default_config,
        making the registry the single source of truth for defaults. The
        parameters dict is taken as-is from this config when non-empty,
        otherwise from the registry default.

        Args:
            constraint_id: The ID of the constraint

        Returns:
            ConstraintConfig with enabled/is_hard/weight fully resolved
        """
        # Imported lazily, matching validate_known_constraint_ids above.
        from shift_solver.solver.constraint_registry import (
            ConstraintRegistry,
            register_builtin_constraints,
        )

        register_builtin_constraints()
        registration = ConstraintRegistry.get_all_constraints().get(constraint_id)
        configured = self.constraints.get(constraint_id)

        if registration is None:
            # Not a registered constraint (validate_known_constraint_ids would
            # have rejected it if it came from YAML) -- fall back to whatever
            # was configured, or plain defaults, with nothing to resolve.
            return configured if configured is not None else ConstraintConfig()

        default = registration.default_config
        if configured is None:
            return ConstraintConfig(
                enabled=default.enabled,
                is_hard=default.is_hard,
                weight=default.weight,
                parameters=dict(default.parameters or {}),
            )

        return ConstraintConfig(
            enabled=configured.enabled if configured.enabled is not None else default.enabled,
            is_hard=configured.is_hard if configured.is_hard is not None else default.is_hard,
            weight=configured.weight if configured.weight is not None else default.weight,
            parameters=(
                configured.parameters
                if configured.parameters
                else dict(default.parameters or {})
            ),
        )

    def is_constraint_enabled(self, constraint_id: str) -> bool:
        """Check if a constraint is enabled, resolving the registry default."""
        enabled = self.get_constraint_config(constraint_id).enabled
        return bool(enabled)

    def get_shift_type_config(self, shift_type_id: str) -> ShiftTypeConfig | None:
        """Get configuration for a specific shift type."""
        for st in self.shift_types:
            if st.id == shift_type_id:
                return st
        return None
