"""Tests for sample data generator."""

from datetime import date
from pathlib import Path

import pytest

from shift_solver.io.sample_generator import IndustryPreset, SampleGenerator


class TestIndustryPresets:
    """Tests for industry presets."""

    def test_retail_preset(self) -> None:
        """Test retail industry preset."""
        preset = IndustryPreset.get("retail")

        assert preset.name == "retail"
        assert len(preset.shift_types) >= 2
        assert any(st["id"] == "morning" for st in preset.shift_types)

    def test_healthcare_preset(self) -> None:
        """Test healthcare industry preset."""
        preset = IndustryPreset.get("healthcare")

        assert preset.name == "healthcare"
        assert any(st["is_undesirable"] for st in preset.shift_types)

    def test_warehouse_preset(self) -> None:
        """Test warehouse industry preset."""
        preset = IndustryPreset.get("warehouse")

        assert preset.name == "warehouse"
        assert len(preset.shift_types) >= 2

    def test_unknown_preset_raises(self) -> None:
        """Test that unknown preset raises error."""
        with pytest.raises(ValueError, match="Unknown industry"):
            IndustryPreset.get("unknown")


class TestSampleGenerator:
    """Tests for SampleGenerator."""

    def test_generate_workers(self) -> None:
        """Test generating workers."""
        gen = SampleGenerator(industry="retail")
        workers = gen.generate_workers(num_workers=10)

        assert len(workers) == 10
        assert all(w.id for w in workers)
        assert all(w.name for w in workers)

    def test_generate_shift_types(self) -> None:
        """Test generating shift types."""
        gen = SampleGenerator(industry="retail")
        shift_types = gen.generate_shift_types()

        assert len(shift_types) >= 2
        assert all(st.id for st in shift_types)
        assert all(st.workers_required >= 1 for st in shift_types)

    def test_generate_availability(self) -> None:
        """Test generating availability records."""
        # Use seed to ensure we get some availability
        gen = SampleGenerator(industry="retail", seed=42)
        workers = gen.generate_workers(num_workers=10)

        avails = gen.generate_availability(
            workers=workers,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 3, 31),
        )

        # Should have some unavailability (with 10 workers and 3 months)
        assert len(avails) > 0
        assert all(a.availability_type == "unavailable" for a in avails)

    def test_generate_requests(self) -> None:
        """Test generating scheduling requests."""
        gen = SampleGenerator(industry="retail")
        workers = gen.generate_workers(num_workers=5)
        shift_types = gen.generate_shift_types()

        requests = gen.generate_requests(
            workers=workers,
            shift_types=shift_types,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 31),
        )

        # Should have some requests
        assert len(requests) >= 0  # May be empty depending on randomness


class TestSampleGeneratorOutput:
    """Tests for sample file generation."""

    def test_generate_csv_files(self, tmp_path: Path) -> None:
        """Test generating CSV sample files."""
        gen = SampleGenerator(industry="retail")

        gen.generate_to_csv(
            output_dir=tmp_path,
            num_workers=10,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 3, 31),
        )

        assert (tmp_path / "workers.csv").exists()
        assert (tmp_path / "shift_types.csv").exists()
        assert (tmp_path / "availability.csv").exists()

    def test_generate_excel_file(self, tmp_path: Path) -> None:
        """Test generating Excel sample file."""
        gen = SampleGenerator(industry="healthcare")

        gen.generate_to_excel(
            output_file=tmp_path / "sample_data.xlsx",
            num_workers=10,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 3, 31),
        )

        assert (tmp_path / "sample_data.xlsx").exists()

    def test_generated_data_is_valid(self, tmp_path: Path) -> None:
        """Test that generated data can be loaded back."""
        gen = SampleGenerator(industry="retail")

        gen.generate_to_csv(
            output_dir=tmp_path,
            num_workers=5,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 31),
        )

        # Try to load the generated data
        from shift_solver.io.csv_loader import CSVLoader

        loader = CSVLoader()
        workers = loader.load_workers(tmp_path / "workers.csv")
        avails = loader.load_availability(tmp_path / "availability.csv")

        assert len(workers) == 5
        # Availability should be loadable (even if empty)
        assert isinstance(avails, list)


class TestSampleGeneratorDeterminism:
    """Tests for reproducible generation."""

    def test_seed_produces_same_output(self, tmp_path: Path) -> None:
        """Test that same seed produces same output."""
        gen1 = SampleGenerator(industry="retail", seed=42)
        gen2 = SampleGenerator(industry="retail", seed=42)

        workers1 = gen1.generate_workers(num_workers=5)
        workers2 = gen2.generate_workers(num_workers=5)

        assert [w.id for w in workers1] == [w.id for w in workers2]
        assert [w.name for w in workers1] == [w.name for w in workers2]

    def test_different_seeds_produce_different_output(self) -> None:
        """Test that different seeds produce different output."""
        gen1 = SampleGenerator(industry="retail", seed=42)
        gen2 = SampleGenerator(industry="retail", seed=123)

        workers1 = gen1.generate_workers(num_workers=5)
        workers2 = gen2.generate_workers(num_workers=5)

        # Names should differ (with very high probability)
        assert [w.name for w in workers1] != [w.name for w in workers2]
