"""Unit contracts for broker-neutral account vocabulary."""

import pytest
from pydantic import ValidationError

from omra.core import Account, AccountMode, AccountType, Broker, SleeveId


def test_account_enum_values_match_the_canonical_vocabulary() -> None:
    assert [member.value for member in Broker] == ["KIS", "UPBIT"]
    assert [member.value for member in AccountType] == [
        "general",
        "isa",
        "pension",
        "irp",
        "upbit",
    ]
    assert [member.value for member in AccountMode] == [
        "AUTO",
        "BROKER_SCHEDULED",
        "INSTRUCTION",
    ]
    assert [member.value for member in SleeveId] == [
        "kis_domestic",
        "kis_overseas",
        "upbit",
    ]


def test_account_accepts_internal_slug_and_serialized_enum_values() -> None:
    account = Account.model_validate(
        {
            "id": "pension_savings",
            "type": "pension",
            "broker": "KIS",
            "mode": "BROKER_SCHEDULED",
        }
    )

    assert account.id == "pension_savings"
    assert account.type is AccountType.PENSION
    assert account.broker is Broker.KIS
    assert account.mode is AccountMode.BROKER_SCHEDULED


@pytest.mark.parametrize(
    "account_id",
    ["a", "1general", "General", "general-account", "general account", "a" * 33],
)
def test_account_rejects_noncanonical_internal_identifiers(account_id: str) -> None:
    with pytest.raises(ValidationError, match="id"):
        Account(
            id=account_id,
            type=AccountType.GENERAL,
            broker=Broker.KIS,
            mode=AccountMode.AUTO,
        )


def test_account_is_frozen_and_rejects_unknown_fields() -> None:
    account = Account(
        id="general_01",
        type=AccountType.GENERAL,
        broker=Broker.KIS,
        mode=AccountMode.AUTO,
    )

    field_name = "id"
    with pytest.raises(ValidationError, match="frozen"):
        setattr(account, field_name, "general_02")

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        Account.model_validate(
            {
                "id": "general_01",
                "type": "general",
                "broker": "KIS",
                "mode": "AUTO",
                "external_account": "should-never-be-a-domain-field",
            }
        )


def test_account_model_contains_only_internal_domain_fields() -> None:
    assert tuple(Account.model_fields) == ("id", "type", "broker", "mode")
