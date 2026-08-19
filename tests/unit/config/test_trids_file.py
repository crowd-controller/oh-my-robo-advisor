"""Unit contracts for the raw KIS TR-ID record and environment safety gate."""

import warnings
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from omra.config import ConfigValidationError, UnsupportedInEnvError
from omra.config.files import (
    RecordFile,
    RestBaseUrls,
    RestSection,
    RestTr,
    TrIdsRaw,
    WsEndpoint,
    WsSection,
    WsTrTable,
    validate_tr_ids_for_env,
)
from omra.config.schema.run import ExecEnv

_ROOT = Path(__file__).resolve().parents[3]
_SEED = _ROOT / "config" / "tr_ids.kis.yaml"
_SEED_UNRESOLVED_PATHS = (
    "rest.base_url.live",
    "rest.base_url.paper",
    "rest.trs[0].tr_id",
    "rest.trs[0].path",
    "rest.trs[2].tr_id",
    "rest.trs[4].tr_id",
    "rest.trs[5].tr_id",
    "ws.live.url",
    "ws.paper.url",
    "ws.paper.tr.exec_notice_domestic",
    "ws.paper.tr.exec_notice_overseas",
)


def _resolved_values() -> dict[str, object]:
    return {
        "rest": {
            "live_prefix": "T",
            "paper_prefix": "V",
            "base_url": {
                "live": "https://live.example.test",
                "paper": "https://paper.example.test",
            },
            "trs": [
                {
                    "name": "holiday",
                    "tr_id": "CTCA0903R",
                    "bucket": "BATCH",
                }
            ],
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


def _rest(values: dict[str, object]) -> dict[str, object]:
    rest = values["rest"]
    assert isinstance(rest, dict)
    return rest


def _rest_rows(values: dict[str, object]) -> list[dict[str, object]]:
    rows = _rest(values)["trs"]
    assert isinstance(rows, list)
    return rows


def _ws_endpoint(values: dict[str, object], env: str) -> dict[str, object]:
    ws = values["ws"]
    assert isinstance(ws, dict)
    endpoint = ws[env]
    assert isinstance(endpoint, dict)
    return endpoint


def test_seed_record_loads_the_canonical_kis_mapping() -> None:
    loaded = RecordFile.load(_SEED, TrIdsRaw)

    assert loaded is not None
    assert loaded.model is TrIdsRaw
    assert tuple(row.name for row in loaded.data.rest.trs) == (
        "balance_domestic",
        "multiprice",
        "overseas_price",
        "holiday",
        "fx_reference_rate",
        "etf_nav",
        "stock_info",
    )
    assert loaded.data.rest.trs[1].tr_id == "FHKST11300006"
    assert loaded.data.rest.trs[3].tr_id == "CTCA0903R"
    assert loaded.data.rest.trs[6].tr_id == "CTPF1002R"
    assert loaded.data.ws.live.port == 21000
    assert loaded.data.ws.live.tr.book_top == "H0STASP0"
    assert loaded.data.ws.live.tr.us_quote_tick == "HDFSCNT0"


def test_seed_reports_only_explicit_unresolved_markers_as_stable_yaml_paths() -> None:
    loaded = RecordFile.load(_SEED, TrIdsRaw)

    assert loaded is not None
    assert loaded.data.unresolved() == _SEED_UNRESOLVED_PATHS
    assert "FHKST11300006" not in str(loaded.data.unresolved())
    assert "H0STCNI0" not in str(loaded.data.unresolved())


def test_live_rejects_every_unresolved_seed_path_without_exposing_values() -> None:
    loaded = RecordFile.load(_SEED, TrIdsRaw)
    assert loaded is not None

    with pytest.raises(UnsupportedInEnvError) as raised:
        validate_tr_ids_for_env(loaded.data, ExecEnv.LIVE)

    assert raised.value.env == "live"
    assert raised.value.paths == _SEED_UNRESOLVED_PATHS
    assert raised.value.code == "config.unsupported_in_env"
    assert "공식 문서의 실전 REST 도메인" not in str(raised.value)
    assert all(path in str(raised.value) for path in _SEED_UNRESOLVED_PATHS)


@pytest.mark.parametrize("env", [ExecEnv.PAPER, ExecEnv.DRY_RUN])
def test_non_live_environments_warn_and_return_every_unresolved_seed_path(env: ExecEnv) -> None:
    loaded = RecordFile.load(_SEED, TrIdsRaw)
    assert loaded is not None

    with pytest.warns(RuntimeWarning, match=r"rest\.base_url\.live"):
        paths = validate_tr_ids_for_env(loaded.data, env)

    assert paths == _SEED_UNRESOLVED_PATHS


@pytest.mark.parametrize("env", list(ExecEnv))
def test_fully_resolved_mapping_is_safe_in_every_environment(env: ExecEnv) -> None:
    raw = TrIdsRaw.model_validate(_resolved_values())

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        paths = validate_tr_ids_for_env(raw, env)

    assert paths == ()


@pytest.mark.parametrize("tr_id", ["lowercase", "ABC-123", "ABC_123", ""])
def test_transaction_ids_reject_noncanonical_spellings(tr_id: str) -> None:
    with pytest.raises(ValidationError) as raised:
        RestTr(name="holiday", tr_id=tr_id, bucket="BATCH")

    assert raised.value.errors()[0]["loc"] == ("tr_id",)


@pytest.mark.parametrize("name", ["A_name", "a", "bad-name", "a" * 33])
def test_rest_names_reject_noncanonical_spellings(name: str) -> None:
    with pytest.raises(ValidationError) as raised:
        RestTr(name=name, tr_id="CTCA0903R", bucket="BATCH")

    assert raised.value.errors()[0]["loc"] == ("name",)


@pytest.mark.parametrize(
    ("field", "value"),
    [("method", "PATCH"), ("method", "get"), ("bucket", "ORDERING"), ("bucket", "quote")],
)
def test_rest_literals_are_closed_to_the_canonical_vocabulary(field: str, value: str) -> None:
    values: dict[str, object] = {
        "name": "holiday",
        "tr_id": "CTCA0903R",
        "bucket": "BATCH",
    }
    values[field] = value

    with pytest.raises(ValidationError) as raised:
        RestTr.model_validate(values)

    assert raised.value.errors()[0]["loc"] == (field,)


def test_unresolved_marker_is_valid_raw_data_for_rest_and_websocket_fields() -> None:
    marker = "<확인 필요 — 운영자가 검증>"
    values = _resolved_values()
    row = _rest_rows(values)[0]
    row["tr_id"] = marker
    row["path"] = marker
    _rest(values)["base_url"] = {"live": marker, "paper": marker}
    for env in ("live", "paper"):
        endpoint = _ws_endpoint(values, env)
        endpoint["url"] = marker
        endpoint["tr"] = {
            "exec_notice_domestic": marker,
            "exec_notice_overseas": marker,
        }

    raw = TrIdsRaw.model_validate(values)

    assert raw.rest.trs[0].tr_id == marker
    assert raw.ws.paper.tr.exec_notice_domestic == marker
    assert len(raw.unresolved()) == 10


def test_rest_prefixes_are_single_distinct_uppercase_letters() -> None:
    for live_prefix, paper_prefix in (("TT", "V"), ("t", "V"), ("T", "T")):
        values = _resolved_values()
        rest = _rest(values)
        rest["live_prefix"] = live_prefix
        rest["paper_prefix"] = paper_prefix

        with pytest.raises(ValidationError):
            TrIdsRaw.model_validate(values)


def test_duplicate_rest_names_are_rejected() -> None:
    values = _resolved_values()
    _rest_rows(values).append({"name": "holiday", "tr_id": "CTCA0903R", "bucket": "BATCH"})

    with pytest.raises(ValidationError, match="must be unique"):
        TrIdsRaw.model_validate(values)


@pytest.mark.parametrize("port", [0, 65536])
def test_websocket_port_is_bounded_when_present(port: int) -> None:
    values = _resolved_values()
    _ws_endpoint(values, "live")["port"] = port

    with pytest.raises(ValidationError) as raised:
        TrIdsRaw.model_validate(values)

    assert raised.value.errors()[0]["loc"] == ("ws", "live", "port")


def test_websocket_execution_notices_are_required_but_other_rows_are_optional() -> None:
    minimal = WsTrTable(
        exec_notice_domestic="H0STCNI0",
        exec_notice_overseas="H0GSCNI0",
    )
    assert minimal.book_top is None
    assert minimal.us_quote_tick is None

    values = _resolved_values()
    endpoint = _ws_endpoint(values, "paper")
    endpoint["tr"] = {"exec_notice_domestic": "H0STCNI0"}
    with pytest.raises(ValidationError) as raised:
        TrIdsRaw.model_validate(values)
    assert raised.value.errors()[0]["loc"] == (
        "ws",
        "paper",
        "tr",
        "exec_notice_overseas",
    )


def test_models_forbid_unknown_fields_and_are_frozen() -> None:
    values = _resolved_values()
    values["broker"] = "kis"
    with pytest.raises(ValidationError) as raised:
        TrIdsRaw.model_validate(values)
    assert raised.value.errors()[0]["loc"] == ("broker",)

    raw = TrIdsRaw.model_validate(_resolved_values())
    root_field = "rest"
    with pytest.raises(ValidationError, match="frozen"):
        setattr(raw, root_field, raw.rest)
    row_field = "tr_id"
    with pytest.raises(ValidationError, match="frozen"):
        setattr(raw.rest.trs[0], row_field, "CTCA0904R")


def test_model_fields_and_defaults_match_the_raw_record_contract() -> None:
    assert tuple(RestBaseUrls.model_fields) == ("live", "paper")
    assert tuple(RestTr.model_fields) == (
        "name",
        "tr_id",
        "method",
        "path",
        "bucket",
        "paper_supported",
    )
    assert tuple(RestSection.model_fields) == (
        "live_prefix",
        "paper_prefix",
        "base_url",
        "trs",
    )
    assert tuple(WsTrTable.model_fields) == (
        "exec_notice_domestic",
        "exec_notice_overseas",
        "book_top",
        "market_status",
        "quote_tick",
        "etf_nav",
        "us_book_top",
        "us_quote_tick",
    )
    assert tuple(WsEndpoint.model_fields) == ("url", "port", "tr")
    assert tuple(WsSection.model_fields) == ("live", "paper")
    assert tuple(TrIdsRaw.model_fields) == ("rest", "ws")

    row = RestTr(name="holiday", tr_id="CTCA0903R", bucket="BATCH")
    assert row.method == "GET"
    assert row.path is None
    assert row.paper_supported is True


def test_record_file_reports_invalid_transaction_path_and_source(tmp_path: Path) -> None:
    source = tmp_path / "tr_ids.kis.yaml"
    values = _resolved_values()
    _rest_rows(values)[0]["tr_id"] = "lower_case"
    source.write_text(
        yaml.safe_dump(values, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )

    with pytest.raises(ConfigValidationError) as raised:
        RecordFile.load(source, TrIdsRaw)

    assert raised.value.violations[0].path == "rest.trs[0].tr_id"
    assert raised.value.violations[0].source == source


def test_unsupported_environment_error_preserves_stable_unique_paths() -> None:
    error = UnsupportedInEnvError("live", ["rest.a", "ws.b", "rest.a"])

    assert error.env == "live"
    assert error.paths == ("rest.a", "ws.b")
    assert error.code == "config.unsupported_in_env"
    with pytest.raises(ValueError, match="at least one path"):
        UnsupportedInEnvError("live", [])
