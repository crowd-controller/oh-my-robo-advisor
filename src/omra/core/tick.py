"""Canonical price-tick rule identifiers."""

from enum import StrEnum


class TickRuleId(StrEnum):
    """Closed vocabulary for venue-specific tick arithmetic."""

    KRX_ETF_5 = "krx_etf_5"
    KRX7 = "krx7"
    USD_PENNY = "usd_penny"
    UPBIT = "upbit"
