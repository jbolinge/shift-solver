"""Integration test fixtures and configuration."""

import pytest

from factories import ScenarioBuilder, ShiftTypeFactory, WorkerFactory


@pytest.fixture
def worker_factory() -> WorkerFactory:
    """Provide a fresh WorkerFactory instance."""
    factory = WorkerFactory()
    yield factory
    factory.reset()


@pytest.fixture
def shift_factory() -> ShiftTypeFactory:
    """Provide a fresh ShiftTypeFactory instance."""
    factory = ShiftTypeFactory()
    yield factory
    factory.reset()


@pytest.fixture
def scenario_builder() -> ScenarioBuilder:
    """Provide a fresh ScenarioBuilder instance."""
    return ScenarioBuilder()


@pytest.fixture
def minimal_feasible_scenario() -> dict:
    """Create a minimal but feasible scheduling scenario.

    1 worker, 1 shift type, 1 period.
    """
    return (
        ScenarioBuilder()
        .with_workers(1)
        .with_shift_types("standard", workers_per_shift=1)
        .with_periods(1)
        .with_schedule_id("MINIMAL-001")
        .build()
    )


@pytest.fixture
def basic_scenario() -> dict:
    """Create a basic scheduling scenario.

    5 workers, standard shifts (day/night/weekend), 4 periods.
    """
    return (
        ScenarioBuilder()
        .with_workers(5)
        .with_shift_types("standard", workers_per_shift=1)
        .with_periods(4)
        .with_constraints("hard_only")
        .with_schedule_id("BASIC-001")
        .build()
    )


@pytest.fixture
def complex_scenario() -> dict:
    """Create a more complex scheduling scenario with constraints.

    10 workers, standard shifts, 8 periods, with availability and requests.
    """
    return (
        ScenarioBuilder()
        .with_workers(10)
        .with_shift_types("standard", workers_per_shift=2)
        .with_periods(8)
        .with_unavailability("W001", period=0)
        .with_unavailability("W002", period=1)
        .with_request("W003", "day", "positive", period=2)
        .with_request("W004", "night", "negative", period=0)
        .with_constraints("all")
        .with_schedule_id("COMPLEX-001")
        .build()
    )
