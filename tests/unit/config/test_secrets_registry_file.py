"""Unit contracts for the metadata-only secrets_registry.yaml schema."""

from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from omra.config import ConfigSyntaxError, ConfigValidationError
from omra.config.files import (
    AutoAction,
    RecordFile,
    SecretRegistryEntry,
    SecretsRegistryFile,
    SecretTier,
)
from omra.core import SleeveId


def _tier_one_values() -> dict[str, object]:
    return {
        "name": "KIS_APP_KEY",
        "issued_at": date(2026, 8, 1),
        "expires_at": date(2027, 8, 1),
        "tier": 1,
        "auto_action": "pause_all_d7_safe_mode_d3",
        "sleeves": ["kis_domestic", "kis_overseas"],
    }


def _tier_two_values() -> dict[str, object]:
    return {
        "name": "KIS_APPROVAL_KEY",
        "issued_at": date(2026, 8, 1),
        "expires_at": None,
        "tier": 2,
        "auto_action": "preemptive_reissue_daily",
    }


def test_canonical_tier_one_entry_uses_dates_enums_and_multiple_sleeves() -> None:
    entry = SecretRegistryEntry.model_validate(_tier_one_values())

    assert entry.name == "KIS_APP_KEY"
    assert entry.issued_at == date(2026, 8, 1)
    assert entry.expires_at == date(2027, 8, 1)
    assert entry.tier is SecretTier.TIER1
    assert entry.auto_action is AutoAction.PAUSE_ALL_D7_SAFE_MODE_D3
    assert entry.sleeves == (SleeveId.KIS_DOMESTIC, SleeveId.KIS_OVERSEAS)


def test_tier_and_auto_action_vocabularies_match_the_canonical_values() -> None:
    assert [tier.value for tier in SecretTier] == [1, 2, 3]
    assert [action.value for action in AutoAction] == [
        "none",
        "pause_all_d7_safe_mode_d3",
        "disable_paper_on_expiry",
        "preemptive_reissue_daily",
        "warn_on_send_fail_streak",
        "critical_on_backup_fail",
        "warn3_critical7_on_fail",
    ]


@pytest.mark.parametrize("tier", [0, 4])
def test_tier_outside_the_closed_vocabulary_is_rejected(tier: int) -> None:
    values = _tier_two_values()
    values["tier"] = tier

    with pytest.raises(ValidationError) as raised:
        SecretRegistryEntry.model_validate(values)

    assert raised.value.errors()[0]["loc"] == ("tier",)


@pytest.mark.parametrize(
    "action",
    [action for action in AutoAction if action is not AutoAction.PAUSE_ALL_D7_SAFE_MODE_D3],
)
def test_tier_one_rejects_every_other_auto_action(action: AutoAction) -> None:
    values = _tier_one_values()
    values["auto_action"] = action

    with pytest.raises(ValidationError, match="tier-1 secrets require") as raised:
        SecretRegistryEntry.model_validate(values)

    assert raised.value.errors()[0]["loc"] == ("auto_action",)


def test_tier_one_rejects_an_omitted_auto_action_instead_of_using_none() -> None:
    values = _tier_one_values()
    del values["auto_action"]

    with pytest.raises(ValidationError, match="tier-1 secrets require") as raised:
        SecretRegistryEntry.model_validate(values)

    assert raised.value.errors()[0]["loc"] == ("auto_action",)


def test_non_tier_one_entry_may_use_the_default_none_action() -> None:
    values = _tier_two_values()
    del values["auto_action"]

    assert SecretRegistryEntry.model_validate(values).auto_action is AutoAction.NONE


def test_name_values_must_be_unique() -> None:
    entry = SecretRegistryEntry.model_validate(_tier_one_values())

    with pytest.raises(ValidationError, match=r"duplicates=.*KIS_APP_KEY") as raised:
        SecretsRegistryFile((entry, entry))

    assert raised.value.errors()[0]["loc"] == ()


def test_expired_metadata_is_accepted_for_the_ladder_to_assess() -> None:
    values = _tier_two_values()
    values["issued_at"] = date(2020, 1, 1)
    values["expires_at"] = date(2021, 1, 1)

    entry = SecretRegistryEntry.model_validate(values)

    assert entry.expires_at == date(2021, 1, 1)


