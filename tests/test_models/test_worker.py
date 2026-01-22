"""Tests for the Worker model."""

import pytest
from hypothesis import given, strategies as st

from shift_solver.models.worker import Worker


class TestWorker:
    """Tests for Worker dataclass."""

    def test_create_worker_minimal(self) -> None:
        """Worker can be created with just id and name."""
        worker = Worker(id="W001", name="John Doe")

        assert worker.id == "W001"
        assert worker.name == "John Doe"
        assert worker.worker_type is None
        assert worker.restricted_shifts == frozenset()
        assert worker.preferred_shifts == frozenset()
        assert worker.attributes == {}

    def test_create_worker_with_all_fields(self) -> None:
        """Worker can be created with all optional fields."""
        worker = Worker(
            id="W002",
            name="Jane Smith",
            worker_type="full_time",
            restricted_shifts=frozenset(["night_shift", "weekend"]),
            preferred_shifts=frozenset(["day_shift"]),
            attributes={"department": "Sales", "seniority": 5},
        )

        assert worker.id == "W002"
        assert worker.name == "Jane Smith"
        assert worker.worker_type == "full_time"
        assert "night_shift" in worker.restricted_shifts
        assert "weekend" in worker.restricted_shifts
        assert "day_shift" in worker.preferred_shifts
        assert worker.attributes["department"] == "Sales"
        assert worker.attributes["seniority"] == 5

    def test_worker_is_frozen(self) -> None:
        """Worker should be immutable (frozen dataclass)."""
        worker = Worker(id="W001", name="Test")

        with pytest.raises(AttributeError):
            worker.name = "Changed"  # type: ignore[misc]

    def test_worker_equality(self) -> None:
        """Two workers with same fields should be equal."""
        worker1 = Worker(id="W001", name="Test")
        worker2 = Worker(id="W001", name="Test")

        assert worker1 == worker2

    def test_worker_hash(self) -> None:
        """Worker should be hashable for use in sets/dicts."""
        worker1 = Worker(id="W001", name="Test")
        worker2 = Worker(id="W002", name="Test2")

        worker_set = {worker1, worker2}
        assert len(worker_set) == 2
        assert worker1 in worker_set

    def test_can_work_shift_no_restrictions(self) -> None:
        """Worker with no restrictions can work any shift."""
        worker = Worker(id="W001", name="Test")

        assert worker.can_work_shift("day_shift")
        assert worker.can_work_shift("night_shift")
        assert worker.can_work_shift("weekend")

    def test_can_work_shift_with_restrictions(self) -> None:
        """Worker cannot work restricted shifts."""
        worker = Worker(
            id="W001",
            name="Test",
            restricted_shifts=frozenset(["night_shift", "weekend"]),
        )

        assert worker.can_work_shift("day_shift")
        assert not worker.can_work_shift("night_shift")
        assert not worker.can_work_shift("weekend")

    def test_prefers_shift(self) -> None:
        """Check if worker prefers a shift."""
        worker = Worker(
            id="W001",
            name="Test",
            preferred_shifts=frozenset(["day_shift"]),
        )

        assert worker.prefers_shift("day_shift")
        assert not worker.prefers_shift("night_shift")

    @given(
        worker_id=st.text(min_size=1, max_size=20),
        name=st.text(min_size=1, max_size=50),
    )
    def test_worker_creation_property(self, worker_id: str, name: str) -> None:
        """Property test: Worker creation always succeeds with valid strings."""
        worker = Worker(id=worker_id, name=name)

        assert worker.id == worker_id
        assert worker.name == name


class TestWorkerValidation:
    """Tests for Worker validation."""

    def test_worker_id_cannot_be_empty(self) -> None:
        """Worker id should not be empty."""
        with pytest.raises(ValueError, match="id cannot be empty"):
            Worker(id="", name="Test")

    def test_worker_name_cannot_be_empty(self) -> None:
        """Worker name should not be empty."""
        with pytest.raises(ValueError, match="name cannot be empty"):
            Worker(id="W001", name="")
