"""Core sample data generation logic."""

import random
from datetime import date, timedelta

from shift_solver.io.sample_generator.exporters import SampleExporterMixin
from shift_solver.io.sample_generator.names import FIRST_NAMES, LAST_NAMES
from shift_solver.io.sample_generator.presets import IndustryPreset
from shift_solver.models import Availability, SchedulingRequest, ShiftType, Worker


class SampleGenerator(SampleExporterMixin):
    """
    Generates sample scheduling data for different industries.

    Supports generating:
    - Workers with realistic names and types
    - Shift types based on industry presets
    - Availability records (vacations, time-off)
    - Scheduling requests

    Usage:
        gen = SampleGenerator(industry="retail", seed=42)
        workers = gen.generate_workers(num_workers=20)
        shift_types = gen.generate_shift_types()
        gen.generate_to_csv(output_dir, num_workers=20, start_date, end_date)
    """

    def __init__(self, industry: str = "retail", seed: int | None = None) -> None:
        """
        Initialize sample generator.

        Args:
            industry: Industry preset to use (retail, healthcare, warehouse)
            seed: Random seed for reproducibility
        """
        self.preset = IndustryPreset.get(industry)
        self.rng = random.Random(seed)

    def generate_workers(self, num_workers: int) -> list[Worker]:
        """
        Generate sample workers.

        Args:
            num_workers: Number of workers to generate

        Returns:
            List of Worker objects
        """
        workers = []
        used_names: set[str] = set()

        for i in range(num_workers):
            worker_id = f"W{i + 1:03d}"

            # Generate unique name
            name = self._generate_unique_name(used_names)
            used_names.add(name)

            # Random worker type
            worker_type = self.rng.choice(self.preset.worker_types)

            # Random restrictions
            restricted_shifts: frozenset[str] = frozenset()
            if self.rng.random() < self.preset.restriction_probability:
                # Pick 1-2 shifts to restrict
                shift_ids = [st["id"] for st in self.preset.shift_types]
                num_restrictions = self.rng.randint(1, min(2, len(shift_ids)))
                restricted_shifts = frozenset(
                    self.rng.sample(shift_ids, num_restrictions)
                )

            workers.append(
                Worker(
                    id=worker_id,
                    name=name,
                    worker_type=worker_type,
                    restricted_shifts=restricted_shifts,
                )
            )

        return workers

    def generate_shift_types(self) -> list[ShiftType]:
        """
        Generate shift types from industry preset.

        Returns:
            List of ShiftType objects
        """
        return [
            ShiftType(
                id=st["id"],
                name=st["name"],
                category=st["category"],
                start_time=st["start_time"],
                end_time=st["end_time"],
                duration_hours=st["duration_hours"],
                workers_required=st["workers_required"],
                is_undesirable=st.get("is_undesirable", False),
            )
            for st in self.preset.shift_types
        ]

    def generate_availability(
        self,
        workers: list[Worker],
        start_date: date,
        end_date: date,
    ) -> list[Availability]:
        """
        Generate availability records (vacations, time-off).

        Args:
            workers: List of workers
            start_date: Schedule start date
            end_date: Schedule end date

        Returns:
            List of Availability objects (unavailable periods)
        """
        availabilities = []
        total_days = (end_date - start_date).days + 1

        for worker in workers:
            # Decide if worker has vacation
            if self.rng.random() < self.preset.vacation_probability:
                # Generate 1-2 vacation periods
                num_vacations = self.rng.randint(1, 2)

                for _ in range(num_vacations):
                    # Random vacation length (3-10 days)
                    vacation_length = self.rng.randint(3, 10)

                    # Random start within the period
                    max_start_offset = max(0, total_days - vacation_length - 1)
                    if max_start_offset <= 0:
                        continue

                    start_offset = self.rng.randint(0, max_start_offset)
                    vac_start = start_date + timedelta(days=start_offset)
                    vac_end = vac_start + timedelta(days=vacation_length - 1)

                    availabilities.append(
                        Availability(
                            worker_id=worker.id,
                            start_date=vac_start,
                            end_date=vac_end,
                            availability_type="unavailable",
                        )
                    )

        return availabilities

    def generate_requests(
        self,
        workers: list[Worker],
        shift_types: list[ShiftType],
        start_date: date,
        end_date: date,
    ) -> list[SchedulingRequest]:
        """
        Generate scheduling requests.

        Args:
            workers: List of workers
            shift_types: List of shift types
            start_date: Schedule start date
            end_date: Schedule end date

        Returns:
            List of SchedulingRequest objects
        """
        requests = []
        total_days = (end_date - start_date).days + 1

        for worker in workers:
            # Decide if worker has requests
            if self.rng.random() < self.preset.request_probability:
                # Generate 1-3 requests
                num_requests = self.rng.randint(1, 3)

                for _ in range(num_requests):
                    # Random request type
                    request_type = self.rng.choice(["positive", "negative"])

                    # Random shift type
                    shift_type = self.rng.choice(shift_types)

                    # Random date
                    day_offset = self.rng.randint(0, total_days - 1)
                    req_date = start_date + timedelta(days=day_offset)

                    # Random priority (1-3)
                    priority = self.rng.randint(1, 3)

                    requests.append(
                        SchedulingRequest(
                            worker_id=worker.id,
                            start_date=req_date,
                            end_date=req_date,
                            request_type=request_type,  # type: ignore
                            shift_type_id=shift_type.id,
                            priority=priority,
                        )
                    )

        return requests

    def _generate_unique_name(self, used_names: set[str]) -> str:
        """Generate a unique full name."""
        for _ in range(100):  # Max attempts
            first = self.rng.choice(FIRST_NAMES)
            last = self.rng.choice(LAST_NAMES)
            name = f"{first} {last}"
            if name not in used_names:
                return name

        # Fallback with number suffix
        first = self.rng.choice(FIRST_NAMES)
        last = self.rng.choice(LAST_NAMES)
        return f"{first} {last} {len(used_names)}"
