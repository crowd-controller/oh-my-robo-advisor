"""Unit contracts for the SC-13 credential placement policy."""

from typing import cast

import pytest

from omra.config import (
    CATALOG,
    ConfigError,
    CredentialSurface,
    ExecEnv,
    MissingSecrets,
    Secrets,
    check_credential_placement,
    has_smtp,
    has_telegram,
)

_TELEGRAM_NAMES = frozenset({"TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"})
_SMTP_NAMES = frozenset({"SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASS"})
_CHANNEL_NAMES = _TELEGRAM_NAMES | _SMTP_NAMES
_TOOLS_FORBIDDEN_NAMES = tuple(
    spec.name for spec in CATALOG if spec.surface == "app" and spec.name != "ANTHROPIC_API_KEY"
)


def _complete_app_core(env: ExecEnv) -> dict[str, object]:
    return {
        spec.name: f"fake-{spec.name.lower()}"
        for spec in CATALOG
        if spec.surface == "app" and env in spec.required_in and spec.name not in _CHANNEL_NAMES
    }


def _telegram_values() -> dict[str, object]:
    return {
        "TELEGRAM_BOT_TOKEN": "fake-telegram-token",
        "TELEGRAM_CHAT_ID": "fake-telegram-chat",
    }


def _smtp_values() -> dict[str, object]:
    return {
        "SMTP_HOST": "fake-smtp-host",
        "SMTP_PORT": "fake-smtp-port",
        "SMTP_USER": "fake-smtp-user",
        "SMTP_PASS": "fake-smtp-pass",
    }


@pytest.mark.parametrize("missing", sorted(_TELEGRAM_NAMES))
def test_telegram_requires_both_non_empty_values(missing: str) -> None:
    values = _telegram_values()
    values[missing] = ""

    assert has_telegram(Secrets.model_validate(_telegram_values()))
    assert not has_telegram(Secrets.model_validate(values))


@pytest.mark.parametrize("missing", sorted(_SMTP_NAMES))
def test_smtp_requires_all_four_non_empty_values(missing: str) -> None:
    values = _smtp_values()
    values[missing] = ""

    assert has_smtp(Secrets.model_validate(_smtp_values()))
    assert not has_smtp(Secrets.model_validate(values))


def test_app_accepts_complete_telegram_as_the_live_notification_channel() -> None:
    values = _complete_app_core(ExecEnv.LIVE)
    values.update(_telegram_values())

    check_credential_placement("app", ExecEnv.LIVE, Secrets.model_validate(values))


def test_app_accepts_complete_smtp_as_the_paper_notification_channel() -> None:
    values = _complete_app_core(ExecEnv.PAPER)
    values.update(_smtp_values())

    check_credential_placement("app", ExecEnv.PAPER, Secrets.model_validate(values))


def test_app_reports_non_channel_requirements_before_channel_completeness() -> None:
    values = _complete_app_core(ExecEnv.LIVE)
    del values["KIS_APP_KEY"]
    partial_value = "fake-partial-channel-value"
    values["TELEGRAM_BOT_TOKEN"] = partial_value

    with pytest.raises(MissingSecrets) as raised:
        check_credential_placement("app", ExecEnv.LIVE, Secrets.model_validate(values))

    assert raised.value.names == ("KIS_APP_KEY",)
    assert partial_value not in str(raised.value)


def test_app_requires_one_complete_notification_channel_without_value_leakage() -> None:
    raw_values = ("fake-partial-telegram", "fake-partial-smtp")
    secrets = Secrets.model_validate(
        {
            "TELEGRAM_BOT_TOKEN": raw_values[0],
            "SMTP_HOST": raw_values[1],
        }
    )

    with pytest.raises(MissingSecrets) as raised:
        check_credential_placement("app", ExecEnv.DRY_RUN, secrets)

    assert raised.value.names == ("TELEGRAM_BOT_TOKEN|SMTP_*",)
    assert all(raw not in str(raised.value) for raw in raw_values)


def test_tools_allows_anthropic_as_the_only_app_catalog_exception() -> None:
    secrets = Secrets.model_validate({"ANTHROPIC_API_KEY": "fake-anthropic-key"})

    check_credential_placement("tools", ExecEnv.LIVE, secrets)


@pytest.mark.parametrize("name", _TOOLS_FORBIDDEN_NAMES)
def test_tools_rejects_every_forbidden_app_catalog_name_without_value_leakage(
    name: str,
) -> None:
    raw_value = f"fake-forbidden-{name.lower()}"
    secrets = Secrets.model_validate({name: raw_value})

    with pytest.raises(ConfigError) as raised:
        check_credential_placement("tools", ExecEnv.DRY_RUN, secrets)

    assert raised.value.code == "config.secret_placement"
    assert name in str(raised.value)
    assert raw_value not in str(raised.value)


def test_tools_rejects_dynamic_kis_account_values_as_the_legacy_catalog_name() -> None:
    raw_value = "fake-dynamic-account-reference"
    secrets = Secrets.model_validate({"KIS_ACCOUNT": {"GENERAL_KIS": raw_value}})

    with pytest.raises(ConfigError) as raised:
        check_credential_placement("tools", ExecEnv.DRY_RUN, secrets)

    assert "KIS_ACCOUNT_NO" in str(raised.value)
    assert raw_value not in str(raised.value)


def test_unsupported_surface_is_not_treated_as_tools() -> None:
    unsupported = cast("CredentialSurface", "litestream")

    with pytest.raises(ValueError, match="unsupported credential surface: 'litestream'"):
        check_credential_placement(unsupported, ExecEnv.DRY_RUN, Secrets.model_validate({}))
