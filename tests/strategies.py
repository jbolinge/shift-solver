"""Hypothesis strategies for property-based testing.

Provides composable strategies for generating valid domain objects
that respect all validation rules and invariants.
"""

from datetime import date, time, timedelta
from typing import Any

from hypothesis import strategies as st
from hypothesis.strategies import SearchStrategy

from shift_solver.models import (
    Availability,
    SchedulingRequest,
    ShiftInstance,
    ShiftType,
    Worker,
)

# =============================================================================
# Base strategies for primitive types
# =============================================================================

# IDs: alphanumeric with optional prefix, non-empty
ids = st.text(
    alphabet=st.sampled_from("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"),
    min_size=1,
    max_size=20,
).filter(lambda s: s[0].isalpha())  # Must start with letter

# Names: printable text, non-empty
names = st.text(min_size=1, max_size=50).filter(
    lambda s: s.strip() and not s.isspace()
)

# Worker types
worker_types = st.sampled_from(["full_time", "part_time", "contractor", None])

# Shift categories
shift_categories = st.sampled_from(["day", "night", "evening", "weekend", "holiday"])

# Times (valid time objects)
times = st.builds(
    time,
    hour=st.integers(min_value=0, max_value=23),
    minute=st.sampled_from([0, 15, 30, 45]),
)

# Dates (reasonable range for scheduling)
dates = st.dates(min_value=date(2020, 1, 1), max_value=date(2030, 12, 31))

# Duration hours (positive, reasonable range)
duration_hours = st.floats(min_value=1.0, max_value=24.0, allow_nan=False)

# Workers required (at least 1)
workers_required = st.integers(min_value=1, max_value=10)

# Priority levels (1 = normal, up to 5 = high)
priorities = st.integers(min_value=1, max_value=5)


# =============================================================================
# Shift type IDs (for consistency across related objects)
# =============================================================================


@st.composite
def shift_type_ids(draw: st.DrawFn, max_size: int = 5) -> frozenset[str]:
    """Generate a frozenset of valid shift type IDs."""
    size = draw(st.integers(min_value=0, max_value=max_size))
    id_list = [draw(ids) for _ in range(size)]
    return frozenset(id_list)


# =============================================================================
# Worker strategies
# =============================================================================


@st.composite
def workers(
    draw: st.DrawFn,
    restricted: bool | None = None,
    preferred: bool | None = None,
    with_attributes: bool = False,
) -> Worker:
    """Generate a valid Worker.

    Args:
        draw: Hypothesis draw function
        restricted: Force restricted_shifts to be non-empty (True), empty (False), or random (None)
        preferred: Force preferred_shifts to be non-empty (True), empty (False), or random (None)
        with_attributes: Whether to include random attributes

    Returns:
        A valid Worker instance
    """
    worker_id = draw(ids)
    worker_name = draw(names)
    worker_type = draw(worker_types)

    # Generate potential shift IDs
    all_shift_ids = draw(shift_type_ids(max_size=8))

    # Split into restricted and preferred (ensuring no overlap)
    restricted_shifts: frozenset[str]
    preferred_shifts: frozenset[str]

    if not all_shift_ids:
        restricted_shifts = frozenset()
        preferred_shifts = frozenset()
    else:
        # Randomly partition the shift IDs
        shift_list = list(all_shift_ids)
        draw(st.random_module())

        # Decide partition point
        split_point = draw(st.integers(min_value=0, max_value=len(shift_list)))
        restricted_shifts = frozenset(shift_list[:split_point])
        preferred_shifts = frozenset(shift_list[split_point:])

    # Apply force options
    if restricted is False:
        restricted_shifts = frozenset()
    elif restricted is True and not restricted_shifts:
        restricted_shifts = frozenset([draw(ids)])

    if preferred is False:
        preferred_shifts = frozenset()
    elif preferred is True and not preferred_shifts:
        # Ensure no overlap with restricted
        new_pref = draw(ids)
        while new_pref in restricted_shifts:
            new_pref = draw(ids)
        preferred_shifts = frozenset([new_pref])

    # Generate attributes
    attributes: dict[str, Any] = {}
    if with_attributes:
        num_attrs = draw(st.integers(min_value=0, max_value=3))
        for i in range(num_attrs):
            key = f"attr_{i}"
            value = draw(st.one_of(st.integers(), st.text(max_size=20), st.booleans()))
            attributes[key] = value

    return Worker(
        id=worker_id,
        name=worker_name,
        worker_type=worker_type,
        restricted_shifts=restricted_shifts,
        preferred_shifts=preferred_shifts,
        attributes=attributes,
    )


