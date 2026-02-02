"""
Tests for JSON round-trip data integrity (scheduler-74).

Tests that data survives serialization to/from JSON without corruption.
"""

import json
from datetime import time
from typing import Any

import pytest

from shift_solver.models import ShiftType, Worker


class TestWorkerFrozensetRoundTrip:
    """Tests for frozenset serialization via JSON."""

    def test_frozenset_to_json_and_back(self) -> None:
        """Test basic frozenset -> JSON -> frozenset round-trip."""
        original = frozenset(["day", "night", "evening"])

        # Simulate JSON serialization (frozenset -> list -> JSON -> list -> frozenset)
        json_str = json.dumps(list(original))
        loaded = json.loads(json_str)
        restored = frozenset(loaded)

        assert restored == original
        assert isinstance(restored, frozenset)

    def test_empty_frozenset_roundtrip(self) -> None:
        """Test empty frozenset -> JSON -> frozenset (should not become [''])."""
        original = frozenset()

        # Simulate JSON serialization
        json_str = json.dumps(list(original))
        loaded = json.loads(json_str)
        restored = frozenset(loaded) if loaded else frozenset()

        assert restored == original
        assert len(restored) == 0
        assert restored == frozenset()
        # Important: should NOT be frozenset([''])
        assert '' not in restored

    def test_single_element_frozenset(self) -> None:
        """Test single-element frozenset round-trip."""
        original = frozenset(["only_shift"])

        json_str = json.dumps(list(original))
        loaded = json.loads(json_str)
        restored = frozenset(loaded)

        assert restored == original
        assert len(restored) == 1

    def test_worker_with_frozensets_roundtrip(self) -> None:
        """Test Worker model with frozenset fields via JSON simulation."""
        original = Worker(
            id="W001",
            name="Test Worker",
            restricted_shifts=frozenset(["night", "early_morning"]),
            preferred_shifts=frozenset(["day", "evening"]),
        )

        # Simulate DB serialization (frozensets become lists)
        serialized = {
            "id": original.id,
            "name": original.name,
            "restricted_shifts": list(original.restricted_shifts),
            "preferred_shifts": list(original.preferred_shifts),
        }

        json_str = json.dumps(serialized)
        loaded = json.loads(json_str)

        restored = Worker(
            id=loaded["id"],
            name=loaded["name"],
            restricted_shifts=frozenset(loaded.get("restricted_shifts", [])),
            preferred_shifts=frozenset(loaded.get("preferred_shifts", [])),
        )

        assert restored.restricted_shifts == original.restricted_shifts
        assert restored.preferred_shifts == original.preferred_shifts


class TestWorkerAttributesRoundTrip:
    """Tests for Worker attributes dict JSON serialization."""

    def test_simple_dict_attributes(self) -> None:
        """Test simple dict attributes round-trip."""
        original = Worker(
            id="W001",
            name="Test Worker",
            attributes={"skill_level": 5, "department": "Engineering"},
        )

        json_str = json.dumps(original.attributes)
        restored_attrs = json.loads(json_str)

        assert restored_attrs == original.attributes

    def test_nested_dict_attributes(self) -> None:
        """Test nested dict attributes round-trip."""
        attributes: dict[str, Any] = {
            "certifications": {
                "medical": ["CPR", "First Aid"],
                "technical": ["Level 1", "Level 2"],
            },
            "preferences": {
                "location": {"building": "A", "floor": 2},
            },
        }

        original = Worker(
            id="W001",
            name="Test Worker",
            attributes=attributes,
        )

        json_str = json.dumps(original.attributes)
        restored_attrs = json.loads(json_str)

        assert restored_attrs == original.attributes
        assert restored_attrs["certifications"]["medical"] == ["CPR", "First Aid"]
        assert restored_attrs["preferences"]["location"]["floor"] == 2

    def test_empty_dict_attributes(self) -> None:
        """Test empty dict attributes round-trip."""
        original = Worker(
            id="W001",
            name="Test Worker",
            attributes={},
        )

        json_str = json.dumps(original.attributes)
        restored_attrs = json.loads(json_str)

        assert restored_attrs == {}
        assert original.attributes == {}


