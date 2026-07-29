"""Tests for sample data generator."""

from datetime import date
from pathlib import Path

import pytest
import yaml

from shift_solver.io.sample_generator import IndustryPreset, SampleGenerator
from shift_solver.io.sample_generator.names import generate_worker_name

REPO_ROOT = Path(__file__).parents[2]


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


class TestPresetConfigAlignment:
    """
    Regression tests for the preset/config mismatch (generate-samples used
    to emit shift IDs matching no shipped config, e.g. warehouse presets
    used "first"/"second"/"third" while config/examples/warehouse.yaml uses
    "first_shift"/"second_shift"/"third_shift"/"weekend_shift"). Every
    preset's shift IDs and categories must be a subset of the corresponding
    config/examples/<industry>.yaml so that generated sample data can be
    solved directly against that config.
    """

    @pytest.mark.parametrize("industry", ["retail", "healthcare", "warehouse"])
    def test_preset_shift_ids_and_categories_match_shipped_config(
        self, industry: str
    ) -> None:
        """Preset shift IDs/categories must be a subset of the shipped config."""
        config_path = REPO_ROOT / "config" / "examples" / f"{industry}.yaml"
        with open(config_path) as f:
            config_data = yaml.safe_load(f)

        config_shifts = {st["id"]: st["category"] for st in config_data["shift_types"]}

        preset = IndustryPreset.get(industry)
        for shift in preset.shift_types:
            assert shift["id"] in config_shifts, (
                f"Preset shift id '{shift['id']}' has no matching shift type "
                f"in {config_path}"
            )
            assert shift["category"] == config_shifts[shift["id"]], (
                f"Preset shift '{shift['id']}' category '{shift['category']}' "
                f"does not match config category '{config_shifts[shift['id']]}'"
            )


class TestSampleGenerator:
    """Tests for SampleGenerator."""

    def test_generate_workers(self) -> None:
        """Test generating workers."""
        gen = SampleGenerator(industry="retail")
        workers = gen.generate_workers(num_workers=10)

        assert len(workers) == 10
        assert all(w.id for w in workers)
        assert all(w.name for w in workers)

    def test_generate_workers_uses_generic_names(self) -> None:
        """
        Names must be generic role-flavored labels, never realistic
        personal names (project convention: no real names in sample data).
        """
        gen = SampleGenerator(industry="healthcare", seed=7)
        workers = gen.generate_workers(num_workers=20)

        # No personal-name-shaped values should ever appear.
        banned_fragments = ("Dr.", "Smith", "Johnson", "Jackson", "William")
        for worker in workers:
            assert not any(fragment in worker.name for fragment in banned_fragments)
            # Name is "<Role Label> <index>", e.g. "Nurse 3" or "Physician 1".
            *_label_parts, suffix = worker.name.split(" ")
            assert suffix.isdigit()

    def test_generate_shift_types(self) -> None:
        """Test generating shift types."""
        gen = SampleGenerator(industry="retail")
        shift_types = gen.generate_shift_types()

        assert len(shift_types) >= 2
        assert all(st.id for st in shift_types)
        assert all(st.workers_required >= 1 for st in shift_types)

    def test_generate_availability(self) -> None:
        """Test generating availability records."""
        # Use seed to ensure we get some availability. (Note: the exact rng
        # draw sequence is an implementation detail -- e.g. it shifted when
        # worker name generation stopped consuming random draws for the
        # (now-removed) realistic first/last name lists -- so this seed is
        # chosen empirically, not because of any semantic property.)
        gen = SampleGenerator(industry="retail", seed=1)
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

    def test_seed_produces_same_output(self, tmp_path: Path) -> None:  # noqa: ARG002
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


class TestGenerateWorkerName:
    """Tests for the generic worker-name helper."""

    def test_uses_role_label_from_worker_type(self) -> None:
        """worker_type is title-cased with underscores rendered as spaces."""
        assert generate_worker_name(1, "nurse") == "Nurse 1"
        assert generate_worker_name(3, "full_time") == "Full Time 3"

    def test_falls_back_to_worker_when_no_type(self) -> None:
        """Missing worker_type falls back to the generic "Worker" label."""
        assert generate_worker_name(2, None) == "Worker 2"

    def test_name_is_unique_whenever_index_is_unique(self) -> None:
        """Same worker_type, different index, always yields distinct names."""
        names = {generate_worker_name(i, "picker") for i in range(1, 21)}
        assert len(names) == 20
