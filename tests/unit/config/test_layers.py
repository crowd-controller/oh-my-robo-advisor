"""Unit contracts for layered configuration bootstrap behavior."""

from pathlib import Path

import pytest

from omra.config import (
    ConfigConflictError,
    ConfigSyntaxError,
    ConfigTypeConflict,
    ConfigValidationError,
    ExecEnv,
    UnknownOverrideError,
    apply_overrides,
    deep_merge,
    load_layered_mapping,
    load_yaml_mapping,
    parse_env_overrides,
    parse_override_value,
    resolve_exec_env,
)


def _write(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def test_load_yaml_mapping_rejects_syntax_with_source_location(tmp_path: Path) -> None:
    source = tmp_path / "config.yaml"
    _write(source, "run:\n  env: [\n")

    with pytest.raises(ConfigSyntaxError) as raised:
        load_yaml_mapping(source)

    assert raised.value.source == source
    assert raised.value.line is not None
    assert str(source) in str(raised.value)


def test_load_yaml_mapping_rejects_non_mapping_root(tmp_path: Path) -> None:
    source = tmp_path / "config.yaml"
    _write(source, "- run\n- paper\n")

    with pytest.raises(ConfigValidationError) as raised:
        load_yaml_mapping(source)

    assert raised.value.violations[0].code == "invalid_root"
    assert raised.value.violations[0].source == source
    assert raised.value.violations[0].line == 1
    assert raised.value.violations[0].column == 1


def test_load_yaml_mapping_rejects_duplicate_keys(tmp_path: Path) -> None:
    source = tmp_path / "config.yaml"
    _write(source, "run:\n  env: paper\n  env: live\n")

    with pytest.raises(ConfigSyntaxError, match="duplicate key 'env'"):
        load_yaml_mapping(source)


def test_deep_merge_recurses_and_replaces_lists_without_mutating_inputs() -> None:
    base: dict[str, object] = {
        "run": {"env": "paper", "flags": ["base"]},
        "stable": {"value": 7},
    }
    overlay: dict[str, object] = {"run": {"flags": ["overlay"], "manual_approve": True}}

    result = deep_merge(base, overlay)

    assert result == {
        "run": {"env": "paper", "flags": ["overlay"], "manual_approve": True},
        "stable": {"value": 7},
    }
    assert base["run"] == {"env": "paper", "flags": ["base"]}
    assert overlay["run"] == {"flags": ["overlay"], "manual_approve": True}


def test_deep_merge_rejects_existing_mapping_replacement_with_scalar() -> None:
    base: dict[str, object] = {"run": {"env": "paper"}}
    overlay: dict[str, object] = {"run": "paper"}

    with pytest.raises(ConfigTypeConflict) as raised:
        deep_merge(base, overlay)

    assert raised.value.path == "run"


def test_deep_merge_allows_explicit_list_or_scalar_replacement_with_mapping() -> None:
    overlay = {"run": {"env": "paper"}}

    assert deep_merge({"run": ["legacy"]}, overlay) == overlay
    assert deep_merge({"run": "legacy"}, overlay) == overlay


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("true", True),
        ("3", 3),
        ('["a"]', ["a"]),
        ("null", None),
        ('"문자열"', "문자열"),
        ("paper", "paper"),
    ],
)
def test_parse_override_value_uses_json_then_string(raw: str, expected: object) -> None:
    assert parse_override_value(raw) == expected


def test_parse_env_overrides_normalizes_nested_path_and_ignores_secrets() -> None:
    result = parse_env_overrides(
        {
            "OMRA__QUOTE__MAX_AGE_MS__KRX": "1500",
            "KIS_APP_SECRET": "must-not-be-read-here",
        }
    )

    assert len(result) == 1
    assert result[0].path == ("quote", "max_age_ms", "krx")
    assert result[0].value == 1500


def test_parse_env_overrides_rejects_duplicate_normalized_path() -> None:
    with pytest.raises(ConfigConflictError, match=r"both target run\.env"):
        parse_env_overrides({"OMRA__RUN__ENV": "paper", "OMRA__run__env": "live"})


def test_apply_overrides_rejects_unknown_path_and_reports_variable() -> None:
    overrides = parse_env_overrides({"OMRA__SAFEMODE__NET_BUY_DAILY_CAP_PCT": "2"})

    with pytest.raises(UnknownOverrideError) as raised:
        apply_overrides(
            {"safe_mode": {"net_buy_daily_cap_pct": 3}},
            overrides,
        )

    assert raised.value.path == ("safemode", "net_buy_daily_cap_pct")
    assert raised.value.variable == "OMRA__SAFEMODE__NET_BUY_DAILY_CAP_PCT"


def test_apply_overrides_materializes_declared_default_path() -> None:
    overrides = parse_env_overrides({"OMRA__RUN__MANUAL_APPROVE": "true"})

    result = apply_overrides(
        {},
        overrides,
        known_shape={"run": {"manual_approve": False}},
    )

    assert result == {"run": {"manual_approve": True}}


def test_apply_overrides_does_not_treat_explicit_null_as_missing_mapping() -> None:
    overrides = parse_env_overrides({"OMRA__RUN__MANUAL_APPROVE": "true"})

    with pytest.raises(ConfigTypeConflict) as raised:
        apply_overrides(
            {"run": None},
            overrides,
            known_shape={"run": {"manual_approve": False}},
        )

    assert raised.value.path == "run"


