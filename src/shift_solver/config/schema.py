"""Configuration schema for shift-solver using Pydantic v2."""

from datetime import time
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator


class SolverConfig(BaseModel):
    """Configuration for the OR-Tools solver."""

    max_time_seconds: int = Field(default=3600, gt=0)
    num_workers: int = Field(default=8, ge=1)
    quick_solution_seconds: int = Field(default=60, gt=0)
    save_interval_seconds: int = Field(default=300, gt=0)


class ScheduleConfig(BaseModel):
    """Configuration for schedule parameters."""

    period_type: str = Field(default="week")
    num_periods: int | None = Field(default=None, ge=1)


class ConstraintConfig(BaseModel):
    """Configuration for a single constraint."""

    enabled: bool = Field(default=True)
    is_hard: bool = Field(default=True)
    weight: int = Field(default=100, ge=0)
    parameters: dict[str, Any] = Field(default_factory=dict)


class ShiftTypeConfig(BaseModel):
    """Configuration for a shift type."""

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    category: str
    start_time: time
    end_time: time
    duration_hours: float = Field(gt=0, le=24)
    is_undesirable: bool = Field(default=False)
    workers_required: int = Field(default=1, ge=1)
    required_attributes: dict[str, Any] = Field(default_factory=dict)

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


class DatabaseConfig(BaseModel):
    """Configuration for database settings."""

    path: str = Field(default="shift_solver.db")
    backup_on_solve: bool = Field(default=True)


class LoggingConfig(BaseModel):
    """Configuration for logging."""

    level: str = Field(default="INFO")
    file: str | None = Field(default=None)


class ShiftSolverConfig(BaseModel):
    """Main configuration for shift-solver."""

    solver: SolverConfig = Field(default_factory=SolverConfig)
    schedule: ScheduleConfig = Field(default_factory=ScheduleConfig)
    constraints: dict[str, ConstraintConfig] = Field(default_factory=dict)
    shift_types: list[ShiftTypeConfig] = Field(min_length=1)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
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
            ValidationError: If the configuration is invalid
        """
        with open(path) as f:
            data = yaml.safe_load(f)
        return cls.model_validate(data)

    def get_constraint_config(self, constraint_id: str) -> ConstraintConfig:
        """
        Get configuration for a specific constraint.

        Args:
            constraint_id: The ID of the constraint

        Returns:
            ConstraintConfig for the constraint, or default if not configured
        """
        return self.constraints.get(constraint_id, ConstraintConfig())

    def is_constraint_enabled(self, constraint_id: str) -> bool:
        """Check if a constraint is enabled."""
        return self.get_constraint_config(constraint_id).enabled

    def get_shift_type_config(self, shift_type_id: str) -> ShiftTypeConfig | None:
        """Get configuration for a specific shift type."""
        for st in self.shift_types:
            if st.id == shift_type_id:
                return st
        return None
