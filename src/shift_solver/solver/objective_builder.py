"""ObjectiveBuilder - builds weighted objective from soft constraint violations."""

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ortools.sat.python import cp_model

if TYPE_CHECKING:
    from shift_solver.constraints.base import BaseConstraint


@dataclass
class ObjectiveTerm:
    """A term in the objective function."""

    constraint_id: str
    variable_name: str
    variable: cp_model.IntVar
    base_weight: int
    priority_multiplier: int = 1

    @property
    def effective_weight(self) -> int:
        """Get the effective weight (base * priority)."""
        return self.base_weight * self.priority_multiplier


@dataclass
class ObjectiveBuilder:
    """
    Builds the objective function from soft constraint violations.

    Collects violation variables from all soft constraints and builds
    a minimization objective with weighted penalties.

    Usage:
        builder = ObjectiveBuilder(model)
        builder.add_constraint(fairness_constraint)
        builder.add_constraint(frequency_constraint)
        builder.build()  # Calls model.minimize(...)
    """

    model: cp_model.CpModel
    constraints: list["BaseConstraint"] = field(default_factory=list)
    objective_terms: list[ObjectiveTerm] = field(default_factory=list)

    def add_constraint(self, constraint: "BaseConstraint") -> None:
        """
        Add a constraint to the objective builder.

        Only soft constraints with violation variables contribute to the
        objective. Hard constraints are ignored (they have no violations).

        Args:
            constraint: A constraint that has been applied to the model
        """
        self.constraints.append(constraint)

    def build(self) -> None:
        """
        Build the objective function and apply it to the model.

        Collects all violation variables from soft constraints,
        applies their weights, and creates a minimization objective.
        """
        self.objective_terms.clear()

        for constraint in self.constraints:
            if constraint.is_hard:
                # Hard constraints don't contribute to objective
                continue

            base_weight = constraint.weight

            for var_name, var in constraint.violation_variables.items():
                # Get variable type from metadata (defaults to "violation")
                var_type = constraint.violation_variable_types.get(var_name, "violation")

                # Skip auxiliary variables (helper variables not for objective)
                if var_type == "auxiliary":
                    continue

                # Handle objective_target variables (like fairness spread)
                if var_type == "objective_target":
                    term = ObjectiveTerm(
                        constraint_id=constraint.constraint_id,
                        variable_name=var_name,
                        variable=var,
                        base_weight=base_weight,
                        priority_multiplier=1,
                    )
                    self.objective_terms.append(term)
                    continue

                # Standard violation variables - get priority from metadata or name
                priority = self._get_priority(constraint, var_name)

                term = ObjectiveTerm(
                    constraint_id=constraint.constraint_id,
                    variable_name=var_name,
                    variable=var,
                    base_weight=base_weight,
                    priority_multiplier=priority,
                )
                self.objective_terms.append(term)

        if not self.objective_terms:
            return

        # Build the minimization objective
        objective_expr = sum(
            term.variable * term.effective_weight for term in self.objective_terms
        )
        self.model.minimize(objective_expr)

    def _get_priority(self, constraint: "BaseConstraint", var_name: str) -> int:
        """Get priority from constraint metadata or fallback to name-based extraction."""
        # First check the violation_priorities dict
        if var_name in constraint.violation_priorities:
            return constraint.violation_priorities[var_name]
        # Fallback to regex for backwards compatibility
        return self._extract_priority(var_name)

    def _extract_priority(self, var_name: str) -> int:
        """Extract priority multiplier from variable name (legacy fallback)."""
        # Look for _prioN at end of name
        match = re.search(r"_prio(\d+)$", var_name)
        if match:
            return int(match.group(1))
        return 1

    def get_objective_breakdown(self) -> dict[str, list[ObjectiveTerm]]:
        """
        Get objective terms grouped by constraint ID.

        Useful for debugging and logging.

        Returns:
            Dict mapping constraint_id to list of ObjectiveTerms
        """
        breakdown: dict[str, list[ObjectiveTerm]] = {}
        for term in self.objective_terms:
            if term.constraint_id not in breakdown:
                breakdown[term.constraint_id] = []
            breakdown[term.constraint_id].append(term)
        return breakdown

    def get_total_weight_by_constraint(self) -> dict[str, int]:
        """
        Get the total potential penalty weight by constraint type.

        Returns:
            Dict mapping constraint_id to total weight of all terms
        """
        totals: dict[str, int] = {}
        for term in self.objective_terms:
            if term.constraint_id not in totals:
                totals[term.constraint_id] = 0
            totals[term.constraint_id] += term.effective_weight
        return totals
