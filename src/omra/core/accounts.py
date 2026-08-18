"""Broker-neutral account vocabulary and identifier invariants."""

from enum import StrEnum
from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from omra.core.errors import IdentifierError
from omra.core.ids import Market
from omra.core.models import Instrument

ACCOUNT_ID_PATTERN: Final = r"^[a-z][a-z0-9_]{1,31}$"


class Broker(StrEnum):
    """External broker families known to the domain."""

    KIS = "KIS"
    UPBIT = "UPBIT"


class AccountType(StrEnum):
    """The five account types from the asset-location contract."""

    GENERAL = "general"
    ISA = "isa"
    PENSION = "pension"
    IRP = "irp"
    UPBIT = "upbit"


class AccountMode(StrEnum):
    """How an account's instructions reach its broker."""

    AUTO = "AUTO"
    BROKER_SCHEDULED = "BROKER_SCHEDULED"
    INSTRUCTION = "INSTRUCTION"


class SleeveId(StrEnum):
    """Broker-by-market sleeves used by execution protections."""

    KIS_DOMESTIC = "kis_domestic"
    KIS_OVERSEAS = "kis_overseas"
    UPBIT = "upbit"


US_MARKETS: Final[frozenset[Market]] = frozenset({Market.NASD, Market.NYSE, Market.AMEX})


class Account(BaseModel):
    """An internal account identity with no external credentials."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(pattern=ACCOUNT_ID_PATTERN)
    type: AccountType
    broker: Broker
    mode: AccountMode


def sleeve_of(account: Account, instrument: Instrument) -> SleeveId:
    """Map a broker-by-market pair to its independently controlled sleeve."""
    if account.broker is Broker.UPBIT:
        return SleeveId.UPBIT
    if instrument.market in US_MARKETS:
        return SleeveId.KIS_OVERSEAS
    if instrument.market is Market.KRX:
        return SleeveId.KIS_DOMESTIC
    raise IdentifierError(
        "account broker and instrument market do not map to a sleeve",
        context={
            "account_id": account.id,
            "broker": account.broker.value,
            "instrument_key": instrument.key,
        },
    )
