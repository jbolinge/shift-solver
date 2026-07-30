"""Constraints module for shift-solver."""

from shift_solver.constraints.availability import AvailabilityConstraint
from shift_solver.constraints.base import BaseConstraint, ConstraintConfig
from shift_solver.constraints.consecutive_shift_type import (
    ConsecutiveShiftTypeConstraint,
)
from shift_solver.constraints.coverage import CoverageConstraint
from shift_solver.constraints.fairness import FairnessConstraint
from shift_solver.constraints.frequency import FrequencyConstraint
from shift_solver.constraints.max_absence import MaxAbsenceConstraint
from shift_solver.constraints.max_consecutive import MaxConsecutiveConstraint
from shift_solver.constraints.min_rest import MinRestConstraint
from shift_solver.constraints.pinned import PinnedAssignmentConstraint
from shift_solver.constraints.preference import PreferenceConstraint
from shift_solver.constraints.request import RequestConstraint
from shift_solver.constraints.restriction import RestrictionConstraint
from shift_solver.constraints.sequence import SequenceConstraint
from shift_solver.constraints.shift_frequency import ShiftFrequencyConstraint
from shift_solver.constraints.shift_order_preference import (
    ShiftOrderPreferenceConstraint,
)
from shift_solver.constraints.shift_succession import ShiftSuccessionConstraint
from shift_solver.constraints.skills import SkillsConstraint
from shift_solver.constraints.weekend import WeekendConstraint
from shift_solver.constraints.worker_pairing import WorkerPairingConstraint
from shift_solver.constraints.worker_shift_limit import WorkerShiftLimitConstraint
from shift_solver.constraints.workload import WorkloadConstraint

__all__ = [
    "BaseConstraint",
    "ConstraintConfig",
    "AvailabilityConstraint",
    "ConsecutiveShiftTypeConstraint",
    "CoverageConstraint",
    "FairnessConstraint",
    "FrequencyConstraint",
    "MaxAbsenceConstraint",
    "MaxConsecutiveConstraint",
    "MinRestConstraint",
    "PinnedAssignmentConstraint",
    "PreferenceConstraint",
    "RequestConstraint",
    "RestrictionConstraint",
    "SequenceConstraint",
    "ShiftFrequencyConstraint",
    "ShiftOrderPreferenceConstraint",
    "ShiftSuccessionConstraint",
    "SkillsConstraint",
    "WeekendConstraint",
    "WorkerPairingConstraint",
    "WorkloadConstraint",
    "WorkerShiftLimitConstraint",
]
