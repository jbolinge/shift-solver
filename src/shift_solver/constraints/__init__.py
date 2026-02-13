"""Constraints module for shift-solver."""

from shift_solver.constraints.availability import AvailabilityConstraint
from shift_solver.constraints.base import BaseConstraint, ConstraintConfig
from shift_solver.constraints.coverage import CoverageConstraint
from shift_solver.constraints.fairness import FairnessConstraint
from shift_solver.constraints.frequency import FrequencyConstraint
from shift_solver.constraints.max_absence import MaxAbsenceConstraint
from shift_solver.constraints.request import RequestConstraint
from shift_solver.constraints.restriction import RestrictionConstraint
from shift_solver.constraints.sequence import SequenceConstraint
from shift_solver.constraints.shift_frequency import ShiftFrequencyConstraint
from shift_solver.constraints.shift_order_preference import (
    ShiftOrderPreferenceConstraint,
)

__all__ = [
    "BaseConstraint",
    "ConstraintConfig",
    "AvailabilityConstraint",
    "CoverageConstraint",
    "FairnessConstraint",
    "FrequencyConstraint",
    "MaxAbsenceConstraint",
    "RequestConstraint",
    "RestrictionConstraint",
    "SequenceConstraint",
    "ShiftFrequencyConstraint",
    "ShiftOrderPreferenceConstraint",
]
