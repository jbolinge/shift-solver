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
        CoverageConstraint,
        FairnessConstraint,
        FrequencyConstraint,
        MaxAbsenceConstraint,
        RequestConstraint,
        RestrictionConstraint,
        SequenceConstraint,
        ShiftFrequencyConstraint,
        ShiftOrderPreferenceConstraint,
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
        ConstraintRegistry._soft_constraints["shift_frequency"] = ConstraintRegistration(
            constraint_id="shift_frequency",
            constraint_class=ShiftFrequencyConstraint,
            is_hard=False,
            default_config=ConstraintConfig(enabled=False, is_hard=False, weight=500),
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
