"""Shared fixtures for web UI tests."""

import sys
from pathlib import Path

import pytest

# Add web/ to sys.path so Django can find our project
_web_dir = Path(__file__).resolve().parent.parent.parent / "web"
if str(_web_dir) not in sys.path:
    sys.path.insert(0, str(_web_dir))

# Also add src/ so Django can import shift_solver
_src_dir = Path(__file__).resolve().parent.parent.parent / "src"
if str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))


@pytest.fixture(scope="session")
def django_db_modify_db_setup_for_web() -> None:
    """Marker fixture to indicate web DB setup is available."""
