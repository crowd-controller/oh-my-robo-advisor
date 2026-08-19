"""Unit contracts for raw and effective configuration fingerprints."""

import hashlib
import os
import re
from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import TYPE_CHECKING, cast

import pytest
import yaml

from omra.config import AppConfig, ConfigFingerprint, config_fingerprint

if TYPE_CHECKING:
    from collections.abc import MutableMapping


def _payload(*, min_weight: str = "0.5") -> dict[str, object]:
    values: dict[str, object] = {name: {} for name in AppConfig.model_fields}
    values["accounts"] = []
    values["backtest"] = {"snapshot": {}}
    values["core"] = {"min_weight": min_weight}
    return values


def _write_config(config_dir: Path, values: dict[str, object]) -> None:
    config_dir.mkdir(parents=True)
    (config_dir / "config.yaml").write_text(
        yaml.safe_dump(values, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def _clear_omra_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in tuple(os.environ):
        if name.startswith("OMRA__"):
            monkeypatch.delenv(name)


def _assert_sha256(value: str) -> None:
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", value)


def test_file_hashes_cover_top_level_yaml_bytes_with_stable_keys(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    values = _payload()
    _write_config(config_dir, values)
    record = config_dir / "record.yaml"
    record.write_bytes(b"version: 1\n")
    (config_dir / "litestream.yml").write_text("dbs: []\n", encoding="utf-8")
    nested = config_dir / "nested"
    nested.mkdir()
    (nested / "ignored.yaml").write_text("version: 1\n", encoding="utf-8")

    fingerprint = config_fingerprint(
        config_dir,
        app=AppConfig.model_validate(values),
    )

    expected = hashlib.sha256(b"version: 1\n").hexdigest()
    assert tuple(fingerprint.files) == ("config/config.yaml", "config/record.yaml")
    assert fingerprint.files["config/record.yaml"] == f"sha256:{expected}"
    _assert_sha256(fingerprint.files["config/config.yaml"])
    _assert_sha256(fingerprint.effective)


def test_fingerprint_copies_sorts_and_freezes_the_file_mapping() -> None:
    source = {"config/z.yaml": "sha256:z", "config/a.yaml": "sha256:a"}
    fingerprint = ConfigFingerprint(files=source, effective="sha256:effective")
    source["config/later.yaml"] = "sha256:later"

    assert tuple(fingerprint.files) == ("config/a.yaml", "config/z.yaml")
    assert "config/later.yaml" not in fingerprint.files
    mutable = cast("MutableMapping[str, str]", fingerprint.files)
    with pytest.raises(TypeError):
        mutable["config/new.yaml"] = "sha256:new"

    field = "effective"
    with pytest.raises(FrozenInstanceError):
        setattr(fingerprint, field, "sha256:changed")


def test_semantically_equal_decimal_spellings_share_effective_hash(tmp_path: Path) -> None:
    short_dir = tmp_path / "short" / "config"
    leading_zero_dir = tmp_path / "leading-zero" / "config"
    _write_config(short_dir, _payload(min_weight=".5"))
    _write_config(leading_zero_dir, _payload(min_weight="0.5"))

    short = config_fingerprint(short_dir)
    leading_zero = config_fingerprint(leading_zero_dir)

    assert short.files["config/config.yaml"] != leading_zero.files["config/config.yaml"]
    assert short.effective == leading_zero.effective


def test_effective_hash_changes_when_the_validated_value_changes(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    _write_config(config_dir, _payload())

    first = config_fingerprint(
        config_dir,
        app=AppConfig.model_validate(_payload(min_weight="0.5")),
    )
    second = config_fingerprint(
        config_dir,
        app=AppConfig.model_validate(_payload(min_weight="0.6")),
    )

    assert first.files == second.files
    assert first.effective != second.effective


def test_nested_mapping_order_does_not_change_effective_hash(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    values = _payload()
    _write_config(config_dir, values)
    first_values = _payload()
    second_values = _payload()
    first_values["crypto"] = {"mix": {"KRW-BTC": "0.7", "KRW-ETH": "0.3"}}
    second_values["crypto"] = {"mix": {"KRW-ETH": "0.3", "KRW-BTC": "0.7"}}

    first = config_fingerprint(config_dir, app=AppConfig.model_validate(first_values))
    second = config_fingerprint(config_dir, app=AppConfig.model_validate(second_values))

    assert first.effective == second.effective


def test_standalone_entrypoint_includes_omra_environment_overrides(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_dir = tmp_path / "config"
    _write_config(config_dir, _payload(min_weight="0.8"))
    _clear_omra_env(monkeypatch)
    baseline = config_fingerprint(config_dir)

    monkeypatch.setenv("OMRA__CORE__MIN_WEIGHT", '"0.7"')
    overridden = config_fingerprint(config_dir)

    assert baseline.files == overridden.files
    assert baseline.effective != overridden.effective


def test_standalone_entrypoint_applies_the_selected_environment_overlay(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_dir = tmp_path / "config"
    values = _payload(min_weight="0.8")
    values["run"] = {"env": "paper"}
    _write_config(config_dir, values)
    (config_dir / "config.paper.yaml").write_text(
        'run:\n  env: paper\ncore:\n  min_weight: "0.7"\n',
        encoding="utf-8",
    )
    _clear_omra_env(monkeypatch)

    standalone = config_fingerprint(config_dir)
    expected_values = _payload(min_weight="0.7")
    expected_values["run"] = {"env": "paper"}
    expected = config_fingerprint(
        config_dir,
        app=AppConfig.model_validate(expected_values),
    )

    assert standalone.effective == expected.effective
