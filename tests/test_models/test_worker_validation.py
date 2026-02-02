"""Tests for Worker validation of restriction/preference conflicts.

These tests verify that a shift cannot appear in both restricted_shifts
and preferred_shifts, as this is a logical contradiction.

Issue: scheduler-77
"""

import pytest

from shift_solver.models.worker import Worker


class TestRestrictionPreferenceConflict:
    """Tests for detecting conflicts between restricted and preferred shifts."""

    def test_same_shift_in_both_raises_error(self) -> None:
        """A shift in both restricted_shifts and preferred_shifts should raise error."""
        with pytest.raises(ValueError, match="cannot be both restricted and preferred"):
            Worker(
                id="W001",
                name="Test Worker",
                restricted_shifts=frozenset({"day"}),
                preferred_shifts=frozenset({"day"}),
            )

    def test_multiple_conflicting_shifts_raises_error(self) -> None:
        """Multiple conflicting shifts should be reported in error."""
        with pytest.raises(ValueError, match="cannot be both restricted and preferred"):
            Worker(
                id="W001",
                name="Test Worker",
                restricted_shifts=frozenset({"day", "night"}),
                preferred_shifts=frozenset({"day", "night", "evening"}),
            )

    def test_partial_overlap_raises_error(self) -> None:
        """Partial overlap between sets should raise error."""
        with pytest.raises(ValueError, match="cannot be both restricted and preferred.*day"):
            Worker(
                id="W001",
                name="Test Worker",
                restricted_shifts=frozenset({"day", "night"}),
                preferred_shifts=frozenset({"day", "morning"}),
            )

    def test_disjoint_sets_allowed(self) -> None:
        """Disjoint restricted and preferred sets should be valid."""
        worker = Worker(
            id="W001",
            name="Test Worker",
            restricted_shifts=frozenset({"night", "weekend"}),
            preferred_shifts=frozenset({"day", "morning"}),
        )
        assert worker.restricted_shifts == frozenset({"night", "weekend"})
        assert worker.preferred_shifts == frozenset({"day", "morning"})

    def test_empty_sets_allowed(self) -> None:
        """Empty restricted or preferred sets should be valid."""
        # Both empty
        worker1 = Worker(id="W001", name="Test")
        assert worker1.restricted_shifts == frozenset()
        assert worker1.preferred_shifts == frozenset()

        # One empty
        worker2 = Worker(
            id="W002",
            name="Test",
            restricted_shifts=frozenset({"night"}),
        )
        assert worker2.restricted_shifts == frozenset({"night"})
        assert worker2.preferred_shifts == frozenset()

        # Other empty
        worker3 = Worker(
            id="W003",
            name="Test",
            preferred_shifts=frozenset({"day"}),
        )
        assert worker3.restricted_shifts == frozenset()
        assert worker3.preferred_shifts == frozenset({"day"})

    def test_error_message_includes_conflicting_shifts(self) -> None:
        """Error message should include the conflicting shift IDs."""
        with pytest.raises(ValueError) as exc_info:
            Worker(
                id="W001",
                name="Test Worker",
                restricted_shifts=frozenset({"day", "night"}),
                preferred_shifts=frozenset({"day", "evening"}),
            )

        error_msg = str(exc_info.value)
        assert "day" in error_msg
        # Should not mention non-conflicting shifts
        assert "night" not in error_msg or "evening" not in error_msg


class TestCanWorkShiftWithPreference:
    """Tests for interaction between can_work_shift and prefers_shift."""

    def test_can_work_and_prefer_same_shift(self) -> None:
        """A worker can prefer a shift they're allowed to work."""
        worker = Worker(
            id="W001",
            name="Test",
            preferred_shifts=frozenset({"day"}),
        )
        assert worker.can_work_shift("day")
        assert worker.prefers_shift("day")

    def test_restricted_shift_cannot_be_preferred(self) -> None:
        """A restricted shift should not be preferrable (enforced at creation)."""
        # This test documents that the validation prevents this state
        # Worker creation would fail if we try to create this invalid state
        pass  # Covered by test_same_shift_in_both_raises_error

    def test_unrestricted_unprefered_shift(self) -> None:
        """A shift can be workable but not preferred."""
        worker = Worker(
            id="W001",
            name="Test",
            restricted_shifts=frozenset({"night"}),
            preferred_shifts=frozenset({"day"}),
        )
        # evening is neither restricted nor preferred
        assert worker.can_work_shift("evening")
        assert not worker.prefers_shift("evening")
