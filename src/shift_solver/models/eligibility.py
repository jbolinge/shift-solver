"""Worker/shift eligibility - combines restriction and skill-matching checks.

Several parts of the codebase need to know whether a worker could ever be
assigned to a shift type, independent of any particular period. Two
separate things gate that:

- Worker.can_work_shift(): the worker isn't on the shift type's
  restricted-worker list.
- SkillsConstraint's attribute matching: the worker's attributes satisfy
  every key/value pair in the shift type's required_attributes.

Callers that only check the first (e.g. via worker.can_work_shift() alone)
can treat a worker as "eligible" for preference/goal purposes even though
SkillsConstraint will always force their assignment variable to 0 for that
shift type - producing an indicator that can never be satisfied. is_eligible
combines both checks so callers get a single, correct answer.
"""

from shift_solver.models.shift import ShiftType
from shift_solver.models.worker import Worker


def is_eligible(worker: Worker, shift_type: ShiftType) -> bool:
    """
    Check whether a worker could ever be assigned to a shift type.

    A worker is eligible only if both hold:
    - worker.can_work_shift(shift_type.id) - the worker isn't restricted
      from the shift type.
    - Every key/value pair in shift_type.required_attributes matches the
      worker's attributes. Mirrors SkillsConstraint._worker_qualifies
      exactly (dict.get comparison, so a missing attribute key is treated
      the same as one whose value doesn't match).

    Args:
        worker: Worker to check.
        shift_type: ShiftType to check eligibility for.

    Returns:
        True if the worker is both unrestricted and skill-qualified for
        the shift type.
    """
    if not worker.can_work_shift(shift_type.id):
        return False

    return all(
        worker.attributes.get(key) == value
        for key, value in shift_type.required_attributes.items()
    )