@st.composite
def worker_lists(
    draw: st.DrawFn,
    min_size: int = 1,
    max_size: int = 20,
) -> list[Worker]:
    """Generate a list of workers with unique IDs."""
    size = draw(st.integers(min_value=min_size, max_value=max_size))
    worker_list: list[Worker] = []
    used_ids: set[str] = set()

    for i in range(size):
        # Generate unique ID
        worker_id = f"W{i:03d}"
        used_ids.add(worker_id)

        worker = draw(workers())
        # Replace ID to ensure uniqueness
        worker = Worker(
            id=worker_id,
            name=worker.name,
            worker_type=worker.worker_type,
            restricted_shifts=worker.restricted_shifts,
            preferred_shifts=worker.preferred_shifts,
            attributes=worker.attributes,
        )
        worker_list.append(worker)

    return worker_list


# =============================================================================
# ShiftType strategies
# =============================================================================


@st.composite
def shift_types(
    draw: st.DrawFn,
    undesirable: bool | None = None,
) -> ShiftType:
    """Generate a valid ShiftType.

    Args:
        draw: Hypothesis draw function
        undesirable: Force is_undesirable (True/False) or random (None)

    Returns:
        A valid ShiftType instance
    """
    shift_id = draw(ids)
    shift_name = draw(names)
    category = draw(shift_categories)
    start = draw(times)
    end = draw(times)
    duration = draw(duration_hours)

    is_undesirable = draw(st.booleans()) if undesirable is None else undesirable

    required = draw(workers_required)

    return ShiftType(
        id=shift_id,
        name=shift_name,
        category=category,
        start_time=start,
        end_time=end,
        duration_hours=duration,
        is_undesirable=is_undesirable,
        workers_required=required,
    )


@st.composite
def shift_type_lists(
    draw: st.DrawFn,
    min_size: int = 1,
    max_size: int = 5,
) -> list[ShiftType]:
    """Generate a list of shift types with unique IDs."""
    size = draw(st.integers(min_value=min_size, max_value=max_size))
    shift_list: list[ShiftType] = []

    for i in range(size):
        shift = draw(shift_types())
        # Replace ID to ensure uniqueness
        shift = ShiftType(
            id=f"shift_{i}",
            name=shift.name,
            category=shift.category,
            start_time=shift.start_time,
            end_time=shift.end_time,
            duration_hours=shift.duration_hours,
            is_undesirable=shift.is_undesirable,
            workers_required=shift.workers_required,
        )
        shift_list.append(shift)

    return shift_list


# =============================================================================
# ShiftInstance strategies
# =============================================================================


@st.composite
def shift_instances(
    draw: st.DrawFn,
    shift_type_id: str | None = None,
    period_index: int | None = None,
    assigned: bool | None = None,
) -> ShiftInstance:
    """Generate a valid ShiftInstance.

    Args:
        draw: Hypothesis draw function
        shift_type_id: Use this shift type ID (or generate random)
        period_index: Use this period index (or generate random)
        assigned: Force assigned (True), unassigned (False), or random (None)

    Returns:
        A valid ShiftInstance
    """
    st_id = shift_type_id or draw(ids)
    p_idx = period_index if period_index is not None else draw(st.integers(min_value=0, max_value=52))
    shift_date = draw(dates)

    worker_id: str | None = None
    if assigned is None:
        if draw(st.booleans()):
            worker_id = draw(ids)
    elif assigned:
        worker_id = draw(ids)

    return ShiftInstance(
        shift_type_id=st_id,
        period_index=p_idx,
        date=shift_date,
        worker_id=worker_id,
    )


# =============================================================================
# Availability strategies
# =============================================================================


@st.composite
def availabilities(
    draw: st.DrawFn,
    worker_id: str | None = None,
    availability_type: str | None = None,
) -> Availability:
    """Generate a valid Availability.

    Args:
        draw: Hypothesis draw function
        worker_id: Use this worker ID (or generate random)
        availability_type: Force type ("unavailable", "preferred", "required") or random

    Returns:
        A valid Availability instance
    """
    w_id = worker_id or draw(ids)
    start = draw(dates)

    # Generate end date >= start date
    days_offset = draw(st.integers(min_value=0, max_value=30))
    end = start + timedelta(days=days_offset)

    if availability_type is None:
        avail_type = draw(st.sampled_from(["unavailable", "preferred", "required"]))
    else:
        avail_type = availability_type

    # Optional shift type restriction
    shift_type_id = draw(st.one_of(st.none(), ids))

    return Availability(
        worker_id=w_id,
        start_date=start,
        end_date=end,
        availability_type=avail_type,  # type: ignore
        shift_type_id=shift_type_id,
    )


@st.composite
def availability_lists(
    draw: st.DrawFn,
    worker_ids: list[str] | None = None,
    min_size: int = 0,
    max_size: int = 10,
) -> list[Availability]:
    """Generate a list of availabilities."""
    size = draw(st.integers(min_value=min_size, max_value=max_size))
    avail_list: list[Availability] = []

    for _ in range(size):
        w_id = draw(st.sampled_from(worker_ids)) if worker_ids else None
        avail = draw(availabilities(worker_id=w_id))
        avail_list.append(avail)

    return avail_list


# =============================================================================
# SchedulingRequest strategies
# =============================================================================


