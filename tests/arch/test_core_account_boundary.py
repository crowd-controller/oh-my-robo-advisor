"""Account domain objects must never gain external credential fields."""

from pathlib import Path

from omra.core import Account

_ACCOUNTS_SOURCE = Path(__file__).resolve().parents[2] / "src" / "omra" / "core" / "accounts.py"


def test_account_source_contains_no_external_credential_vocabulary() -> None:
    source = _ACCOUNTS_SOURCE.read_text(encoding="utf-8")
    forbidden = ("CANO", "ACNT_PRDT_CD", "appkey", "appsecret", "account_number")

    assert [token for token in forbidden if token in source] == []


def test_account_schema_exposes_only_internal_domain_fields() -> None:
    assert set(Account.model_json_schema()["properties"]) == {"id", "type", "broker", "mode"}
