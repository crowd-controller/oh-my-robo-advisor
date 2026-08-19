"""Unit contracts for the environment-only secret catalog and loader."""

import os
import sys
import warnings
from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import Literal

import pytest
from pydantic import SecretStr, ValidationError

from omra.config import (
    CATALOG,
    ConfigError,
    ExecEnv,
    MissingSecrets,
    Secrets,
    SecretSpec,
    load_secrets,
)
from omra.config.files import SecretTier

_SECURE_ENV_MODE = 0o600
_LIVE = frozenset({ExecEnv.LIVE})
_PAPER = frozenset({ExecEnv.PAPER})
_LIVE_PAPER = frozenset({ExecEnv.LIVE, ExecEnv.PAPER})
SecretSurface = Literal["app", "litestream", "tools"]
CatalogRow = tuple[str, frozenset[ExecEnv], SecretSurface, SecretTier, bool]

_EXPECTED_CATALOG: tuple[CatalogRow, ...] = (
    ("KIS_APP_KEY", _LIVE, "app", SecretTier.TIER1, True),
    ("KIS_APP_SECRET", _LIVE, "app", SecretTier.TIER1, True),
    ("KIS_PAPER_APP_KEY", _PAPER, "app", SecretTier.TIER2, True),
    ("KIS_PAPER_APP_SECRET", _PAPER, "app", SecretTier.TIER2, True),
    ("KIS_ACCOUNT_NO", _LIVE_PAPER, "app", SecretTier.TIER1, False),
    ("KIS_HTS_ID", _LIVE_PAPER, "app", SecretTier.TIER2, True),
    ("UPBIT_ACCESS", _LIVE, "app", SecretTier.TIER1, True),
    ("UPBIT_SECRET", _LIVE, "app", SecretTier.TIER1, True),
    ("TELEGRAM_BOT_TOKEN", _LIVE_PAPER, "app", SecretTier.TIER2, True),
    ("TELEGRAM_CHAT_ID", _LIVE_PAPER, "app", SecretTier.TIER2, False),
    ("SMTP_HOST", _LIVE, "app", SecretTier.TIER2, False),
    ("SMTP_PORT", _LIVE, "app", SecretTier.TIER2, False),
    ("SMTP_USER", _LIVE, "app", SecretTier.TIER2, False),
    ("SMTP_PASS", _LIVE, "app", SecretTier.TIER2, True),
    ("DEADMAN_WEBHOOK_URL", _LIVE, "app", SecretTier.TIER2, False),
    ("WEB_SESSION_SECRET", _LIVE_PAPER, "app", SecretTier.TIER3, True),
    ("WEB_ADMIN_PASSWORD_HASH", _LIVE_PAPER, "app", SecretTier.TIER3, True),
    ("SAFETY_CODE_SECRET", _LIVE_PAPER, "app", SecretTier.TIER3, True),
    ("LITESTREAM_BUCKET", _LIVE, "litestream", SecretTier.TIER2, False),
    ("LITESTREAM_ACCESS_KEY_ID", _LIVE, "litestream", SecretTier.TIER2, True),
    ("LITESTREAM_SECRET_ACCESS_KEY", _LIVE, "litestream", SecretTier.TIER2, True),
    ("RESTIC_REPOSITORY", _LIVE, "app", SecretTier.TIER2, False),
    ("RESTIC_PASSWORD", _LIVE, "app", SecretTier.TIER2, True),
    ("RESTIC_ACCESS_KEY_ID", _LIVE, "app", SecretTier.TIER2, True),
    ("RESTIC_SECRET_ACCESS_KEY", _LIVE, "app", SecretTier.TIER2, True),
    ("ANTHROPIC_API_KEY", frozenset(), "app", SecretTier.TIER3, True),
)


def _clear_secret_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    names = {spec.name for spec in CATALOG}
    for name in tuple(os.environ):
        if name in names or name.startswith("KIS_ACCOUNT__"):
            monkeypatch.delenv(name, raising=False)


def _write_env(path: Path, text: str, *, mode: int = _SECURE_ENV_MODE) -> None:
    path.write_text(text, encoding="utf-8")
    path.chmod(mode)


def _required_values(env: ExecEnv, surface: SecretSurface) -> dict[str, object]:
    return {
        spec.name: f"fake-{spec.name.lower()}"
        for spec in CATALOG
        if spec.surface == surface and env in spec.required_in
    }


def test_catalog_exactly_matches_the_canonical_twenty_six_specs() -> None:
    actual = tuple(
        (spec.name, spec.required_in, spec.surface, spec.tier, spec.registry_tracked)
        for spec in CATALOG
    )

    assert actual == _EXPECTED_CATALOG
    assert len({spec.name for spec in CATALOG}) == 26
    assert all(isinstance(spec, SecretSpec) for spec in CATALOG)


