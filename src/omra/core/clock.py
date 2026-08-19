"""Injectable, deterministic time boundary shared by live and simulated runs."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from datetime import UTC, datetime, timedelta
from typing import Final
from zoneinfo import ZoneInfo

from omra.core.errors import InvariantViolation

KST: Final = ZoneInfo("Asia/Seoul")


def _aware(value: datetime, *, name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise InvariantViolation(f"{name} must be timezone-aware")
    return value


def _utc(value: datetime, *, name: str) -> datetime:
    return _aware(value, name=name).astimezone(UTC)


def to_kst_text(value: datetime) -> str:
    """Serialize an aware instant as offset-bearing KST ISO 8601 text."""
    return _aware(value, name="timestamp").astimezone(KST).isoformat()


def from_kst_text(value: str) -> datetime:
    """Parse the strict offset-bearing KST representation used by persistence."""
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise InvariantViolation("KST timestamp must be valid ISO 8601 text") from error
    _aware(parsed, name="KST timestamp")
    if parsed.utcoffset() != timedelta(hours=9):
        raise InvariantViolation("KST timestamp must carry the +09:00 offset")
    return parsed.astimezone(KST)


class Clock(ABC):
    """A single injectable timeline for timestamping and deterministic waiting."""

    @abstractmethod
    def now_utc(self) -> datetime:
        """Return the current aware UTC instant."""

    def now_kst(self) -> datetime:
        """Return the current instant represented in canonical KST."""
        return _utc(self.now_utc(), name="Clock.now_utc() result").astimezone(KST)

    @abstractmethod
    async def sleep_until(self, target: datetime) -> None:
        """Wait until an aware target, returning immediately for past targets."""

    async def sleep_for(self, delta: timedelta) -> None:
        """Wait relative to this clock's current timeline."""
        await self.sleep_until(self.now_utc() + delta)


class SystemClock(Clock):
    """Live wall clock; the sole production boundary for direct time and sleep."""

    def now_utc(self) -> datetime:
        """Return the operating system wall clock in UTC."""
        return datetime.now(UTC)

    async def sleep_until(self, target: datetime) -> None:
        """Sleep for the positive remaining wall-clock duration."""
        target_utc = _utc(target, name="sleep target")
        delay = (target_utc - self.now_utc()).total_seconds()
        if delay > 0:
            await asyncio.sleep(delay)


class SimClock(Clock):
    """Monotonic explicitly advanced clock for tests and time-compressed replay."""

    def __init__(self, start: datetime) -> None:
        self._now = _utc(start, name="simulation start")

    def now_utc(self) -> datetime:
        """Return the current simulated UTC instant."""
        return self._now

    def set_to(self, target: datetime) -> None:
        """Advance to an aware target without ever moving backward."""
        target_utc = _utc(target, name="simulation target")
        if target_utc < self._now:
            raise InvariantViolation("simulation clock cannot move backward")
        self._now = target_utc

    def advance(self, delta: timedelta) -> None:
        """Advance by a non-negative duration."""
        self.set_to(self._now + delta)

    async def sleep_until(self, target: datetime) -> None:
        """Advance immediately to a future target; past targets are no-ops."""
        target_utc = _utc(target, name="sleep target")
        self._now = max(self._now, target_utc)


__all__ = [
    "KST",
    "Clock",
    "SimClock",
    "SystemClock",
    "from_kst_text",
    "to_kst_text",
]
