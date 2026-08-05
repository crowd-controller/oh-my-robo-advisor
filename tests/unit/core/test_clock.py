from __future__ import annotations

import socket
from datetime import UTC, datetime, timedelta
from time import perf_counter

import pytest

from omra.core import clock as clock_module
from omra.core.clock import KST, Clock, SimClock, SystemClock
from omra.core.errors import InvariantViolation
from omra.core.money import KST as MONEY_KST

START = datetime(2026, 8, 5, tzinfo=UTC)
_ORIGINAL_SOCKET = socket.socket


@pytest.fixture(autouse=True)
def _allow_asyncio_self_pipe(_no_network: None, monkeypatch: pytest.MonkeyPatch) -> None:
    del _no_network

    def socket_for_asyncio_self_pipe(
        family: socket.AddressFamily = socket.AF_INET,
        kind: socket.SocketKind = socket.SOCK_STREAM,
        proto: int = 0,
        fileno: int | None = None,
    ) -> socket.socket:
        if fileno is not None and family == socket.AF_UNIX:
            return _ORIGINAL_SOCKET(family, kind, proto, fileno)
        raise RuntimeError("네트워크 차단 — 카세트를 쓰거나 record 마커를 붙여라 (설계 16 §11.2)")

    monkeypatch.setattr(socket, "socket", socket_for_asyncio_self_pipe)


def test_clock_abstract_surface_is_exact() -> None:
    assert Clock.__abstractmethods__ == frozenset({"now_utc", "sleep_until"})


def test_clock_module_public_exports_are_exact() -> None:
    assert clock_module.__all__ == ["Clock", "KST", "SimClock", "SystemClock"]


def test_money_reexports_the_canonical_kst() -> None:
    assert MONEY_KST is KST


def test_sim_clock_normalizes_aware_start_to_utc() -> None:
    clock = SimClock(datetime(2026, 8, 5, 9, 0, tzinfo=KST))
    assert clock.now_utc() == datetime(2026, 8, 5, 0, 0, tzinfo=UTC)
    assert clock.now_utc().tzinfo is UTC


def test_sim_clock_rejects_naive_start() -> None:
    with pytest.raises(InvariantViolation):
        SimClock(datetime(2026, 8, 5))


def test_sim_clock_rejects_naive_set_target() -> None:
    clock = SimClock(START)
    with pytest.raises(InvariantViolation):
        clock.set_to(datetime(2026, 8, 6))


@pytest.mark.asyncio
async def test_sim_clock_rejects_naive_sleep_target() -> None:
    clock = SimClock(START)
    with pytest.raises(InvariantViolation):
        await clock.sleep_until(datetime(2026, 8, 6))


def test_sim_clock_rejects_backward_set() -> None:
    clock = SimClock(START)
    with pytest.raises(InvariantViolation):
        clock.set_to(START - timedelta(microseconds=1))


def test_sim_clock_rejects_negative_advance() -> None:
    clock = SimClock(START)
    with pytest.raises(InvariantViolation):
        clock.advance(timedelta(microseconds=-1))


def test_sim_clock_advance_accumulates_exactly() -> None:
    clock = SimClock(START)
    clock.advance(timedelta(minutes=30))
    clock.advance(timedelta(seconds=45))
    assert clock.now_utc() == datetime(2026, 8, 5, 0, 30, 45, tzinfo=UTC)


@pytest.mark.parametrize(
    "target",
    [START, START - timedelta(days=1)],
)
@pytest.mark.asyncio
async def test_sim_clock_nonfuture_sleep_does_not_rewind(target: datetime) -> None:
    clock = SimClock(START)
    await clock.sleep_until(target)
    assert clock.now_utc() == START


@pytest.mark.asyncio
async def test_sim_clock_future_sleep_advances_without_wall_wait() -> None:
    clock = SimClock(START)
    target = datetime(2036, 8, 5, tzinfo=UTC)
    wall_start = perf_counter()
    await clock.sleep_until(target)
    assert perf_counter() - wall_start < 0.1
    assert clock.now_utc() == target


@pytest.mark.asyncio
async def test_sleep_for_uses_the_same_clock_timeline() -> None:
    clock = SimClock(START)
    await clock.sleep_for(timedelta(hours=2, seconds=3))
    assert clock.now_utc() == datetime(2026, 8, 5, 2, 0, 3, tzinfo=UTC)


def test_system_clock_now_utc_is_current_aware_utc() -> None:
    clock = SystemClock()
    before = datetime.now(UTC)
    observed = clock.now_utc()
    after = datetime.now(UTC)
    assert before <= observed <= after
    assert observed.tzinfo is UTC


def test_system_clock_now_kst_has_fixed_nine_hour_offset() -> None:
    observed = SystemClock().now_kst()
    assert observed.tzinfo is KST
    assert observed.utcoffset() == timedelta(hours=9)


@pytest.mark.asyncio
async def test_system_clock_rejects_naive_sleep_target() -> None:
    with pytest.raises(InvariantViolation):
        await SystemClock().sleep_until(datetime(2026, 8, 5))


@pytest.mark.asyncio
async def test_system_clock_really_waits_for_future_deadline() -> None:
    clock = SystemClock()
    deadline = clock.now_utc() + timedelta(milliseconds=30)
    await clock.sleep_until(deadline)
    assert clock.now_utc() >= deadline


@pytest.mark.asyncio
async def test_system_clock_past_sleep_returns_immediately() -> None:
    clock = SystemClock()
    wall_start = perf_counter()
    await clock.sleep_until(clock.now_utc() - timedelta(days=1))
    assert perf_counter() - wall_start < 0.1
