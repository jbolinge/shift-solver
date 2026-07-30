"""Regression tests ensuring every shipped config file validates against the schema."""

from datetime import time
from pathlib import Path

import pytest
from click.testing import CliRunner
from pydantic import ValidationError

from shift_solver.cli.main import cli
from shift_solver.config.schema import ShiftSolverConfig
from shift_solver.solver.constraint_registry import (
    ConstraintRegistry,
    register_builtin_constraints,
)

REPO_ROOT = Path(__file__).parents[2]

SHIPPED_CONFIGS = sorted(
    [
        REPO_ROOT / "config" / "config.yaml",
        *(REPO_ROOT / "config" / "examples").glob("*.yaml"),
        # config/examples/*.yaml only matches files directly under
        # config/examples/ -- config/examples/physician_multisite/config.yaml
        # lives in a subdirectory and needs its own glob to be found.
        *(REPO_ROOT / "config" / "examples").glob("*/config.yaml"),
        *REPO_ROOT.glob("examples/*/config.yaml"),
    ]
)

# examples/<name>/ directories each ship their own workers.csv (and, for some,
# availability.csv/requests.csv) alongside config.yaml -- these are exactly
# the runnable examples documented via run.sh. A config can pass
# test_shipped_config_validates (schema loads) while still being infeasible
# once combined with its own roster/CSV data, which is what run.sh actually
# exercises end-to-end. See config-cli-docs review: healthcare/retail shipped
# with worker_shift_limit.max_shifts_per_period=1, which was structurally
# infeasible against their rosters and shift coverage requirements.
RUNNABLE_EXAMPLE_DIRS = sorted(
    p
    for p in (REPO_ROOT / "examples").iterdir()
    if p.is_dir() and (p / "config.yaml").exists() and (p / "workers.csv").exists()
)

BASE_SHIFT_TYPE = {
    "id": "day",
    "name": "Day",
    "category": "day",
    "start_time": time(7, 0),
    "end_time": time(15, 0),
    "duration_hours": 8.0,
}


def test_shipped_configs_found() -> None:
    """Guard against the glob silently matching nothing (or missing subdirs)."""
    assert len(SHIPPED_CONFIGS) >= 8


@pytest.mark.parametrize(
    "config_path", SHIPPED_CONFIGS, ids=lambda p: str(p.relative_to(REPO_ROOT))
)
def test_shipped_config_validates(config_path: Path) -> None:
    config = ShiftSolverConfig.load_from_yaml(config_path)
    assert config.shift_types


@pytest.mark.parametrize("example_dir", RUNNABLE_EXAMPLE_DIRS, ids=lambda p: p.name)
def test_shipped_example_solves(example_dir: Path, tmp_path: Path) -> None:
    """A runnable example's config.yaml + CSVs must actually produce a
    feasible schedule -- mirrors what examples/<name>/run.sh does end to end,
    over the same 4-week window run.sh uses."""
    args = [
        "-c",
        str(example_dir / "config.yaml"),
        "generate",
        "--start-date",
        "2026-02-01",
        "--end-date",
        "2026-02-28",
        "--output",
        str(tmp_path / "schedule.json"),
        "--workers",
        str(example_dir / "workers.csv"),
        "--quick-solve",
    ]
    availability_path = example_dir / "availability.csv"
    if availability_path.exists():
        args += ["--availability", str(availability_path)]
    requests_path = example_dir / "requests.csv"
    if requests_path.exists():
        args += ["--requests", str(requests_path)]

    result = CliRunner().invoke(cli, args)
    assert result.exit_code == 0, result.output


def test_unknown_constraint_id_rejected() -> None:
    with pytest.raises(ValidationError, match="Unknown constraint IDs"):
        ShiftSolverConfig.model_validate(
            {
                "shift_types": [BASE_SHIFT_TYPE],
                "constraints": {"worker_restriction": {"enabled": True}},
            }
        )


def test_all_registered_constraint_ids_accepted() -> None:
    register_builtin_constraints()
    config = ShiftSolverConfig.model_validate(
        {
            "shift_types": [BASE_SHIFT_TYPE],
            "constraints": {
                cid: {"enabled": True}
                for cid in ConstraintRegistry.get_all_constraints()
            },
        }
    )
    assert set(config.constraints) == set(ConstraintRegistry.get_all_constraints())
