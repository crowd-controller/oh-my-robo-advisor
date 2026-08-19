"""Unit contracts for deterministic multi-source ConfigBundle loading."""

import os
from dataclasses import FrozenInstanceError
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
import yaml

from omra.config import (
    AppConfig,
    ConfigBundle,
    ConfigValidationError,
    load_and_validate_config,
)
from omra.core import SimClock


@pytest.fixture(autouse=True)
def _clear_omra_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in tuple(os.environ):
        if name.startswith("OMRA__"):
            monkeypatch.delenv(name)


def _clock() -> SimClock:
    return SimClock(datetime(2026, 8, 19, tzinfo=UTC))


def _write_yaml(path: Path, values: object) -> None:
    path.write_text(
        yaml.safe_dump(values, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def _app_values(*, env: str = "dry_run") -> dict[str, object]:
    values: dict[str, object] = {name: {} for name in AppConfig.model_fields}
    values["run"] = {"env": env}
    values["accounts"] = []
    values["backtest"] = {"snapshot": {}}
    return values


def _tax_values(*, effective_from: str = "2026-01-01") -> dict[str, object]:
    return {
        "schema_version": 1,
        "versions": [
            {
                "effective_from": effective_from,
                "note": "loader fixture",
                "params": {
                    "overseas_cg_rate": "0.22",
                    "overseas_cg_deduction_krw": "2500000",
                    "dividend_wht_rate": "0.154",
                    "fin_income_aggregate_threshold_krw": "20000000",
                    "isa_free_limit_krw": "2000000",
                    "isa_excess_rate": "0.099",
                    "isa_annual_contrib_cap_krw": "20000000",
                    "pension_deduct_cap_savings_krw": "6000000",
                    "pension_deduct_cap_total_krw": "9000000",
                    "pension_contrib_cap_total_krw": "18000000",
                    "harvest_cost_gate_factor": "0.5",
                    "harvest_annual_nav_cap": "0.20",
                    "crypto_tax_enabled": False,
                },
            }
        ],
    }


def _trids_values(*, unresolved: bool = False) -> dict[str, object]:
    live_url = "<확인 필요: live REST URL>" if unresolved else "https://live.example.test"
    return {
        "rest": {
            "live_prefix": "T",
            "paper_prefix": "V",
            "base_url": {
                "live": live_url,
                "paper": "https://paper.example.test",
            },
            "trs": [],
        },
        "ws": {
            "live": {
                "url": "wss://live.example.test",
                "port": 21000,
                "tr": {
                    "exec_notice_domestic": "H0STCNI0",
                    "exec_notice_overseas": "H0GSCNI0",
                },
            },
            "paper": {
                "url": "wss://paper.example.test",
                "port": 21001,
                "tr": {
                    "exec_notice_domestic": "H0STCNI0",
                    "exec_notice_overseas": "H0GSCNI0",
                },
            },
        },
    }


def _surveillance_values() -> dict[str, object]:
    return {
        "version": 1,
        "map": [
            {"risk_type": "KR-01", "level": "SV3"},
            {"risk_type": "KR-02", "level": "SV2"},
            {"risk_type": "KR-03", "level": "SV2"},
            {"risk_type": "KR-04", "level": "SV2"},
            {"risk_type": "KR-12", "level": "SV3"},
            {"risk_type": "US-01", "level": "SV3"},
            {"risk_type": "US-02", "level": "SV2"},
        ],
    }


def _record_values(*, unresolved_trids: bool = False) -> dict[str, object]:
    return {
        "universe.yaml": {
            "version": 1,
            "approved_at": "2026-08-01",
            "instruments": [],
            "approved_substitutes": [],
        },
        "goals.yaml": {
            "goals": [],
            "glide_path": {},
        },
        "market_weights.yaml": {
            "version": 1,
            "as_of": "2026-08-01",
            "top_level": {
                "equity": "0.45",
                "bond": "0.45",
                "alternative": "0.10",
            },
            "equity_regions": {
                "source": "msci_acwi_imi",
                "weights": {"kr": None, "us": None, "dev_ex_us": None},
            },
        },
        "external_schedules.yaml": [],
        "external_income.yaml": [],
        "surveillance.yaml": _surveillance_values(),
        "tax.yaml": _tax_values(),
        "secrets_registry.yaml": [],
        "tr_ids.kis.yaml": _trids_values(unresolved=unresolved_trids),
    }


def _config_dir(
    tmp_path: Path,
    *,
    env: str = "dry_run",
    unresolved_trids: bool = False,
    targets: bool = False,
    questions: bool = False,
) -> Path:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    _write_yaml(config_dir / "config.yaml", _app_values(env=env))
    if env != "dry_run":
        _write_yaml(config_dir / f"config.{env}.yaml", {"run": {"env": env}})
    for name, values in _record_values(unresolved_trids=unresolved_trids).items():
        _write_yaml(config_dir / name, values)
    if targets:
        _write_yaml(
            config_dir / "targets.yaml",
            {
                "version": 1,
                "as_of": "2026-08-01",
                "risk_level": 6,
                "weights": {},
                "cash": "1",
            },
        )
    if questions:
        _write_yaml(
            config_dir / "research_open_questions.yaml",
            {"version": 1, "questions": []},
        )
    return config_dir


def test_loader_assembles_every_required_source_and_effective_tax(tmp_path: Path) -> None:
    config_dir = _config_dir(tmp_path)

    bundle = load_and_validate_config(config_dir, clock=_clock())

    assert isinstance(bundle, ConfigBundle)
    assert bundle.app.run.env.value == "dry_run"
    assert bundle.universe.version == 1
    assert bundle.targets is None
    assert bundle.questions.version == 1
    assert bundle.questions.questions == ()
    assert bundle.tax.at(date(2026, 8, 19)).effective_from == date(2026, 1, 1)

    expected_names = (
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
    assert tuple(source.path.name for source in bundle.sources) == expected_names
    assert tuple(source.kind for source in bundle.sources) == (
        "base",
        *(["record"] * 9),
    )
    for source in bundle.sources:
        assert source.sha256 == bundle.fingerprint.files[f"config/{source.path.name}"]


def test_optional_records_are_loaded_only_when_present(tmp_path: Path) -> None:
    config_dir = _config_dir(tmp_path, targets=True, questions=True)

    bundle = load_and_validate_config(config_dir, clock=_clock())

    assert bundle.targets is not None
    assert bundle.targets.cash == 1
    assert bundle.questions.questions == ()
    source_names = {source.path.name for source in bundle.sources}
    assert "targets.yaml" in source_names
    assert "research_open_questions.yaml" in source_names


def test_selected_environment_overlay_is_tracked_as_an_exact_source(tmp_path: Path) -> None:
    config_dir = _config_dir(tmp_path, env="paper")

    bundle = load_and_validate_config(config_dir, clock=_clock())

    assert tuple(source.path.name for source in bundle.sources[:2]) == (
        "config.yaml",
        "config.paper.yaml",
    )
    assert tuple(source.kind for source in bundle.sources[:2]) == ("base", "overlay")


def test_loader_applies_default_path_env_override_then_cli_precedence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_dir = _config_dir(tmp_path)
    monkeypatch.setenv("OMRA__RUNTIME__FILL_QUEUE_WARN", "321")

    bundle = load_and_validate_config(
        config_dir,
        cli_overrides={"runtime": {"fill_queue_warn": 456}},
        clock=_clock(),
    )

    assert bundle.app.runtime.fill_queue_warn == 456


def test_loader_aggregates_scalar_and_independent_record_failures(tmp_path: Path) -> None:
    config_dir = _config_dir(tmp_path)
    app_values = _app_values()
    app_values["unexpected_root"] = True
    _write_yaml(config_dir / "config.yaml", app_values)
    universe = _record_values()["universe.yaml"]
    assert isinstance(universe, dict)
    universe["version"] = 0
    _write_yaml(config_dir / "universe.yaml", universe)
    (config_dir / "goals.yaml").unlink()

    with pytest.raises(ConfigValidationError) as raised:
        load_and_validate_config(config_dir, clock=_clock())

    violations = raised.value.violations
    assert len(violations) == 3
    assert any(
        violation.source is None
        and violation.path == "unexpected_root"
        and violation.code == "extra_forbidden"
        for violation in violations
    )
    assert any(
        violation.source == config_dir / "universe.yaml" and violation.path == "version"
        for violation in violations
    )
    assert any(
        violation.source == config_dir / "goals.yaml" and violation.code == "file_missing"
        for violation in violations
    )


def test_loader_aggregates_yaml_syntax_errors_across_sources(tmp_path: Path) -> None:
    config_dir = _config_dir(tmp_path)
    (config_dir / "config.yaml").write_text("run:\n  env: [\n", encoding="utf-8")
    (config_dir / "goals.yaml").write_text("goals: [\n", encoding="utf-8")

    with pytest.raises(ConfigValidationError) as raised:
        load_and_validate_config(config_dir, clock=_clock())

    syntax_sources = tuple(
        violation.source for violation in raised.value.violations if violation.code == "yaml_syntax"
    )
    assert syntax_sources == (
        config_dir / "config.yaml",
        config_dir / "goals.yaml",
    )


def test_loader_rejects_when_no_tax_version_is_effective_on_clock_date(
    tmp_path: Path,
) -> None:
    config_dir = _config_dir(tmp_path)
    _write_yaml(config_dir / "tax.yaml", _tax_values(effective_from="2027-01-01"))

    with pytest.raises(ConfigValidationError) as raised:
        load_and_validate_config(config_dir, clock=_clock())

    assert len(raised.value.violations) == 1
    violation = raised.value.violations[0]
    assert violation.code == "effective_version_missing"
    assert violation.path == "versions"
    assert violation.source == config_dir / "tax.yaml"


def test_loader_rejects_every_unresolved_live_tr_id_path(tmp_path: Path) -> None:
    config_dir = _config_dir(tmp_path, env="live", unresolved_trids=True)

    with pytest.raises(ConfigValidationError) as raised:
        load_and_validate_config(config_dir, clock=_clock())

    assert len(raised.value.violations) == 1
    violation = raised.value.violations[0]
    assert violation.code == "unsupported_in_env"
    assert violation.path == "rest.base_url.live"
    assert violation.source == config_dir / "tr_ids.kis.yaml"


def test_unresolved_non_live_tr_ids_warn_but_keep_the_bundle(tmp_path: Path) -> None:
    config_dir = _config_dir(tmp_path, unresolved_trids=True)

    with pytest.warns(RuntimeWarning, match="rest.base_url.live"):
        bundle = load_and_validate_config(config_dir, clock=_clock())

    assert bundle.trids.unresolved() == ("rest.base_url.live",)


def test_bundle_and_loaded_sources_are_frozen(tmp_path: Path) -> None:
    bundle = load_and_validate_config(_config_dir(tmp_path), clock=_clock())

    bundle_attribute = "targets"
    with pytest.raises(FrozenInstanceError):
        setattr(bundle, bundle_attribute, None)
    source_attribute = "kind"
    with pytest.raises(FrozenInstanceError):
        setattr(bundle.sources[0], source_attribute, "changed")