def test_secret_spec_is_frozen() -> None:
    field_name = "name"
    with pytest.raises(FrozenInstanceError):
        setattr(CATALOG[0], field_name, "CHANGED")


def test_every_catalog_value_is_secretstr_and_the_model_is_frozen() -> None:
    values: dict[str, object] = {spec.name: f"fake-{spec.name.lower()}" for spec in CATALOG}
    values["KIS_ACCOUNT"] = {"GENERAL_KIS": "fake-account-ref"}
    secrets = Secrets.model_validate(values)

    for spec in CATALOG:
        assert isinstance(getattr(secrets, spec.name.lower()), SecretStr)
    assert isinstance(secrets.kis_accounts["general_kis"], SecretStr)

    field_name = "kis_app_key"
    with pytest.raises(ValidationError, match="frozen"):
        setattr(secrets, field_name, SecretStr("replacement"))


def test_model_fields_have_exact_canonical_environment_aliases() -> None:
    expected_fields = [spec.name.lower() for spec in CATALOG]
    expected_fields.append("kis_accounts")

    assert tuple(Secrets.model_fields) == tuple(expected_fields)
    for spec in CATALOG:
        assert Secrets.model_fields[spec.name.lower()].validation_alias == spec.name
    assert Secrets.model_fields["kis_accounts"].validation_alias == "KIS_ACCOUNT"


