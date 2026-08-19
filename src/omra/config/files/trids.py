"""Strict raw schema and environment safety gate for KIS TR-ID configuration."""

import re
import warnings
from collections import Counter
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from omra.config.errors import UnsupportedInEnvError
from omra.config.schema.run import ExecEnv

_UNRESOLVED_PREFIX: Final = "<확인 필요"
_TR_ID_PATTERN: Final = re.compile(r"^[A-Z0-9]+$")
_TR_NAME_PATTERN: Final = r"^[a-z][a-z0-9_]{1,31}$"

HttpMethod = Literal["GET", "POST"]
PriorityBucket = Literal["ORDER", "QUOTE", "BATCH"]


def _is_unresolved(value: str) -> bool:
    return value.startswith(_UNRESOLVED_PREFIX)


def _validate_tr_id(value: str) -> str:
    if _is_unresolved(value) or _TR_ID_PATTERN.fullmatch(value):
        return value
    raise ValueError(
        "tr_id must contain only uppercase ASCII letters and digits, "
        f"or start with {_UNRESOLVED_PREFIX!r}"
    )


class RestBaseUrls(BaseModel):
    """Environment-specific KIS REST endpoints without interpretation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    live: str = Field(min_length=1)
    paper: str = Field(min_length=1)


class RestTr(BaseModel):
    """One raw REST transaction row owned by the external YAML mapping."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=2, max_length=32, pattern=_TR_NAME_PATTERN)
    tr_id: str = Field(min_length=1)
    method: HttpMethod = "GET"
    path: str | None = Field(default=None, min_length=1)
    bucket: PriorityBucket
    paper_supported: bool = True

    @field_validator("tr_id")
    @classmethod
    def _validate_transaction_id(cls, value: str) -> str:
        return _validate_tr_id(value)


class RestSection(BaseModel):
    """Raw REST prefix rules, endpoints, and named transaction rows."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    live_prefix: str = Field(min_length=1, max_length=1, pattern=r"^[A-Z]$")
    paper_prefix: str = Field(min_length=1, max_length=1, pattern=r"^[A-Z]$")
    base_url: RestBaseUrls
    trs: tuple[RestTr, ...]

    @field_validator("trs")
    @classmethod
    def _reject_duplicate_names(cls, value: tuple[RestTr, ...]) -> tuple[RestTr, ...]:
        counts = Counter(row.name for row in value)
        duplicates = sorted(name for name, count in counts.items() if count > 1)
        if duplicates:
            raise ValueError(f"REST transaction names must be unique (duplicates={duplicates})")
        return value

    @model_validator(mode="after")
    def _require_distinct_prefixes(self) -> "RestSection":
        if self.live_prefix == self.paper_prefix:
            raise ValueError("live_prefix and paper_prefix must be different")
        return self


class WsTrTable(BaseModel):
    """Closed KIS WebSocket transaction vocabulary from design 05 §7.1."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    exec_notice_domestic: str = Field(min_length=1)
    exec_notice_overseas: str = Field(min_length=1)
    book_top: str | None = Field(default=None, min_length=1)
    market_status: str | None = Field(default=None, min_length=1)
    quote_tick: str | None = Field(default=None, min_length=1)
    etf_nav: str | None = Field(default=None, min_length=1)
    us_book_top: str | None = Field(default=None, min_length=1)
    us_quote_tick: str | None = Field(default=None, min_length=1)

    @field_validator(
        "exec_notice_domestic",
        "exec_notice_overseas",
        "book_top",
        "market_status",
        "quote_tick",
        "etf_nav",
        "us_book_top",
        "us_quote_tick",
    )
    @classmethod
    def _validate_transaction_ids(cls, value: str | None) -> str | None:
        return None if value is None else _validate_tr_id(value)


class WsEndpoint(BaseModel):
    """One environment's explicit WebSocket endpoint and TR table."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    url: str = Field(min_length=1)
    port: int | None = Field(default=None, ge=1, le=65535)
    tr: WsTrTable


class WsSection(BaseModel):
    """Live and paper WebSocket mappings, which cannot use REST prefix replacement."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    live: WsEndpoint
    paper: WsEndpoint


class TrIdsRaw(BaseModel):
    """Validated raw KIS mapping; broker-side interpretation remains out of config."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    rest: RestSection
    ws: WsSection

    def unresolved(self) -> tuple[str, ...]:
        """Return every explicit unresolved marker as a deterministic YAML path."""
        paths: list[str] = []

        def add(path: str, value: str | None) -> None:
            if value is not None and _is_unresolved(value):
                paths.append(path)

        add("rest.base_url.live", self.rest.base_url.live)
        add("rest.base_url.paper", self.rest.base_url.paper)
        for index, row in enumerate(self.rest.trs):
            add(f"rest.trs[{index}].tr_id", row.tr_id)
            add(f"rest.trs[{index}].path", row.path)

        for env_name, endpoint in (("live", self.ws.live), ("paper", self.ws.paper)):
            add(f"ws.{env_name}.url", endpoint.url)
            table = endpoint.tr
            for name, value in (
                ("exec_notice_domestic", table.exec_notice_domestic),
                ("exec_notice_overseas", table.exec_notice_overseas),
                ("book_top", table.book_top),
                ("market_status", table.market_status),
                ("quote_tick", table.quote_tick),
                ("etf_nav", table.etf_nav),
                ("us_book_top", table.us_book_top),
                ("us_quote_tick", table.us_quote_tick),
            ):
                add(f"ws.{env_name}.tr.{name}", value)

        return tuple(paths)


def validate_tr_ids_for_env(raw: TrIdsRaw, env: ExecEnv) -> tuple[str, ...]:
    """Reject unresolved live configuration and warn in non-live environments."""
    paths = raw.unresolved()
    if not paths:
        return ()
    if env is ExecEnv.LIVE:
        raise UnsupportedInEnvError(env.value, paths)

    warnings.warn(
        f"KIS TR-ID configuration has unresolved paths for {env.value}: {', '.join(paths)}",
        RuntimeWarning,
        stacklevel=2,
    )
    return paths


__all__ = [
    "HttpMethod",
    "PriorityBucket",
    "RestBaseUrls",
    "RestSection",
    "RestTr",
    "TrIdsRaw",
    "WsEndpoint",
    "WsSection",
    "WsTrTable",
    "validate_tr_ids_for_env",
]
