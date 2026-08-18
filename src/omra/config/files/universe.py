"""Strict schema for the independently loaded universe registry."""

from collections.abc import Mapping
from datetime import date
from typing import Final, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from omra.core import AccountType, Dec, DomainError, Instrument, Market, TickRuleId

_ASSET_CLASSES: Final[frozenset[str]] = frozenset(
    {
        "kr_etf_equity",
        "kr_etf_bond",
        "kr_etf_bond_ultrashort",
        "kr_etf_reit",
        "kr_etf_gold",
        "kr_etf_us_equity",
        "kr_etf_us_dividend",
        "us_etf_equity",
        "us_etf_bond",
        "us_etf_reit",
        "us_etf_gold",
        "us_etf_tips",
        "us_stock",
        "crypto",
    }
)


class UniverseInstrument(BaseModel):
    """One universe row with both allocation metadata and a core instrument contract."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    symbol: str
    market: Market
    currency: Literal["KRW", "USD"]
    asset_class: str
    sleeve: Literal["core", "momentum", "crypto"]
    tax_inefficiency_score: int = Field(ge=0, le=5)
    risk_asset: bool
    lot_step: Dec
    tick_rule: TickRuleId
    allowed_accounts: tuple[AccountType, ...]
    account_preference: Mapping[AccountType, int]
    qualified_tdf: bool = False
    proxy_index_key: str | None = None
    fx_hedged: bool = False

    @field_validator("asset_class")
    @classmethod
    def _validate_asset_class(cls, value: str) -> str:
        if value not in _ASSET_CLASSES:
            allowed = ", ".join(sorted(_ASSET_CLASSES))
            msg = f"asset_class must be one of: {allowed}"
            raise ValueError(msg)
        return value

    @model_validator(mode="after")
    def _validate_record_contract(self) -> Self:
        allowed = frozenset(self.allowed_accounts)
        preferred = frozenset(self.account_preference)
        if preferred != allowed:
            missing = sorted(account.value for account in allowed - preferred)
            extra = sorted(account.value for account in preferred - allowed)
            msg = (
                "account_preference keys must exactly match allowed_accounts "
                f"(missing={missing}, extra={extra})"
            )
            raise ValueError(msg)

        try:
            self.to_instrument()
        except DomainError as error:
            raise ValueError(str(error)) from error
        return self

    def to_instrument(self) -> Instrument:
        """Convert exactly the execution fields into the immutable core model."""
        return Instrument(
            symbol=self.symbol,
            market=self.market,
            currency=self.currency,
            asset_class=self.asset_class,
            lot_step=self.lot_step,
            tick_rule=self.tick_rule,
        )

    @property
    def key(self) -> str:
        """Return the canonical exact-match key of the converted core instrument."""
        return self.to_instrument().key


class UniverseFile(BaseModel):
    """Versioned human-approved universe input, independent of scalar config layers."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    version: int = Field(ge=1)
    approved_at: date
    instruments: tuple[UniverseInstrument, ...]
    approved_substitutes: tuple[tuple[str, str], ...] = ()


__all__ = ["UniverseFile", "UniverseInstrument"]
