"""Unit contracts for the surveillance.yaml record schema."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from omra.config import ConfigSyntaxError, ConfigValidationError
from omra.config.files import RecordFile, SurveillanceMapFile, SurvMapEntry


def _required_entries() -> list[dict[str, object]]:
    return [
        {"risk_type": "KR-01", "level": "SV3"},
        {"risk_type": "KR-02", "level": "SV2", "esc_proposal": "ESC_REPLACE"},
        {"risk_type": "KR-03", "level": "SV2", "notify": "SV1"},
        {
            "risk_type": "KR-04",
            "level": "SV2",
            "esc_proposal": "ESC_REPLACE",
            "deadline_from": "lstg_abol_dt",
        },
        {
            "risk_type": "KR-12",
            "level": "SV3",
            "notify": "SV1",
            "effective_from": "td_stop_dt",
        },
        {"risk_type": "US-01", "level": "SV3"},
        {"risk_type": "US-02", "level": "SV2", "esc_proposal": "ESC_REPLACE"},
    ]


def _file_values() -> dict[str, object]:
    return {"version": 1, "map": _required_entries()}


def test_surveillance_map_matches_the_seven_canonical_baseline_entries() -> None:
    surveillance = SurveillanceMapFile.model_validate(_file_values())
    entries = {entry.risk_type: entry for entry in surveillance.map}

    assert surveillance.version == 1
    assert tuple(entries) == ("KR-01", "KR-02", "KR-03", "KR-04", "KR-12", "US-01", "US-02")
    assert entries["KR-01"].level == "SV3"
    assert entries["KR-02"].esc_proposal == "ESC_REPLACE"
    assert entries["KR-03"].notify == "SV1"
    assert entries["KR-04"].deadline_from == "lstg_abol_dt"
    assert entries["KR-12"].effective_from == "td_stop_dt"
    assert entries["US-01"].hold_orders is False
    assert entries["US-02"].p9_exempt is False
    assert entries["US-02"].requires_source is None


def test_m9_rows_use_requires_source_and_the_ascii_prime_token() -> None:
    values = _file_values()
    entries = values["map"]
    assert isinstance(entries, list)
    entries.extend(
        [
            {
                "risk_type": "KR-09",
                "level": "SV0",
                "hold_orders": True,
                "p9_exempt": True,
                "requires_source": "kis_ws_market",
            },
            {
                "risk_type": "KR-01P",
                "level": "SV3",
                "requires_source": "kis_ws_market",
            },
        ]
    )

    surveillance = SurveillanceMapFile.model_validate(values)

    assert surveillance.map[-2].risk_type == "KR-09"
    assert surveillance.map[-2].hold_orders is True
    assert surveillance.map[-2].p9_exempt is True
    assert surveillance.map[-1].risk_type == "KR-01P"
    assert surveillance.map[-1].requires_source == "kis_ws_market"


def test_unicode_prime_risk_type_is_rejected_in_favor_of_kr_01p() -> None:
    values = _file_values()
    entries = values["map"]
    assert isinstance(entries, list)
    entries.append({"risk_type": "KR-01\u2032", "level": "SV3"})

    with pytest.raises(ValidationError, match=r"U\+2032 prime") as raised:
        SurveillanceMapFile.model_validate(values)

    assert raised.value.errors()[0]["loc"] == ("map", 7, "risk_type")


def test_every_baseline_risk_type_is_required() -> None:
    values = _file_values()
    entries = values["map"]
    assert isinstance(entries, list)
    entries.pop()

    with pytest.raises(ValidationError, match="US-02") as raised:
        SurveillanceMapFile.model_validate(values)

    assert raised.value.errors()[0]["loc"] == ("map",)


def test_risk_type_values_must_be_unique() -> None:
    values = _file_values()
    entries = values["map"]
    assert isinstance(entries, list)
    entries.append({"risk_type": "KR-01", "level": "SV0"})

    with pytest.raises(ValidationError, match=r"duplicates=.*KR-01") as raised:
        SurveillanceMapFile.model_validate(values)

    assert raised.value.errors()[0]["loc"] == ("map",)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("level", "SV4"),
        ("notify", "SV2"),
        ("notify", True),
        ("esc_proposal", "ESC_LIQUIDATE"),
        ("esc_proposal", "replace"),
    ],
)
def test_level_notification_and_escalation_vocabularies_are_exact(
    field: str,
    value: object,
) -> None:
    values = _file_values()
    entries = values["map"]
    assert isinstance(entries, list)
    entries[0][field] = value

    with pytest.raises(ValidationError) as raised:
        SurveillanceMapFile.model_validate(values)

    assert raised.value.errors()[0]["loc"] == ("map", 0, field)


@pytest.mark.parametrize("version", [0, -1])
def test_version_must_be_positive(version: int) -> None:
    values = _file_values()
    values["version"] = version

    with pytest.raises(ValidationError) as raised:
        SurveillanceMapFile.model_validate(values)

    assert raised.value.errors()[0]["loc"] == ("version",)


@pytest.mark.parametrize("field", ["enabled", "tax_event", "freeze_vol_scale"])
def test_entry_rejects_parallel_switches_and_unaccepted_actions(field: str) -> None:
    values = _file_values()
    entries = values["map"]
    assert isinstance(entries, list)
    entries[0][field] = True

    with pytest.raises(ValidationError) as raised:
        SurveillanceMapFile.model_validate(values)

    assert raised.value.errors()[0]["loc"] == ("map", 0, field)


def test_row_and_file_are_frozen_and_forbid_unknown_fields() -> None:
    entry = SurvMapEntry(risk_type="KR-01", level="SV3")
    entry_field = "level"
    with pytest.raises(ValidationError, match="frozen"):
        setattr(entry, entry_field, "SV2")

    surveillance = SurveillanceMapFile.model_validate(_file_values())
    file_field = "version"
    with pytest.raises(ValidationError, match="frozen"):
        setattr(surveillance, file_field, 2)

    with pytest.raises(ValidationError) as raised:
        SurveillanceMapFile.model_validate({**_file_values(), "catalog": []})
    assert raised.value.errors()[0]["loc"] == ("catalog",)


def test_model_fields_match_the_canonical_record_contract() -> None:
    assert tuple(SurvMapEntry.model_fields) == (
        "risk_type",
        "level",
        "notify",
        "esc_proposal",
        "deadline_from",
        "effective_from",
        "hold_orders",
        "p9_exempt",
        "requires_source",
    )
    assert tuple(SurveillanceMapFile.model_fields) == ("version", "map")


def test_record_file_loads_canonical_surveillance_mapping(tmp_path: Path) -> None:
    source = tmp_path / "surveillance.yaml"
    source.write_text(
        """version: 1
