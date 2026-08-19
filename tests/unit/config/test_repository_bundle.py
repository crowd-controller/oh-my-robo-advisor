"""Executable contract for the checked-in credential-free configuration bundle."""

from datetime import UTC, datetime
from pathlib import Path

from omra.config import load_and_validate_config
from omra.core import SimClock

_ROOT = Path(__file__).resolve().parents[3]


def test_repository_config_is_a_valid_secret_free_dry_run_bundle() -> None:
    bundle = load_and_validate_config(
        _ROOT / "config",
        clock=SimClock(datetime(2026, 8, 19, tzinfo=UTC)),
    )

    assert bundle.app.run.env.value == "dry_run"
    assert bundle.app.accounts == ()
    assert bundle.registry.entries == ()
    assert tuple(source.path.name for source in bundle.sources) == (
        "config.yaml",
        "universe.yaml",
        "goals.yaml",
        "market_weights.yaml",
        "external_schedules.yaml",
        "external_income.yaml",
        "surveillance.yaml",
        "tax.yaml",
        "secrets_registry.yaml",
        "tr_ids.kis.yaml",
    )
    assert all(value.startswith("sha256:") for value in bundle.fingerprint.files.values())
    assert bundle.fingerprint.effective.startswith("sha256:")
