"""Configuration-facing account registry entries."""

from pydantic import BaseModel, ConfigDict, Field

from omra.core.accounts import (
    ACCOUNT_ID_PATTERN,
    Account,
    AccountMode,
    AccountType,
    Broker,
)


class AccountCfg(BaseModel):
    """One configured account without any external account number or secret."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(pattern=ACCOUNT_ID_PATTERN)
    type: AccountType
    broker: Broker
    mode: AccountMode
    enabled: bool = True
    forbidden_asset_classes: tuple[str, ...] = ()

    def to_domain(self) -> Account:
        """Project the configuration entry into its credential-free domain value."""
        return Account(id=self.id, type=self.type, broker=self.broker, mode=self.mode)