@st.composite
def scheduling_requests(
    draw: st.DrawFn,
    worker_id: str | None = None,
    shift_type_id: str | None = None,
    request_type: str | None = None,
) -> SchedulingRequest:
    """Generate a valid SchedulingRequest.

    Args:
        draw: Hypothesis draw function
        worker_id: Use this worker ID (or generate random)
        shift_type_id: Use this shift type ID (or generate random)
        request_type: Force type ("positive", "negative") or random

    Returns:
        A valid SchedulingRequest instance
    """
    w_id = worker_id or draw(ids)
    st_id = shift_type_id or draw(ids)

    start = draw(dates)
    days_offset = draw(st.integers(min_value=0, max_value=30))
    end = start + timedelta(days=days_offset)

    if request_type is None:
        req_type = draw(st.sampled_from(["positive", "negative"]))
    else:
        req_type = request_type

    priority = draw(priorities)

    return SchedulingRequest(
        worker_id=w_id,
        start_date=start,
        end_date=end,
        request_type=req_type,  # type: ignore
        shift_type_id=st_id,
        priority=priority,
    )


@st.composite
def scheduling_request_lists(
    draw: st.DrawFn,
    worker_ids: list[str] | None = None,
    shift_type_ids: list[str] | None = None,
    min_size: int = 0,
    max_size: int = 10,
) -> list[SchedulingRequest]:
    """Generate a list of scheduling requests."""
    size = draw(st.integers(min_value=min_size, max_value=max_size))
    request_list: list[SchedulingRequest] = []

    for _ in range(size):
        w_id = draw(st.sampled_from(worker_ids)) if worker_ids else None
        st_id = draw(st.sampled_from(shift_type_ids)) if shift_type_ids else None

        req = draw(scheduling_requests(worker_id=w_id, shift_type_id=st_id))
        request_list.append(req)

    return request_list


# =============================================================================
# Period date strategies
# =============================================================================


@st.composite
def period_dates(
    draw: st.DrawFn,
    num_periods: int | None = None,
    period_length_days: int = 7,
) -> list[tuple[date, date]]:
    """Generate a list of period date ranges.

    Args:
        draw: Hypothesis draw function
        num_periods: Number of periods (or generate random 1-12)
        period_length_days: Length of each period in days

    Returns:
        List of (start_date, end_date) tuples
    """
    if num_periods is None:
        num_periods = draw(st.integers(min_value=1, max_value=12))

    start_date = draw(dates)
    periods: list[tuple[date, date]] = []
    current = start_date

    for _ in range(num_periods):
        period_end = current + timedelta(days=period_length_days - 1)
        periods.append((current, period_end))
        current = period_end + timedelta(days=1)

    return periods


# =============================================================================
# Complete scenario strategies
# =============================================================================


@st.composite
def scheduling_scenarios(
    draw: st.DrawFn,
    num_workers: int | None = None,
    num_shift_types: int | None = None,
    num_periods: int | None = None,
) -> dict[str, Any]:
    """Generate a complete scheduling scenario.

    Returns a dictionary with:
    - workers: list of Worker
    - shift_types: list of ShiftType
    - period_dates: list of (start, end) tuples
    - availabilities: list of Availability
    - requests: list of SchedulingRequest
    """
    # Generate workers
    n_workers = num_workers or draw(st.integers(min_value=2, max_value=15))
    scenario_workers = draw(worker_lists(min_size=n_workers, max_size=n_workers))
    worker_ids = [w.id for w in scenario_workers]

    # Generate shift types
    n_shifts = num_shift_types or draw(st.integers(min_value=1, max_value=4))
    scenario_shift_types = draw(shift_type_lists(min_size=n_shifts, max_size=n_shifts))
    shift_type_ids_list = [st.id for st in scenario_shift_types]

    # Generate period dates
    n_periods = num_periods or draw(st.integers(min_value=1, max_value=8))
    scenario_periods = draw(period_dates(num_periods=n_periods))

    # Generate availabilities (referencing valid workers)
    scenario_availabilities = draw(
        availability_lists(worker_ids=worker_ids, max_size=n_workers)
    )

    # Generate requests (referencing valid workers and shift types)
    scenario_requests = draw(
        scheduling_request_lists(
            worker_ids=worker_ids,
            shift_type_ids=shift_type_ids_list,
            max_size=n_workers * 2,
        )
    )

    return {
        "workers": scenario_workers,
        "shift_types": scenario_shift_types,
        "period_dates": scenario_periods,
        "availabilities": scenario_availabilities,
        "requests": scenario_requests,
    }


# =============================================================================
# Convenience strategy instances for common use
# =============================================================================

# Pre-built strategies that can be used directly
any_worker: SearchStrategy[Worker] = workers()
any_shift_type: SearchStrategy[ShiftType] = shift_types()
any_shift_instance: SearchStrategy[ShiftInstance] = shift_instances()
any_availability: SearchStrategy[Availability] = availabilities()
any_request: SearchStrategy[SchedulingRequest] = scheduling_requests()
