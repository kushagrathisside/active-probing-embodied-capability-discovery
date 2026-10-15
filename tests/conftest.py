import pytest

from src.damage import load_damage
from src.outcomes import build_table
from src.platform_adapter import load_platform
from src.tiers import load_tiers


@pytest.fixture(scope="session")
def arm():
    """The real arm6 platform, configs and simulated outcome table. Built once per test run."""
    platform = load_platform()
    tiers = load_tiers()
    damage = load_damage()
    table = build_table(platform, tiers, damage)
    return platform, tiers, damage, table
