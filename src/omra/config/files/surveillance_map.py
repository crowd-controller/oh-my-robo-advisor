"""Strict schema for the externalized surveillance risk-to-action map."""

from collections import Counter
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

_REQUIRED_RISK_TYPES = frozenset(
    {
        "KR-01",
        "KR-02",
        "KR-03",
        "KR-04",
        "KR-12",
        "US-01",
        "US-02",
    }
)
_UNICODE_PRIME = "\N{PRIME}"


class SurvMapEntry(BaseModel):
    """One exact-match surveillance risk mapping and its reversible actions."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    risk_type: str
    level: Literal["SV0", "SV1", "SV2", "SV3"]
    notify: Literal["SV1"] | None = None
    esc_proposal: Literal["ESC_REPLACE"] | None = None
    deadline_from: str | None = None
    effective_from: str | None = None
    hold_orders: bool = False
    p9_exempt: bool = False
    requires_source: str | None = None

    @field_validator("risk_type")
    @classmethod
    def _reject_ambiguous_prime(cls, value: str) -> str:
        if _UNICODE_PRIME in value:
            raise ValueError(
                "risk_type must use the canonical ASCII token KR-01P, not U+2032 prime"
            )
        return value


class SurveillanceMapFile(BaseModel):
    """Versioned surveillance map containing every mandatory baseline risk type."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    version: int = Field(ge=1)
    map: tuple[SurvMapEntry, ...]

    @field_validator("map")
    @classmethod
    def _validate_risk_types(
        cls,
        value: tuple[SurvMapEntry, ...],
    ) -> tuple[SurvMapEntry, ...]:
        counts = Counter(entry.risk_type for entry in value)
        duplicates = sorted(risk_type for risk_type, count in counts.items() if count > 1)
        if duplicates:
            raise ValueError(f"risk_type values must be unique (duplicates={duplicates})")

        missing = sorted(_REQUIRED_RISK_TYPES - counts.keys())
        if missing:
            raise ValueError(f"surveillance map is missing required risk types: {missing}")
        return value


__all__ = ["SurvMapEntry", "SurveillanceMapFile"]
