"""Base class for all constraints."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from ortools.sat.python import cp_model

if TYPE_CHECKING:
    from shift_solver.solver.types import SolverVariables


@dataclass
class ConstraintConfig:
    """Configuration for a constraint."""

    enabled: bool = True
    is_hard: bool = True
    weight: int = 100
    parameters: dict[str, Any] | None = None

    def get_param(self, key: str, default: Any = None) -> Any:
        """Get a parameter value with a default."""
        if self.parameters is None:
            return default
        return self.parameters.get(key, default)


class BaseConstraint(ABC):
    """
    Abstract base class for all constraints.

    Constraints encapsulate the logic for adding specific scheduling rules
    to the OR-Tools model. Each constraint has:
    - A unique constraint_id
    - Configuration (enabled, hard/soft, weight, parameters)
    - An apply() method that adds constraints to the model
    """

    constraint_id: str = "base"

    def __init__(
        self,
        model: cp_model.CpModel,
        variables: "SolverVariables",
        config: ConstraintConfig | None = None,
    ) -> None:
        """
        Initialize the constraint.

        Args:
            model: OR-Tools CP model to add constraints to
            variables: SolverVariables container
            config: Constraint configuration (uses defaults if None)
        """
        self.model = model
        self.variables = variables
        self.config = config or ConstraintConfig()
        self._constraint_count = 0
        self._violation_variables: dict[str, cp_model.IntVar] = {}
        self._violation_priorities: dict[str, int] = {}
        self._violation_variable_types: dict[str, str] = {}

    @property
    def is_enabled(self) -> bool:
        """Check if this constraint is enabled."""
        return self.config.enabled

    @property
    def is_hard(self) -> bool:
        """Check if this is a hard constraint."""
        return self.config.is_hard

    @property
    def weight(self) -> int:
        """Get the weight for soft constraint violations."""
        return self.config.weight

    @property
    def constraint_count(self) -> int:
        """Get the number of constraints added."""
        return self._constraint_count

    @property
    def violation_variables(self) -> dict[str, cp_model.IntVar]:
        """Get violation variables (for soft constraints)."""
        return self._violation_variables

    @property
    def violation_priorities(self) -> dict[str, int]:
        """Get priority multipliers for violation variables."""
        return self._violation_priorities

    @property
    def violation_variable_types(self) -> dict[str, str]:
        """
        Get the types of violation variables.

        Variable types:
        - "violation": Standard violation variable to include in objective (default)
        - "objective_target": Explicit target for objective (e.g., spread to minimize)
        - "auxiliary": Helper variable not for objective (e.g., max/min intermediates)
        """
        return self._violation_variable_types

    @abstractmethod
    def apply(self, **context: Any) -> None:
        """
        Apply this constraint to the model.

        Subclasses must implement this method to add their specific
        constraints to the OR-Tools model.

        Args:
            **context: Additional context needed by the constraint
                (e.g., workers, shift_types, availabilities)
        """
        pass

    def _add_hard_constraint(self, _constraint: cp_model.Constraint) -> None:
        """Add a hard constraint and increment counter."""
        self._constraint_count += 1

    def _create_violation_var(self, name: str) -> cp_model.IntVar:
        """Create and track a violation variable for soft constraints."""
        var = self.model.new_bool_var(f"{self.constraint_id}_{name}")
        self._violation_variables[name] = var
        return var
