"""Generic display-name generation for sample data.

Per project convention, sample/example data must never resemble real
individuals -- no realistic personal names. Names are generated as a
role label (derived from the worker's `worker_type`, e.g. "nurse" ->
"Nurse") plus the worker's 1-based position in the generated batch, e.g.
"Nurse 3" or "Worker 3" when no worker_type is available.
"""


def generate_worker_name(index: int, worker_type: str | None) -> str:
    """
    Generate a generic, role-flavored display name for a worker.

    Args:
        index: 1-based position of this worker among all generated workers.
        worker_type: The worker's type/role (e.g. "nurse", "full_time").
            Underscores are rendered as spaces and title-cased. Falls back
            to "Worker" when not provided.

    Returns:
        A generic name such as "Nurse 3" or "Worker 3". Unique whenever
        index is unique -- no personal names are ever used.
    """
    label = worker_type.replace("_", " ").title() if worker_type else "Worker"
    return f"{label} {index}"