def test_sleeves_use_the_closed_core_vocabulary() -> None:
    values = _tier_one_values()
    values["sleeves"] = ["kis_domestic", "unsupported"]

    with pytest.raises(ValidationError) as raised:
        SecretRegistryEntry.model_validate(values)

    assert raised.value.errors()[0]["loc"] == ("sleeves", 1)


@pytest.mark.parametrize("field", ["value", "secret", "key", "owner"])
def test_secret_bearing_and_other_unknown_fields_are_rejected(field: str) -> None:
    values = _tier_two_values()
    values[field] = "must-not-enter-the-registry"

    with pytest.raises(ValidationError) as raised:
        SecretRegistryEntry.model_validate(values)

    assert raised.value.errors()[0]["loc"] == (field,)
    assert raised.value.errors()[0]["type"] == "extra_forbidden"


def test_row_and_sequence_wrapper_are_frozen() -> None:
    entry = SecretRegistryEntry.model_validate(_tier_one_values())
    registry = SecretsRegistryFile((entry,))
    row_field = "expires_at"
    with pytest.raises(ValidationError, match="frozen"):
        setattr(entry, row_field, None)
    root_field = "root"
    with pytest.raises(ValidationError, match="frozen"):
        setattr(registry, root_field, ())


def test_model_fields_match_the_canonical_record_contract() -> None:
    assert tuple(SecretRegistryEntry.model_fields) == (
        "name",
        "issued_at",
        "expires_at",
        "tier",
        "auto_action",
        "sleeves",
    )
    assert tuple(SecretsRegistryFile.model_fields) == ("root",)


def test_entries_is_a_read_only_view_of_the_canonical_root_sequence() -> None:
    entry = SecretRegistryEntry.model_validate(_tier_one_values())
    registry = SecretsRegistryFile((entry,))

    assert registry.entries is registry.root


def test_record_file_loads_the_canonical_root_sequence(tmp_path: Path) -> None:
    source = tmp_path / "secrets_registry.yaml"
    source.write_text(
        """- name: KIS_APP_KEY
  issued_at: 2026-08-01
  expires_at: 2027-08-01
  tier: 1
  auto_action: pause_all_d7_safe_mode_d3
  sleeves: [kis_domestic, kis_overseas]
- name: KIS_APPROVAL_KEY
  issued_at: 2026-08-01
  expires_at: null
  tier: 2
  auto_action: preemptive_reissue_daily
""",
        encoding="utf-8",
    )

    loaded = RecordFile.load(source, SecretsRegistryFile)

    assert loaded is not None
    assert loaded.model is SecretsRegistryFile
    assert len(loaded.data.entries) == 2
    assert loaded.data.entries[0].tier is SecretTier.TIER1
    assert loaded.data.entries[0].sleeves == (
        SleeveId.KIS_DOMESTIC,
        SleeveId.KIS_OVERSEAS,
    )
    assert loaded.data.entries[1].expires_at is None


def test_registry_sequence_reuses_duplicate_key_rejection(tmp_path: Path) -> None:
    source = tmp_path / "secrets_registry.yaml"
    source.write_text(
        """- name: KIS_APPROVAL_KEY
  issued_at: 2026-08-01
  issued_at: 2026-08-02
  expires_at: null
  tier: 2
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigSyntaxError, match="duplicate key 'issued_at'"):
        RecordFile.load(source, SecretsRegistryFile)


def test_registry_error_reports_second_row_field_and_source(tmp_path: Path) -> None:
    source = tmp_path / "secrets_registry.yaml"
    source.write_text(
        """- name: KIS_APPROVAL_KEY
  issued_at: 2026-08-01
  expires_at: null
  tier: 2
  auto_action: preemptive_reissue_daily
- name: UPBIT_ACCESS_KEY
  issued_at: 2026-02-01
  expires_at: 2027-02-01
  tier: 1
  auto_action: none
  sleeves: [upbit]
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigValidationError) as raised:
        RecordFile.load(source, SecretsRegistryFile)

    violation = raised.value.violations[0]
    assert violation.source == source
    assert violation.path == "[1].auto_action"


def test_registry_root_model_rejects_mapping_document_at_root(tmp_path: Path) -> None:
    source = tmp_path / "secrets_registry.yaml"
    source.write_text("entries: []\n", encoding="utf-8")

    with pytest.raises(ConfigValidationError) as raised:
        RecordFile.load(source, SecretsRegistryFile)

    assert raised.value.violations[0].path == "$"
