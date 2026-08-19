"""Single recursive credential masker shared by audit and cassette boundaries."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Literal

MASKED = "***"

_SENSITIVE_KEYS = frozenset(
    {
        "accesstoken",
        "accesskey",
        "acntprdtcd",
        "appkey",
        "appsecret",
        "approvalkey",
        "authorization",
        "cano",
        "htsid",
        "secretkey",
        "upbitaccesskey",
        "upbitsecretkey",
    }
)


def _normalized_key(value: object) -> str:
    return "".join(character for character in str(value).casefold() if character.isalnum())


class Masker:
    """Mask broker credential keys and every explicitly registered secret value."""

    __slots__ = ("_secret_values",)

    def __init__(self, secret_values: Iterable[str] = ()) -> None:
        self._secret_values = tuple(
            sorted(
                {value for value in secret_values if value},
                key=len,
                reverse=True,
            )
        )

    @property
    def secret_values(self) -> tuple[str, ...]:
        """Return only the registered values needed for deterministic composition."""
        return self._secret_values

    def _mask_string(self, value: str) -> str:
        masked = value
        for secret in self._secret_values:
            masked = masked.replace(secret, MASKED)
        return masked

    def _mask_value(self, value: object) -> object:
        if isinstance(value, Mapping):
            return {
                str(key): (
                    MASKED if _normalized_key(key) in _SENSITIVE_KEYS else self._mask_value(nested)
                )
                for key, nested in value.items()
            }
        if isinstance(value, (list, tuple)):
            return [self._mask_value(item) for item in value]
        if isinstance(value, str):
            return self._mask_string(value)
        return value

    def mask(
        self,
        payload: Mapping[str, object],
        *,
        direction: Literal["req", "res"],
    ) -> dict[str, object]:
        """Return a detached recursively masked mapping for request or response storage."""
        if direction not in {"req", "res"}:
            raise ValueError("masking direction must be 'req' or 'res'")
        masked = self._mask_value(payload)
        if not isinstance(masked, dict):
            raise TypeError("masked payload root must remain a mapping")
        return masked


def mask_payload(
    payload: Mapping[str, object],
    *,
    direction: Literal["req", "res"],
) -> dict[str, object]:
    """Mask credential-bearing keys without a separately injected value registry."""
    return Masker().mask(payload, direction=direction)


__all__ = ["MASKED", "Masker", "mask_payload"]
