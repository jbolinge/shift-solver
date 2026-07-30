"""Constraint registry for automatic constraint discovery and registration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from shift_solver.constraints.base import ConstraintConfig

if TYPE_CHECKING:
    from shift_solver.constraints.base import BaseConstraint


@dataclass
class ConstraintRegistration:
    """Registration info for a constraint."""

    constraint_id: str
    constraint_class: type["BaseConstraint"]
    is_hard: bool
    default_config: ConstraintConfig


class ConstraintRegistry:
    """
    Registry for constraint classes.

    Provides automatic registration via decorators and
    dynamic constraint instantiation based on configuration.
    """

    _hard_constraints: dict[str, ConstraintRegistration] = {}
    _soft_constraints: dict[str, ConstraintRegistration] = {}

    @classmethod
    def register_hard(
        cls, constraint_id: str
    ) -> Callable[[type["BaseConstraint"]], type["BaseConstraint"]]:
        """
        Decorator to register a hard constraint class.

        Args:
            constraint_id: Unique identifier for the constraint

        Returns:
            Decorator function
        """

        def decorator(
            constraint_class: type["BaseConstraint"],
        ) -> type["BaseConstraint"]:
            registration = ConstraintRegistration(
                constraint_id=constraint_id,
                constraint_class=constraint_class,
                is_hard=True,
                default_config=ConstraintConfig(enabled=True, is_hard=True),
            )
            cls._hard_constraints[constraint_id] = registration
            return constraint_class

        return decorator

    @classmethod
    def register_soft(
        cls,
        constraint_id: str,
        default_config: ConstraintConfig | None = None,
    ) -> Callable[[type["BaseConstraint"]], type["BaseConstraint"]]:
        """
        Decorator to register a soft constraint class.

        Args:
            constraint_id: Unique identifier for the constraint
            default_config: Default configuration for the constraint

        Returns:
            Decorator function
        """
        if default_config is None:
            default_config = ConstraintConfig(enabled=False, is_hard=False, weight=100)

        def decorator(
            constraint_class: type["BaseConstraint"],
        ) -> type["BaseConstraint"]:
            registration = ConstraintRegistration(
                constraint_id=constraint_id,
                constraint_class=constraint_class,
                is_hard=False,
                default_config=default_config,
            )
            cls._soft_constraints[constraint_id] = registration
            return constraint_class

        return decorator

    @classmethod
    def get_hard_constraints(cls) -> dict[str, ConstraintRegistration]:
        """Get all registered hard constraints."""
        return cls._hard_constraints.copy()

    @classmethod
    def get_soft_constraints(cls) -> dict[str, ConstraintRegistration]:
        """Get all registered soft constraints."""
        return cls._soft_constraints.copy()

    @classmethod
    def get_all_constraints(cls) -> dict[str, ConstraintRegistration]:
        """Get all registered constraints."""
        return {**cls._hard_constraints, **cls._soft_constraints}

    @classmethod
    def clear(cls) -> None:
        """Clear all registrations (useful for testing)."""
        cls._hard_constraints.clear()
        cls._soft_constraints.clear()


def register_builtin_constraints() -> None:
    """
    Register all built-in constraints.

    This function should be called during module initialization
    to ensure all constraints are available in the registry.
    """
    # Import constraint modules to trigger their registration decorators
    # The imports themselves cause the decorators to run
    from shift_solver.constraints import (
        AvailabilityConstraint,
        ConsecutiveShiftTypeConstraint,
        CoverageConstraint,
        FairnessConstraint,
        FrequencyConstraint,
        MaxAbsenceConstraint,
        MaxConsecutiveConstraint,
        MinRestConstraint,
        PinnedAssignmentConstraint,
        PreferenceConstraint,
        RequestConstraint,
        RestrictionConstraint,
        SequenceConstraint,
        ShiftFrequencyConstraint,
        ShiftOrderPreferenceConstraint,
        ShiftSuccessionConstraint,
        SkillsConstraint,
        WeekendConstraint,
        WorkerPairingConstraint,
        WorkerShiftLimitConstraint,
        WorkloadConstraint,
    )

    # Register hard constraints if not already registered by decorators
    if "coverage" not in ConstraintRegistry._hard_constraints:
        ConstraintRegistry._hard_constraints["coverage"] = ConstraintRegistration(
            constraint_id="coverage",
            constraint_class=CoverageConstraint,
            is_hard=True,
            default_config=ConstraintConfig(enabled=True, is_hard=True),
        )

    if "restriction" not in ConstraintRegistry._hard_constraints:
        ConstraintRegistry._hard_constraints["restriction"] = ConstraintRegistration(
            constraint_id="restriction",
            constraint_class=RestrictionConstraint,
            is_hard=True,
            default_config=ConstraintConfig(enabled=True, is_hard=True),
        )

    if "availability" not in ConstraintRegistry._hard_constraints:
        ConstraintRegistry._hard_constraints["availability"] = ConstraintRegistration(
            constraint_id="availability",
            constraint_class=AvailabilityConstraint,
            is_hard=True,
            default_config=ConstraintConfig(enabled=True, is_hard=True),
        )

    if "worker_shift_limit" not in ConstraintRegistry._hard_constraints:
        ConstraintRegistry._hard_constraints["worker_shift_limit"] = (
            ConstraintRegistration(
                constraint_id="worker_shift_limit",
                constraint_class=WorkerShiftLimitConstraint,
                is_hard=True,
                default_config=ConstraintConfig(
                    enabled=True,
                    is_hard=True,
                    parameters={"max_shifts_per_period": 1},
                ),
            )
        )

    if "skills" not in ConstraintRegistry._hard_constraints:
        ConstraintRegistry._hard_constraints["skills"] = ConstraintRegistration(
            constraint_id="skills",
            constraint_class=SkillsConstraint,
            is_hard=True,
            default_config=ConstraintConfig(enabled=True, is_hard=True),
        )

    if "pinned" not in ConstraintRegistry._hard_constraints:
        ConstraintRegistry._hard_constraints["pinned"] = ConstraintRegistration(
            constraint_id="pinned",
            constraint_class=PinnedAssignmentConstraint,
            is_hard=True,
            default_config=ConstraintConfig(
                enabled=False,
                is_hard=True,
                parameters={"assignments": []},
            ),
        )

    # Register soft constraints if not already registered by decorators
    if "fairness" not in ConstraintRegistry._soft_constraints:
        ConstraintRegistry._soft_constraints["fairness"] = ConstraintRegistration(
            constraint_id="fairness",
            constraint_class=FairnessConstraint,
            is_hard=False,
            default_config=ConstraintConfig(enabled=True, is_hard=False, weight=1000),
        )

    if "frequency" not in ConstraintRegistry._soft_constraints:
        ConstraintRegistry._soft_constraints["frequency"] = ConstraintRegistration(
            constraint_id="frequency",
            constraint_class=FrequencyConstraint,
            is_hard=False,
            default_config=ConstraintConfig(enabled=False, is_hard=False, weight=100),
        )

    if "request" not in ConstraintRegistry._soft_constraints:
        ConstraintRegistry._soft_constraints["request"] = ConstraintRegistration(
            constraint_id="request",
            constraint_class=RequestConstraint,
            is_hard=False,
            default_config=ConstraintConfig(enabled=True, is_hard=False, weight=150),
        )

    if "sequence" not in ConstraintRegistry._soft_constraints:
        ConstraintRegistry._soft_constraints["sequence"] = ConstraintRegistration(
            constraint_id="sequence",
            constraint_class=SequenceConstraint,
            is_hard=False,
            default_config=ConstraintConfig(enabled=False, is_hard=False, weight=100),
        )

    if "max_absence" not in ConstraintRegistry._soft_constraints:
        ConstraintRegistry._soft_constraints["max_absence"] = ConstraintRegistration(
            constraint_id="max_absence",
            constraint_class=MaxAbsenceConstraint,
            is_hard=False,
            default_config=ConstraintConfig(enabled=False, is_hard=False, weight=100),
        )

    if "shift_frequency" not in ConstraintRegistry._soft_constraints:
        ConstraintRegistry._soft_constraints["shift_frequency"] = (
            ConstraintRegistration(
                constraint_id="shift_frequency",
                constraint_class=ShiftFrequencyConstraint,
                is_hard=False,
                default_config=ConstraintConfig(
                    enabled=False, is_hard=False, weight=500
                ),
            )
        )

    if "shift_order_preference" not in ConstraintRegistry._soft_constraints:
        ConstraintRegistry._soft_constraints["shift_order_preference"] = (
            ConstraintRegistration(
                constraint_id="shift_order_preference",
                constraint_class=ShiftOrderPreferenceConstraint,
                is_hard=False,
                default_config=ConstraintConfig(
                    enabled=False, is_hard=False, weight=200
                ),
            )
        )

    if "workload" not in ConstraintRegistry._soft_constraints:
        ConstraintRegistry._soft_constraints["workload"] = ConstraintRegistration(
            constraint_id="workload",
            constraint_class=WorkloadConstraint,
            is_hard=False,
            default_config=ConstraintConfig(
                enabled=False,
                is_hard=False,
                weight=100,
                parameters={"min_total_shifts": 0, "max_total_shifts": None},
            ),
        )

    # -- Commercial-parity constraints (all opt-in: enabling a new
    # constraint by default would silently change existing deployments'
    # schedules, so each must be turned on explicitly in config). --

    if "min_rest" not in ConstraintRegistry._soft_constraints:
        ConstraintRegistry._soft_constraints["min_rest"] = ConstraintRegistration(
            constraint_id="min_rest",
            constraint_class=MinRestConstraint,
            is_hard=False,
            default_config=ConstraintConfig(
                enabled=False,
                is_hard=True,
                weight=1000,
                parameters={"min_rest_hours": 11.0},
            ),
        )

    if "max_consecutive" not in ConstraintRegistry._soft_constraints:
        ConstraintRegistry._soft_constraints["max_consecutive"] = (
            ConstraintRegistration(
                constraint_id="max_consecutive",
                constraint_class=MaxConsecutiveConstraint,
                is_hard=False,
                default_config=ConstraintConfig(
                    enabled=False, is_hard=True, weight=100
                ),
            )
        )

    if "shift_succession" not in ConstraintRegistry._soft_constraints:
        ConstraintRegistry._soft_constraints["shift_succession"] = (
            ConstraintRegistration(
                constraint_id="shift_succession",
                constraint_class=ShiftSuccessionConstraint,
                is_hard=False,
                default_config=ConstraintConfig(
                    enabled=False,
                    is_hard=False,
                    weight=100,
                    parameters={"rules": []},
                ),
            )
        )

    if "consecutive_shift_type" not in ConstraintRegistry._soft_constraints:
        ConstraintRegistry._soft_constraints["consecutive_shift_type"] = (
            ConstraintRegistration(
                constraint_id="consecutive_shift_type",
                constraint_class=ConsecutiveShiftTypeConstraint,
                is_hard=False,
                default_config=ConstraintConfig(
                    enabled=False,
                    is_hard=True,
                    weight=100,
                    parameters={"rules": []},
                ),
            )
        )

    if "weekend" not in ConstraintRegistry._soft_constraints:
        ConstraintRegistry._soft_constraints["weekend"] = ConstraintRegistration(
            constraint_id="weekend",
            constraint_class=WeekendConstraint,
            is_hard=False,
            default_config=ConstraintConfig(
                enabled=False,
                is_hard=False,
                weight=150,
                parameters={"weekend_days": [5, 6]},
            ),
        )

    if "preference" not in ConstraintRegistry._soft_constraints:
        ConstraintRegistry._soft_constraints["preference"] = ConstraintRegistration(
            constraint_id="preference",
            constraint_class=PreferenceConstraint,
            is_hard=False,
            default_config=ConstraintConfig(
                enabled=False, is_hard=False, weight=100
            ),
        )

    if "worker_pairing" not in ConstraintRegistry._soft_constraints:
        ConstraintRegistry._soft_constraints["worker_pairing"] = (
            ConstraintRegistration(
                constraint_id="worker_pairing",
                constraint_class=WorkerPairingConstraint,
                is_hard=False,
                default_config=ConstraintConfig(
                    enabled=False,
                    is_hard=False,
                    weight=200,
                    parameters={"rules": []},
                ),
            )
        )