def test_load_secrets_reads_canonical_keys_and_ignores_app_overrides(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_secret_environment(monkeypatch)
    source = tmp_path / ".env"
    _write_env(
        source,
        """KIS_APP_KEY=fake-live-app-key
KIS_ACCOUNT_NO=fake-legacy-account
KIS_ACCOUNT__GENERAL_KIS=fake-general-account
OMRA__RUN__ENV=live
UNRELATED_SETTING=ignored
""",
    )

    secrets = load_secrets((source,))

    assert secrets.kis_app_key is not None
    assert secrets.kis_app_key.get_secret_value() == "fake-live-app-key"
    assert secrets.kis_account_no is not None
    assert secrets.kis_account_no.get_secret_value() == "fake-legacy-account"
    assert tuple(secrets.kis_accounts) == ("general_kis",)
    assert secrets.kis_accounts["general_kis"].get_secret_value() == "fake-general-account"


def test_later_env_file_and_then_process_environment_take_precedence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_secret_environment(monkeypatch)
    base = tmp_path / ".env"
    overlay = tmp_path / ".env.local"
    _write_env(base, "KIS_APP_KEY=fake-base\n")
    _write_env(overlay, "KIS_APP_KEY=fake-overlay\n")

    from_files = load_secrets((base, overlay))
    assert from_files.kis_app_key is not None
    assert from_files.kis_app_key.get_secret_value() == "fake-overlay"

    monkeypatch.setenv("KIS_APP_KEY", "fake-process")
    from_process = load_secrets((base, overlay))
    assert from_process.kis_app_key is not None
    assert from_process.kis_app_key.get_secret_value() == "fake-process"


@pytest.mark.parametrize(
    ("env", "surface", "expected"),
    [
        (
            ExecEnv.LIVE,
            "app",
            (
                "DEADMAN_WEBHOOK_URL",
                "KIS_ACCOUNT_NO",
                "KIS_APP_KEY",
                "KIS_APP_SECRET",
                "KIS_HTS_ID",
                "RESTIC_ACCESS_KEY_ID",
                "RESTIC_PASSWORD",
                "RESTIC_REPOSITORY",
                "RESTIC_SECRET_ACCESS_KEY",
                "SAFETY_CODE_SECRET",
                "SMTP_HOST",
                "SMTP_PASS",
                "SMTP_PORT",
                "SMTP_USER",
                "TELEGRAM_BOT_TOKEN",
                "TELEGRAM_CHAT_ID",
                "UPBIT_ACCESS",
                "UPBIT_SECRET",
                "WEB_ADMIN_PASSWORD_HASH",
                "WEB_SESSION_SECRET",
            ),
        ),
        (
            ExecEnv.PAPER,
            "app",
            (
                "KIS_ACCOUNT_NO",
                "KIS_HTS_ID",
                "KIS_PAPER_APP_KEY",
                "KIS_PAPER_APP_SECRET",
                "SAFETY_CODE_SECRET",
                "TELEGRAM_BOT_TOKEN",
                "TELEGRAM_CHAT_ID",
                "WEB_ADMIN_PASSWORD_HASH",
                "WEB_SESSION_SECRET",
            ),
        ),
        (
            ExecEnv.LIVE,
            "litestream",
            (
                "LITESTREAM_ACCESS_KEY_ID",
                "LITESTREAM_BUCKET",
                "LITESTREAM_SECRET_ACCESS_KEY",
            ),
        ),
    ],
)
def test_require_reports_every_missing_name_deterministically(
    env: ExecEnv,
    surface: SecretSurface,
    expected: tuple[str, ...],
) -> None:
    with pytest.raises(MissingSecrets) as raised:
        Secrets.model_validate({}).require(env, surface)

    assert raised.value.names == expected
    assert raised.value.code == "config.secrets_missing"


@pytest.mark.parametrize("surface", ["app", "litestream", "tools"])
def test_dry_run_requires_no_credentials(surface: SecretSurface) -> None:
    Secrets.model_validate({}).require(ExecEnv.DRY_RUN, surface)


def test_complete_values_pass_and_dynamic_accounts_satisfy_the_legacy_name() -> None:
    values: dict[str, object] = _required_values(ExecEnv.LIVE, "app")
    del values["KIS_ACCOUNT_NO"]
    values["KIS_ACCOUNT"] = {"GENERAL_KIS": "fake-account-ref"}

    Secrets.model_validate(values).require(ExecEnv.LIVE, "app")


def test_empty_values_do_not_satisfy_require() -> None:
    values: dict[str, object] = _required_values(ExecEnv.PAPER, "app")
    values["KIS_PAPER_APP_KEY"] = ""
    values["KIS_ACCOUNT_NO"] = ""
    values["KIS_ACCOUNT"] = {"GENERAL_KIS": ""}

    with pytest.raises(MissingSecrets) as raised:
        Secrets.model_validate(values).require(ExecEnv.PAPER, "app")

    assert raised.value.names == ("KIS_ACCOUNT_NO", "KIS_PAPER_APP_KEY")


def test_assert_absent_reports_names_without_values() -> None:
    raw_value = "fake-value-that-must-not-leak"
    secrets = Secrets.model_validate(
        {
            "KIS_APP_KEY": raw_value,
            "KIS_ACCOUNT": {"GENERAL_KIS": "fake-account-ref"},
        }
    )

    with pytest.raises(ConfigError) as raised:
        secrets.assert_absent(["KIS_ACCOUNT_NO", "KIS_APP_KEY", "SMTP_PASS"])

    message = str(raised.value)
    assert "KIS_ACCOUNT_NO" in message
    assert "KIS_APP_KEY" in message
    assert "SMTP_PASS" not in message
    assert raw_value not in message
    assert raised.value.code == "config.secret_placement"


def test_assert_absent_rejects_unknown_catalog_names() -> None:
    with pytest.raises(ValueError, match="NOT_A_SECRET"):
        Secrets.model_validate({}).assert_absent(["NOT_A_SECRET"])


def test_all_values_collects_non_empty_named_and_mapped_values_once() -> None:
    secrets = Secrets.model_validate(
        {
            "KIS_APP_KEY": "fake-shared",
            "SMTP_PASS": "fake-shared",
            "ANTHROPIC_API_KEY": "",
            "KIS_ACCOUNT": {
                "GENERAL_KIS": "fake-account",
                "EMPTY_ACCOUNT": "",
            },
        }
    )

    assert secrets.all_values() == frozenset({"fake-shared", "fake-account"})


def test_repr_dump_and_json_never_include_raw_values() -> None:
    raw_values = ("fake-app-key", "fake-account-ref")
    secrets = Secrets.model_validate(
        {
            "KIS_APP_KEY": raw_values[0],
            "KIS_ACCOUNT": {"GENERAL_KIS": raw_values[1]},
        }
    )

    rendered = (repr(secrets), str(secrets.model_dump()), secrets.model_dump_json())
    for raw in raw_values:
        assert all(raw not in value for value in rendered)
    assert all("**********" in value for value in rendered)


def test_missing_secrets_sorts_and_deduplicates_names() -> None:
    error = MissingSecrets(["SMTP_PASS", "KIS_APP_KEY", "SMTP_PASS"])

    assert error.names == ("KIS_APP_KEY", "SMTP_PASS")
    assert str(error) == "required secrets are missing: KIS_APP_KEY, SMTP_PASS"
    with pytest.raises(ValueError, match="at least one"):
        MissingSecrets([])


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Linux mode contract")
def test_linux_env_file_mode_warns_unless_it_is_exactly_0600(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_secret_environment(monkeypatch)
    insecure = tmp_path / ".env.insecure"
    secure = tmp_path / ".env.secure"
    _write_env(insecure, "KIS_APP_KEY=fake-insecure-source\n", mode=0o640)
    _write_env(secure, "KIS_APP_KEY=fake-secure-source\n")

    with pytest.warns(RuntimeWarning, match=r"0o640.*0o600"):
        load_secrets((insecure,))

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        load_secrets((secure,))
    assert caught == []
