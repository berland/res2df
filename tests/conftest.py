from pathlib import Path

import pytest

import ecl2df


@pytest.fixture
def path_to_ecl2df() -> Path:
    """Path to installed ecl2df module.

    This is used for testing hook implementations, where the install
    location can vary"""
    return Path(ecl2df.__file__).parent
