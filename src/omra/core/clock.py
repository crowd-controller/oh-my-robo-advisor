"""결정론적 시간축 추상화."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from datetime import UTC, datetime, timedelta
from typing import Final
from zoneinfo import ZoneInfo

from omra.core.errors import InvariantViolation

__all__ = ["Clock", "KST", "SimClock", "SystemClock"]  # noqa: RUF022

KST: Final[ZoneInfo] = ZoneInfo("Asia/Seoul")


def _require_aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise InvariantViolation("naive datetime 은 Clock 시간축에 들어올 수 없다")
    return value


class Clock(ABC):
    @abstractmethod
    def now_utc(self) -> datetime:
        raise NotImplementedError

    def now_kst(self) -> datetime:
        return _require_aware(self.now_utc()).astimezone(KST)

    @abstractmethod
    async def sleep_until(self, t: datetime) -> None:
        raise NotImplementedError

    async def sleep_for(self, delta: timedelta) -> None:
        await self.sleep_until(self.now_utc() + delta)


class SystemClock(Clock):
    def now_utc(self) -> datetime:
        return datetime.now(UTC)

    async def sleep_until(self, t: datetime) -> None:
        target = _require_aware(t).astimezone(UTC)
        delay = (target - self.now_utc()).total_seconds()
        if delay > 0:
            await asyncio.sleep(delay)


class SimClock(Clock):
    def __init__(self, start: datetime) -> None:
        self._current = _require_aware(start).astimezone(UTC)

    def now_utc(self) -> datetime:
        return self._current

    def set_to(self, t: datetime) -> None:
        target = _require_aware(t).astimezone(UTC)
        if target < self._current:
            raise InvariantViolation("SimClock 시각은 뒤로 이동할 수 없다")
        self._current = target

    def advance(self, delta: timedelta) -> None:
        self.set_to(self._current + delta)

    async def sleep_until(self, t: datetime) -> None:
        target = _require_aware(t).astimezone(UTC)
        if target > self._current:
            self.set_to(target)
