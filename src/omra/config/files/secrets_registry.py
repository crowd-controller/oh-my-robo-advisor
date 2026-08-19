"""Strict metadata-only schema for the secret expiry registry."""

from collections import Counter
from datetime import date
from enum import IntEnum, StrEnum

from pydantic import BaseModel, ConfigDict, Field, RootModel, ValidationInfo, field_validator

from omra.core import SleeveId


class SecretTier(IntEnum):
    """Operational impact tier for an expiring secret."""

    TIER1 = 1
    TIER2 = 2
    TIER3 = 3


class AutoAction(StrEnum):
    """Closed vocabulary of expiry-triggered operational actions."""

    NONE = "none"
    PAUSE_ALL_D7_SAFE_MODE_D3 = "pause_all_d7_safe_mode_d3"
    DISABLE_PAPER_ON_EXPIRY = "disable_paper_on_expiry"
    PREEMPTIVE_REISSUE_DAILY = "preemptive_reissue_daily"
    WARN_ON_SEND_FAIL_STREAK = "warn_on_send_fail_streak"
    CRITICAL_ON_BACKUP_FAIL = "critical_on_backup_fail"
    WARN3_CRITICAL7_ON_FAIL = "warn3_critical7_on_fail"


class SecretRegistryEntry(BaseModel):
    """Issuance and expiry metadata for one secret, never its value."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    issued_at: date
    expires_at: date | None
    tier: SecretTier
    auto_action: AutoAction = Field(default=AutoAction.NONE, validate_default=True)
    sleeves: tuple[SleeveId, ...] = ()

    @field_validator("auto_action")
    @classmethod
    def _require_tier_one_action(
        cls,
        value: AutoAction,
        info: ValidationInfo,
    ) -> AutoAction:
        if (
            info.data.get("tier") is SecretTier.TIER1
            and value is not AutoAction.PAUSE_ALL_D7_SAFE_MODE_D3
        ):
            raise ValueError("tier-1 secrets require auto_action pause_all_d7_safe_mode_d3")
        return value


class SecretsRegistryFile(RootModel[tuple[SecretRegistryEntry, ...]]):
    """The canonical sequence-root secrets_registry.yaml document."""

    model_config = ConfigDict(frozen=True)

    @field_validator("root")
    @classmethod
    def _require_unique_names(
        cls,
        value: tuple[SecretRegistryEntry, ...],
    ) -> tuple[SecretRegistryEntry, ...]:
        counts = Counter(entry.name for entry in value)
        duplicates = sorted(name for name, count in counts.items() if count > 1)
        if duplicates:
            raise ValueError(f"secret registry names must be unique (duplicates={duplicates})")
        return value

    @property
    def entries(self) -> tuple[SecretRegistryEntry, ...]:
        """Expose the design's named consumer view over the sequence-root document."""
        return self.root


__all__ = ["AutoAction", "SecretRegistryEntry", "SecretTier", "SecretsRegistryFile"]
