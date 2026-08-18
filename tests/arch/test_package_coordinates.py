"""The M0 scaffold must expose every package coordinate named by design 01."""

from importlib.util import find_spec
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]

_FIRST_LEVEL_PACKAGES = frozenset(
    {
        "audit",
        "backtest",
        "brokers",
        "calendar",
        "cli",
        "collectors",
        "config",
        "core",
        "data",
        "engine",
        "execution",
        "labs",
        "monitoring",
        "persistence",
        "portfolio",
        "protections",
        "realtime",
        "research",
        "rpc",
        "runtime",
        "scheduler",
        "surveillance",
        "tax",
        "web",
    }
)

_REQUIRED_COORDINATES = (
    "omra.brokers.kis.client",
    "omra.brokers.kis.ws.events",
    "omra.brokers.upbit.client",
    "omra.brokers.upbit.ws.events",
    "omra.data.fetchers",
    "omra.data.providers",
    "omra.data.quote",
    "omra.data.store",
    "omra.engine.covariance_monitor",
    "omra.engine.expected_returns",
    "omra.engine.optimizer",
    "omra.engine.rebalancer",
    "omra.engine.overlay",
    "omra.persistence.ro",
    "omra.persistence.migrations",
    "omra.persistence.models",
    "omra.persistence.session",
    "omra.surveillance.catalog",
    "omra.surveillance.flags",
    "omra.surveillance.gate",
    "omra.surveillance.models",
    "omra.surveillance.sources",
)


def test_first_level_package_set_matches_design() -> None:
    package_root = _ROOT / "src" / "omra"
    actual = {
        path.name
        for path in package_root.iterdir()
        if path.is_dir() and (path / "__init__.py").is_file()
    }

    assert actual == _FIRST_LEVEL_PACKAGES


@pytest.mark.parametrize("module", _REQUIRED_COORDINATES)
def test_required_coordinate_is_importable(module: str) -> None:
    assert find_spec(module) is not None
