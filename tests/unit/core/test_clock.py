"""Unit contracts for injectable live and simulated clocks."""

from datetime import UTC, datetime, timedelta
from time import perf_counter

import pytest

from omra.core import (
    KST,
    Clock,
    InvariantViolation,
    SimClock,
    SystemClock,
    from_kst_text,
    to_kst_text,
)
from omra.core.clock import KST as MODULE_KST
from omra.core.clock import Clock as ModuleClock
from omra.core.clock import SimClock as ModuleSimClock
from omra.core.clock import SystemClock as ModuleSystemClock
from omra.core.clock import from_kst_text as module_from_kst_text
from omra.core.clock import to_kst_text as module_to_kst_text


class _NaiveClock(Clock):
    def now_utc(self) -> datetime:
        return datetime(2026, 8, 19, 0, 0)

    async def sleep_until(self, target: datetime) -> None:
        return None


def test_clock_public_coordinates_are_stable() -> None:
    assert KST is MODULE_KST
    assert Clock is ModuleClock
    assert SimClock is ModuleSimClock
    assert SystemClock is ModuleSystemClock
    assert from_kst_text is module_from_kst_text
    assert to_kst_text is module_to_kst_text


def test_kst_text_normalizes_an_aware_instant_and_round_trips() -> None:
    source = datetime(2026, 8, 2, 1, 3, 11, 123456, tzinfo=UTC)

    rendered = to_kst_text(source)
    restored = from_kst_text(rendered)

    assert rendered == "2026-08-02T10:03:11.123456+09:00"
    assert restored == source
    assert restored.tzinfo is KST


def test_to_kst_text_rejects_naive_datetime() -> None:
    with pytest.raises(InvariantViolation, match="timezone-aware"):
        to_kst_text(datetime(2026, 8, 2, 10, 3, 11))


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ("not-a-timestamp", "valid ISO 8601"),
        ("2026-08-02T10:03:11", "timezone-aware"),
        ("2026-08-02T01:03:11+00:00", r"\+09:00"),
    ],
)
def test_from_kst_text_rejects_noncanonical_text(value: str, message: str) -> None:
    with pytest.raises(InvariantViolation, match=message):
        from_kst_text(value)


def test_system_clock_returns_aware_utc_and_kst_instants() -> None:
    clock = SystemClock()

    utc_now = clock.now_utc()
    kst_now = clock.now_kst()

    assert utc_now.tzinfo is UTC
    assert utc_now.utcoffset() == timedelta(0)
    assert kst_now.tzinfo is KST
    assert kst_now.utcoffset() == timedelta(hours=9)


async def test_system_clock_sleeps_only_for_a_positive_duration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = SystemClock()
    now = datetime(2026, 8, 19, tzinfo=UTC)
    delays: list[float] = []

    monkeypatch.setattr(clock, "now_utc", lambda: now)

    async def fake_sleep(delay: float) -> None:
        delays.append(delay)

    monkeypatch.setattr("omra.core.clock.asyncio.sleep", fake_sleep)

    await clock.sleep_until(now - timedelta(seconds=1))
    assert delays == []

    await clock.sleep_until(now + timedelta(seconds=2, microseconds=500000))
    assert delays == [2.5]


async def test_system_clock_rejects_naive_sleep_target() -> None:
    with pytest.raises(InvariantViolation, match="timezone-aware"):
        await SystemClock().sleep_until(datetime(2026, 8, 19))


def test_base_clock_rejects_a_naive_now_utc_result() -> None:
    with pytest.raises(InvariantViolation, match=r"Clock\.now_utc"):
        _NaiveClock().now_kst()


def test_sim_clock_normalizes_start_and_advances_exactly() -> None:
    start_kst = datetime(2026, 8, 19, 9, 0, tzinfo=KST)
    clock = SimClock(start_kst)

    assert clock.now_utc() == datetime(2026, 8, 19, 0, 0, tzinfo=UTC)

    clock.advance(timedelta(days=1, seconds=3, microseconds=5))

    assert clock.now_utc() == datetime(2026, 8, 20, 0, 0, 3, 5, tzinfo=UTC)


def test_sim_clock_rejects_naive_inputs_and_backward_movement() -> None:
    now = datetime(2026, 8, 19, tzinfo=UTC)

    with pytest.raises(InvariantViolation, match="timezone-aware"):
        SimClock(datetime(2026, 8, 19))

    clock = SimClock(now)
    with pytest.raises(InvariantViolation, match="timezone-aware"):
        clock.set_to(datetime(2026, 8, 20))
    with pytest.raises(InvariantViolation, match="backward"):
        clock.set_to(now - timedelta(microseconds=1))
    with pytest.raises(InvariantViolation, match="backward"):
        clock.advance(timedelta(microseconds=-1))


async def test_sim_clock_sleep_compresses_future_time_and_ignores_past() -> None:
    start = datetime(2026, 8, 19, tzinfo=UTC)
    future = start + timedelta(days=30)
    clock = SimClock(start)

    before = perf_counter()
    await clock.sleep_until(future)
    elapsed = perf_counter() - before

    assert elapsed < 0.5
    assert clock.now_utc() == future

    await clock.sleep_until(start)
    assert clock.now_utc() == future


async def test_sim_clock_sleep_for_uses_its_own_timeline() -> None:
    start = datetime(2026, 8, 19, tzinfo=UTC)
    clock = SimClock(start)

    await clock.sleep_for(timedelta(seconds=90))
    assert clock.now_utc() == start + timedelta(seconds=90)

    await clock.sleep_for(timedelta(seconds=-1))
    assert clock.now_utc() == start + timedelta(seconds=90)


async def test_sim_clock_rejects_naive_sleep_target() -> None:
    clock = SimClock(datetime(2026, 8, 19, tzinfo=UTC))

    with pytest.raises(InvariantViolation, match="timezone-aware"):
        await clock.sleep_until(datetime(2026, 8, 20))