map:
  - {risk_type: KR-01, level: SV3}
  - {risk_type: KR-02, level: SV2, esc_proposal: ESC_REPLACE}
  - {risk_type: KR-03, level: SV2, notify: SV1}
  - {risk_type: KR-04, level: SV2, esc_proposal: ESC_REPLACE, deadline_from: lstg_abol_dt}
  - {risk_type: KR-12, level: SV3, notify: SV1, effective_from: td_stop_dt}
  - {risk_type: US-01, level: SV3}
  - {risk_type: US-02, level: SV2, esc_proposal: ESC_REPLACE}
  - risk_type: KR-09
    level: SV0
    hold_orders: true
    p9_exempt: true
    requires_source: kis_ws_market
  - {risk_type: KR-01P, level: SV3, requires_source: kis_ws_market}
""",
        encoding="utf-8",
    )

    loaded = RecordFile.load(source, SurveillanceMapFile)

    assert loaded is not None
    assert loaded.model is SurveillanceMapFile
    assert len(loaded.data.map) == 9
    assert loaded.data.map[-2].hold_orders is True
    assert loaded.data.map[-1].risk_type == "KR-01P"


def test_record_file_rejects_duplicate_yaml_keys(tmp_path: Path) -> None:
    source = tmp_path / "surveillance.yaml"
    source.write_text("version: 1\nversion: 2\nmap: []\n", encoding="utf-8")

    with pytest.raises(ConfigSyntaxError, match="duplicate key 'version'"):
        RecordFile.load(source, SurveillanceMapFile)


def test_record_file_reports_entry_field_path_and_source(tmp_path: Path) -> None:
    source = tmp_path / "surveillance.yaml"
    source.write_text(
        """version: 1
map:
  - {risk_type: KR-01, level: SV3}
  - {risk_type: KR-02, level: SV2, esc_proposal: ESC_REPLACE}
  - {risk_type: KR-03, level: SV2, notify: SV1}
  - {risk_type: KR-04, level: SV2, esc_proposal: ESC_REPLACE, deadline_from: lstg_abol_dt}
  - {risk_type: KR-12, level: SV3, notify: SV1, effective_from: td_stop_dt}
  - {risk_type: US-01, level: SV3}
  - {risk_type: US-02, level: SV2, esc_proposal: ESC_LIQUIDATE}
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigValidationError) as raised:
        RecordFile.load(source, SurveillanceMapFile)

    violation = raised.value.violations[0]
    assert violation.source == source
    assert violation.path == "map[6].esc_proposal"


def test_record_file_rejects_sequence_document_at_root(tmp_path: Path) -> None:
    source = tmp_path / "surveillance.yaml"
    source.write_text("- risk_type: KR-01\n  level: SV3\n", encoding="utf-8")

    with pytest.raises(ConfigValidationError) as raised:
        RecordFile.load(source, SurveillanceMapFile)

    assert raised.value.violations[0].code == "invalid_root"
    assert raised.value.violations[0].path == "$"
