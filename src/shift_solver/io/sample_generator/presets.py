"""Industry presets for sample data generation."""

from dataclasses import dataclass
from datetime import time
from typing import Any


@dataclass
class IndustryPreset:
    """Configuration preset for an industry."""

    name: str
    shift_types: list[dict[str, Any]]
    worker_types: list[str]
    restriction_probability: float = 0.1
    vacation_probability: float = 0.15
    request_probability: float = 0.2

    @classmethod
    def get(cls, industry: str) -> "IndustryPreset":
        """Get preset for an industry."""
        presets = {
            "retail": cls._retail_preset(),
            "healthcare": cls._healthcare_preset(),
            "warehouse": cls._warehouse_preset(),
        }
        if industry not in presets:
            raise ValueError(
                f"Unknown industry '{industry}'. Available: {list(presets.keys())}"
            )
        return presets[industry]

    @classmethod
    def _retail_preset(cls) -> "IndustryPreset":
        """Retail industry preset."""
        return cls(
            name="retail",
            shift_types=[
                {
                    "id": "morning",
                    "name": "Morning Shift",
                    "category": "day",
                    "start_time": time(6, 0),
                    "end_time": time(14, 0),
                    "duration_hours": 8.0,
                    "workers_required": 3,
                    "is_undesirable": False,
                },
                {
                    "id": "afternoon",
                    "name": "Afternoon Shift",
                    "category": "day",
                    "start_time": time(14, 0),
                    "end_time": time(22, 0),
                    "duration_hours": 8.0,
                    "workers_required": 4,
                    "is_undesirable": False,
                },
                {
                    "id": "night",
                    "name": "Night Shift",
                    "category": "night",
                    "start_time": time(22, 0),
                    "end_time": time(6, 0),
                    "duration_hours": 8.0,
                    "workers_required": 2,
                    "is_undesirable": True,
                },
                {
                    "id": "weekend",
                    "name": "Weekend Shift",
                    "category": "weekend",
                    "start_time": time(10, 0),
                    "end_time": time(18, 0),
                    "duration_hours": 8.0,
                    "workers_required": 5,
                    "is_undesirable": True,
                },
            ],
            worker_types=["full_time", "part_time", "seasonal"],
            restriction_probability=0.15,
            vacation_probability=0.1,
            request_probability=0.15,
        )

    @classmethod
    def _healthcare_preset(cls) -> "IndustryPreset":
        """Healthcare industry preset."""
        return cls(
            name="healthcare",
            shift_types=[
                {
                    "id": "day",
                    "name": "Day Shift",
                    "category": "day",
                    "start_time": time(7, 0),
                    "end_time": time(19, 0),
                    "duration_hours": 12.0,
                    "workers_required": 4,
                    "is_undesirable": False,
                },
                {
                    "id": "night",
                    "name": "Night Shift",
                    "category": "night",
                    "start_time": time(19, 0),
                    "end_time": time(7, 0),
                    "duration_hours": 12.0,
                    "workers_required": 3,
                    "is_undesirable": True,
                },
                {
                    "id": "on_call",
                    "name": "On-Call",
                    "category": "on_call",
                    "start_time": time(0, 0),
                    "end_time": time(23, 59),
                    "duration_hours": 24.0,
                    "workers_required": 1,
                    "is_undesirable": True,
                },
            ],
            worker_types=["physician", "nurse", "resident"],
            restriction_probability=0.2,
            vacation_probability=0.12,
            request_probability=0.25,
        )

    @classmethod
    def _warehouse_preset(cls) -> "IndustryPreset":
        """Warehouse industry preset."""
        return cls(
            name="warehouse",
            shift_types=[
                {
                    "id": "first",
                    "name": "First Shift",
                    "category": "day",
                    "start_time": time(6, 0),
                    "end_time": time(14, 0),
                    "duration_hours": 8.0,
                    "workers_required": 8,
                    "is_undesirable": False,
                },
                {
                    "id": "second",
                    "name": "Second Shift",
                    "category": "evening",
                    "start_time": time(14, 0),
                    "end_time": time(22, 0),
                    "duration_hours": 8.0,
                    "workers_required": 6,
                    "is_undesirable": False,
                },
                {
                    "id": "third",
                    "name": "Third Shift",
                    "category": "night",
                    "start_time": time(22, 0),
                    "end_time": time(6, 0),
                    "duration_hours": 8.0,
                    "workers_required": 4,
                    "is_undesirable": True,
                },
            ],
            worker_types=["forklift_operator", "picker", "supervisor"],
            restriction_probability=0.1,
            vacation_probability=0.08,
            request_probability=0.1,
        )