class TestUnicodePreservation:
    """Tests for Unicode character preservation in JSON."""

    def test_unicode_in_shift_ids(self) -> None:
        """Test non-ASCII characters in shift IDs."""
        original = frozenset(["día", "noche", "日勤", "夜勤", "Früh", "Nacht"])

        json_str = json.dumps(list(original))
        loaded = json.loads(json_str)
        restored = frozenset(loaded)

        assert restored == original
        assert "日勤" in restored
        assert "Früh" in restored

    def test_unicode_in_worker_name(self) -> None:
        """Test Unicode in worker names."""
        original = Worker(
            id="W001",
            name="José García 田中太郎",
            attributes={"greeting": "Здравствуйте"},
        )

        data = {
            "id": original.id,
            "name": original.name,
            "attributes": original.attributes,
        }

        json_str = json.dumps(data, ensure_ascii=False)
        loaded = json.loads(json_str)

        assert loaded["name"] == original.name
        assert "田中太郎" in loaded["name"]
        assert loaded["attributes"]["greeting"] == "Здравствуйте"

    def test_emoji_in_attributes(self) -> None:
        """Test emoji characters in attributes."""
        attributes = {
            "status": "🟢 Active",
            "notes": "⭐ Top performer 🏆",
        }

        json_str = json.dumps(attributes)
        restored = json.loads(json_str)

        assert restored["status"] == "🟢 Active"
        assert "🏆" in restored["notes"]


class TestSpecialCharacters:
    """Tests for special character handling."""

    def test_quotes_in_values(self) -> None:
        """Test quotes in attribute values."""
        attributes = {
            "nickname": 'The "Boss"',
            "notes": "Said 'hello' today",
        }

        json_str = json.dumps(attributes)
        restored = json.loads(json_str)

        assert restored["nickname"] == 'The "Boss"'
        assert restored["notes"] == "Said 'hello' today"

    def test_backslashes_in_values(self) -> None:
        """Test backslashes in attribute values."""
        attributes = {
            "path": "C:\\Users\\worker",
            "regex": "\\d+\\.\\d+",
        }

        json_str = json.dumps(attributes)
        restored = json.loads(json_str)

        assert restored["path"] == "C:\\Users\\worker"
        assert restored["regex"] == "\\d+\\.\\d+"

    def test_newlines_in_values(self) -> None:
        """Test newlines in attribute values."""
        attributes = {
            "notes": "Line 1\nLine 2\nLine 3",
            "address": "Street\n\tCity",
        }

        json_str = json.dumps(attributes)
        restored = json.loads(json_str)

        assert "Line 1\nLine 2" in restored["notes"]
        assert "\n\t" in restored["address"]


class TestLargeData:
    """Tests for handling large data sets."""

    def test_many_shift_ids_in_frozenset(self) -> None:
        """Test frozenset with many shift IDs."""
        # Generate 1000 shift IDs
        original = frozenset(f"shift_{i:04d}" for i in range(1000))

        json_str = json.dumps(list(original))
        loaded = json.loads(json_str)
        restored = frozenset(loaded)

        assert restored == original
        assert len(restored) == 1000
        assert "shift_0500" in restored

    def test_deeply_nested_attributes(self) -> None:
        """Test deeply nested dict structures."""
        attributes: dict[str, Any] = {"level_0": {}}
        current = attributes["level_0"]

        # Create 10 levels of nesting
        for i in range(1, 10):
            current[f"level_{i}"] = {}
            current = current[f"level_{i}"]
        current["value"] = "deep"

        json_str = json.dumps(attributes)
        restored = json.loads(json_str)

        # Verify deep value is preserved
        current = restored["level_0"]
        for i in range(1, 10):
            current = current[f"level_{i}"]
        assert current["value"] == "deep"

    def test_many_attributes(self) -> None:
        """Test dict with many attributes."""
        # 500 attributes
        attributes = {f"attr_{i}": f"value_{i}" for i in range(500)}

        json_str = json.dumps(attributes)
        restored = json.loads(json_str)

        assert len(restored) == 500
        assert restored["attr_250"] == "value_250"


