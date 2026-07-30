"""Tests for the is_eligible() worker/shift eligibility helper."""

from datetime import time

from shift_solver.models.eligibility import is_eligible
from shift_solver.models.shift import ShiftType
from shift_solver.models.worker import Worker


def _shift_type(**overrides: object) -> ShiftType:
    """Build a ShiftType with sensible defaults, overridable per test."""
    defaults: dict[str, object] = {
        "id": "night_shift",
        "name": "Night Shift",
        "category": "night",
        "start_time": time(23, 0),
        "end_time": time(7, 0),
        "duration_hours": 8.0,
    }
    defaults.update(overrides)
    return ShiftType(**defaults)  # type: ignore[arg-type]


class TestIsEligible:
    """Tests for is_eligible()."""

    def test_no_restrictions_no_required_attributes(self) -> None:
        """Worker with no restrictions is eligible for an unconstrained shift."""
        worker = Worker(id="worker_1", name="Worker 1")
        shift_type = _shift_type()

        assert is_eligible(worker, shift_type) is True

    def test_restricted_worker_ineligible(self) -> None:
        """A worker restricted from the shift type is ineligible regardless of skills."""
        worker = Worker(
            id="worker_1", name="Worker 1", restricted_shifts=frozenset(["night_shift"])
        )
        shift_type = _shift_type()

        assert is_eligible(worker, shift_type) is False

    def test_matching_required_attributes_eligible(self) -> None:
        """Worker whose attributes satisfy every required key/value pair is eligible."""
        worker = Worker(id="worker_1", name="Worker 1", attributes={"skill": "acls"})
        shift_type = _shift_type(required_attributes={"skill": "acls"})

        assert is_eligible(worker, shift_type) is True

    def test_missing_required_attribute_ineligible(self) -> None:
        """Worker missing a required attribute key is ineligible."""
        worker = Worker(id="worker_1", name="Worker 1")
        shift_type = _shift_type(required_attributes={"skill": "acls"})

        assert is_eligible(worker, shift_type) is False

    def test_mismatched_required_attribute_value_ineligible(self) -> None:
        """Worker with the attribute key present but wrong value is ineligible."""
        worker = Worker(id="worker_1", name="Worker 1", attributes={"skill": "bls"})
        shift_type = _shift_type(required_attributes={"skill": "acls"})

        assert is_eligible(worker, shift_type) is False

    def test_extra_attributes_ignored(self) -> None:
        """Worker attributes beyond what's required don't affect eligibility."""
        worker = Worker(
            id="worker_1",
            name="Worker 1",
            attributes={"skill": "acls", "department": "clinic_a"},
        )
        shift_type = _shift_type(required_attributes={"skill": "acls"})

        assert is_eligible(worker, shift_type) is True

    def test_partial_multi_attribute_match_ineligible(self) -> None:
        """All required key/value pairs must match, not just some."""
        worker = Worker(id="worker_1", name="Worker 1", attributes={"skill": "acls"})
        shift_type = _shift_type(
            required_attributes={"skill": "acls", "department": "clinic_a"}
        )

        assert is_eligible(worker, shift_type) is False

    def test_restricted_and_skill_ineligible(self) -> None:
        """Worker both restricted and missing a required attribute is ineligible."""
        worker = Worker(
            id="worker_1", name="Worker 1", restricted_shifts=frozenset(["night_shift"])
        )
        shift_type = _shift_type(required_attributes={"skill": "acls"})

        assert is_eligible(worker, shift_type) is False

    def test_matches_skills_constraint_semantics(self) -> None:
        """
        is_eligible mirrors SkillsConstraint._worker_qualifies (dict.get
        comparison): a missing key behaves identically to a present key
        with a mismatched value.
        """
        worker_missing_key = Worker(id="worker_1", name="Worker 1", attributes={})
        worker_wrong_value = Worker(
            id="worker_2", name="Worker 2", attributes={"skill": None}
        )
        shift_type = _shift_type(required_attributes={"skill": "acls"})

        assert is_eligible(worker_missing_key, shift_type) is False
        assert is_eligible(worker_wrong_value, shift_type) is False
