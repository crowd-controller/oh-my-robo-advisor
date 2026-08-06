"""`core.models` 2차 — 주문 상태 전이표 계약.

검증 항목: 설계 02 §7.1 [DD-02-5·18], 진행표 S03-3.
"""

from __future__ import annotations

from itertools import product

import pytest

from omra.core import models
from omra.core.errors import TransitionError
from omra.core.models import OrderStatus, assert_transition

_ALLOWED_TRANSITIONS = frozenset(
    {
        (OrderStatus.SUBMITTING, OrderStatus.PENDING),
        (OrderStatus.SUBMITTING, OrderStatus.REJECTED),
        (OrderStatus.SUBMITTING, OrderStatus.EXPIRED_UNKNOWN),
        (OrderStatus.PENDING, OrderStatus.PARTIALLY_FILLED),
        (OrderStatus.PENDING, OrderStatus.FILLED),
        (OrderStatus.PENDING, OrderStatus.CANCELLED),
        (OrderStatus.PENDING, OrderStatus.EXPIRED),
        (OrderStatus.PARTIALLY_FILLED, OrderStatus.FILLED),
        (OrderStatus.PARTIALLY_FILLED, OrderStatus.CANCELLED),
        (OrderStatus.PARTIALLY_FILLED, OrderStatus.EXPIRED),
        (OrderStatus.EXPIRED_UNKNOWN, OrderStatus.PENDING),
        (OrderStatus.EXPIRED_UNKNOWN, OrderStatus.CANCELLED),
    }
)


@pytest.mark.parametrize(("current", "new"), tuple(product(OrderStatus, repeat=2)))
def test_transition_matrix_allows_exactly_the_canonical_edges_and_idempotency(
    current: OrderStatus,
    new: OrderStatus,
) -> None:
    if current == new or (current, new) in _ALLOWED_TRANSITIONS:
        assert_transition(current, new)
    else:
        with pytest.raises(TransitionError) as exc_info:
            assert_transition(current, new)
        assert exc_info.value.context == {"current": current.value, "new": new.value}


def test_terminal_statuses_are_the_exact_four_canonical_values() -> None:
    assert (
        frozenset(
            {
                OrderStatus.FILLED,
                OrderStatus.CANCELLED,
                OrderStatus.REJECTED,
                OrderStatus.EXPIRED,
            }
        )
        == models._TERMINAL
    )