class TestNullVsEmptyHandling:
    """Tests for null vs empty value handling."""

    def test_null_vs_empty_list(self) -> None:
        """Test JSON null vs empty list distinction."""
        data_with_null = {"shifts": None}
        data_with_empty = {"shifts": []}

        json_null = json.dumps(data_with_null)
        json_empty = json.dumps(data_with_empty)

        restored_null = json.loads(json_null)
        restored_empty = json.loads(json_empty)

        assert restored_null["shifts"] is None
        assert restored_empty["shifts"] == []
        assert restored_null["shifts"] != restored_empty["shifts"]

    def test_null_vs_empty_string(self) -> None:
        """Test JSON null vs empty string distinction."""
        data_with_null = {"name": None}
        data_with_empty = {"name": ""}

        json_null = json.dumps(data_with_null)
        json_empty = json.dumps(data_with_empty)

        restored_null = json.loads(json_null)
        restored_empty = json.loads(json_empty)

        assert restored_null["name"] is None
        assert restored_empty["name"] == ""
        assert restored_null["name"] != restored_empty["name"]

    def test_null_vs_empty_dict(self) -> None:
        """Test JSON null vs empty dict distinction."""
        data_with_null = {"attrs": None}
        data_with_empty = {"attrs": {}}

        json_null = json.dumps(data_with_null)
        json_empty = json.dumps(data_with_empty)

        restored_null = json.loads(json_null)
        restored_empty = json.loads(json_empty)

        assert restored_null["attrs"] is None
        assert restored_empty["attrs"] == {}

    def test_frozenset_from_none(self) -> None:
        """Test converting None to frozenset gracefully."""
        data = {"shifts": None}
        json_str = json.dumps(data)
        loaded = json.loads(json_str)

        # Should handle None gracefully
        shifts = frozenset(loaded["shifts"] or [])
        assert shifts == frozenset()
        assert len(shifts) == 0


class TestShiftTypeRequiredAttributes:
    """Tests for ShiftType required_attributes JSON round-trip."""

    def test_required_attributes_simple(self) -> None:
        """Test simple required_attributes round-trip."""
        required = {"certification": "CPR", "experience_years": 2}

        shift = ShiftType(
            id="emergency",
            name="Emergency Shift",
            category="urgent",
            start_time=time(0, 0),
            end_time=time(8, 0),
            duration_hours=8.0,
            workers_required=1,
            required_attributes=required,
        )

        json_str = json.dumps(shift.required_attributes)
        restored = json.loads(json_str)

        assert restored == required
        assert restored["certification"] == "CPR"
        assert restored["experience_years"] == 2

    def test_required_attributes_with_lists(self) -> None:
        """Test required_attributes containing lists."""
        required = {
            "skills": ["driving", "lifting", "first_aid"],
            "clearance_level": 3,
        }

        json_str = json.dumps(required)
        restored = json.loads(json_str)

        assert restored["skills"] == ["driving", "lifting", "first_aid"]
        assert isinstance(restored["skills"], list)


class TestTypePreservation:
    """Tests for data type preservation across JSON round-trips."""

    def test_int_float_distinction(self) -> None:
        """Note: JSON doesn't preserve int/float distinction for integers."""
        data = {"count": 5, "rate": 5.0}

        json_str = json.dumps(data)
        restored = json.loads(json_str)

        # JSON represents both as numbers; 5 and 5.0 are equal in JSON
        assert restored["count"] == 5
        assert restored["rate"] == 5.0

    def test_bool_preservation(self) -> None:
        """Test boolean values are preserved."""
        data = {"active": True, "suspended": False}

        json_str = json.dumps(data)
        restored = json.loads(json_str)

        assert restored["active"] is True
        assert restored["suspended"] is False
        assert isinstance(restored["active"], bool)

    def test_list_vs_tuple_becomes_list(self) -> None:
        """Note: JSON converts tuples to lists."""
        data = {"as_list": [1, 2, 3], "as_tuple": (1, 2, 3)}

        json_str = json.dumps(data)
        restored = json.loads(json_str)

        # Both become lists in JSON
        assert restored["as_list"] == [1, 2, 3]
        assert restored["as_tuple"] == [1, 2, 3]
        assert isinstance(restored["as_tuple"], list)

    def test_frozenset_type_not_preserved(self) -> None:
        """Note: frozenset must be explicitly restored."""
        original = frozenset([1, 2, 3])

        json_str = json.dumps(list(original))
        restored_list = json.loads(json_str)

        # JSON restores as list, not frozenset
        assert isinstance(restored_list, list)
        assert not isinstance(restored_list, frozenset)

        # Must explicitly convert back
        restored_frozenset = frozenset(restored_list)
        assert isinstance(restored_frozenset, frozenset)