@pytest.mark.parametrize(
    ("base", "environ", "cli", "expected"),
    [
        ({}, {}, None, ExecEnv.DRY_RUN),
        ({"run": {"env": "paper"}}, {}, None, ExecEnv.PAPER),
        ({"run": {"env": "paper"}}, {"OMRA__RUN__ENV": "live"}, None, ExecEnv.LIVE),
        (
            {"run": {"env": "paper"}},
            {"OMRA__RUN__ENV": "live"},
            {"run": {"env": "dry_run"}},
            ExecEnv.DRY_RUN,
        ),
    ],
)
def test_resolve_exec_env_obeys_bootstrap_precedence(
    base: dict[str, object],
    environ: dict[str, str],
    cli: dict[str, object] | None,
    expected: ExecEnv,
) -> None:
    assert resolve_exec_env(base, environ=environ, cli_overrides=cli) is expected


def test_resolve_exec_env_rejects_invalid_value() -> None:
    with pytest.raises(ConfigValidationError, match="invalid_exec_env"):
        resolve_exec_env({"run": {"env": "production"}}, environ={})


def test_load_layered_mapping_obeys_overlay_env_cli_precedence(tmp_path: Path) -> None:
    _write(
        tmp_path / "config.yaml",
        "run:\n  env: paper\nruntime:\n  fill_queue_warn: 100\n",
    )
    _write(
        tmp_path / "config.paper.yaml",
        "run:\n  env: paper\nruntime:\n  fill_queue_warn: 200\n",
    )
    known = {"run": {"env": "dry_run"}, "runtime": {"fill_queue_warn": 1000}}

    overlay_only = load_layered_mapping(tmp_path, environ={}, known_shape=known)
    env_wins = load_layered_mapping(
        tmp_path,
        environ={"OMRA__RUNTIME__FILL_QUEUE_WARN": "300"},
        known_shape=known,
    )
    cli_wins = load_layered_mapping(
        tmp_path,
        environ={"OMRA__RUNTIME__FILL_QUEUE_WARN": "300"},
        cli_overrides={"runtime": {"fill_queue_warn": 400}},
        known_shape=known,
    )

    assert overlay_only.values["runtime"] == {"fill_queue_warn": 200}
    assert env_wins.values["runtime"] == {"fill_queue_warn": 300}
    assert cli_wins.values["runtime"] == {"fill_queue_warn": 400}
    assert [source.kind for source in cli_wins.sources] == ["base", "overlay"]


def test_load_layered_mapping_rejects_overlay_env_conflict(tmp_path: Path) -> None:
    _write(tmp_path / "config.yaml", "run:\n  env: paper\n")
    _write(tmp_path / "config.paper.yaml", "run:\n  env: live\n")

    with pytest.raises(ConfigConflictError, match="expected 'paper'"):
        load_layered_mapping(tmp_path, environ={})


def test_load_layered_mapping_rejects_dry_run_overlay_file(tmp_path: Path) -> None:
    _write(tmp_path / "config.yaml", "run:\n  env: dry_run\n")
    _write(tmp_path / "config.dry_run.yaml", "run:\n  env: dry_run\n")

    with pytest.raises(ConfigConflictError, match="is forbidden"):
        load_layered_mapping(tmp_path, environ={})


def test_load_layered_mapping_requires_selected_overlay(tmp_path: Path) -> None:
    _write(tmp_path / "config.yaml", "run:\n  env: live\n")

    with pytest.raises(ConfigValidationError) as raised:
        load_layered_mapping(tmp_path, environ={})

    assert raised.value.violations[0].code == "file_unreadable"
    assert raised.value.violations[0].source == tmp_path / "config.live.yaml"


def test_two_pass_environment_selects_overlay_before_final_precedence(tmp_path: Path) -> None:
    _write(
        tmp_path / "config.yaml",
        "run:\n  env: dry_run\nruntime:\n  fill_queue_warn: 100\n",
    )
    _write(
        tmp_path / "config.paper.yaml",
        "run:\n  env: paper\nruntime:\n  fill_queue_warn: 200\n",
    )
    _write(
        tmp_path / "config.live.yaml",
        "run:\n  env: live\nruntime:\n  fill_queue_warn: 300\n",
    )

    from_env = load_layered_mapping(
        tmp_path,
        environ={"OMRA__RUN__ENV": "paper"},
        known_shape={"runtime": {"fill_queue_warn": 1000}},
    )
    from_cli = load_layered_mapping(
        tmp_path,
        environ={"OMRA__RUN__ENV": "paper"},
        cli_overrides={"run": {"env": "live"}},
        known_shape={"runtime": {"fill_queue_warn": 1000}},
    )

    assert from_env.env is ExecEnv.PAPER
    assert from_env.values["runtime"] == {"fill_queue_warn": 200}
    assert from_env.sources[-1].path.name == "config.paper.yaml"
    assert from_cli.env is ExecEnv.LIVE
    assert from_cli.values["runtime"] == {"fill_queue_warn": 300}
    assert from_cli.values["run"] == {"env": "live"}
