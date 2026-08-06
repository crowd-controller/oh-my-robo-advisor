"""`core.models` 3차 — Order·Fill 모델 계약.

검증 항목: 설계 02 §7.3 [DD-02-5], 진행표 S03-4.
"""

from __future__ import annotations

import ast
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from omra.core.errors import InvariantViolation, LotStepError, TickRuleError, TransitionError
from omra.core.ids import Market
from omra.core.models import (
    Fill,
    Instrument,
    Order,
    OrderIntent,
    OrderSide,
    OrderStatus,
    OrderType,
)
from omra.core.tick import TickRuleId
from tests.arch import astutil


@pytest.fixture
def krx_instrument() -> Instrument:
    return Instrument(
        symbol="069500",
        market=Market.KRX,
        currency="KRW",
        asset_class="kr_etf_equity",
        lot_step=Decimal("1"),
        tick_rule=TickRuleId.KRX_ETF_5,
    )


def _order(instrument: Instrument, **updates: object) -> Order:
    values: dict[str, object] = {
        "id": "01ORDER",
        "account_id": "kis_domestic_taxable",
        "instrument": instrument,
        "side": OrderSide.BUY,
        "order_type": OrderType.LIMIT,
        "intent": OrderIntent.BAND_RESTORE,
        "qty": Decimal("3"),
        "limit_price": Decimal("10000"),
        "dry_run": True,
    }
    values.update(updates)
    return Order.model_validate(values)


def test_order_constructs_the_canonical_fields_with_submitting_default(
    krx_instrument: Instrument,
) -> None:
    order = _order(krx_instrument)

    assert order.status is OrderStatus.SUBMITTING
    assert order.broker_order_id is None
    assert order.broker_order_org_no is None
    assert order.orig_broker_order_id is None
    assert order.plan_id is None
    assert order.reprice_count == 0
    assert order.submitted_at_kst is None
    assert list(type(order).model_fields) == [
        "id",
        "account_id",
        "broker_order_id",
        "broker_order_org_no",
        "orig_broker_order_id",
        "instrument",
        "side",
        "order_type",
        "intent",
        "qty",
        "limit_price",
        "status",
        "plan_id",
        "reprice_count",
        "submitted_at_kst",
        "dry_run",
    ]


@pytest.mark.parametrize(
    "bad_qty",
    [
        Decimal("0"),
        Decimal("-1"),
        Decimal("1.5"),
    ],
)
def test_order_rejects_nonpositive_or_off_lot_grid_quantity(
    krx_instrument: Instrument,
    bad_qty: Decimal,
) -> None:
    with pytest.raises(LotStepError):
        _order(krx_instrument, qty=bad_qty)


@pytest.mark.parametrize("nonfinite", [Decimal("NaN"), Decimal("Infinity")])
def test_order_rejects_nonfinite_quantity(
    krx_instrument: Instrument,
    nonfinite: Decimal,
) -> None:
    with pytest.raises(ValidationError):
        _order(krx_instrument, qty=nonfinite)


@pytest.mark.parametrize("order_type", [OrderType.LIMIT, OrderType.LOO, OrderType.LOC])
def test_price_bearing_order_types_require_an_aligned_limit_price(
    krx_instrument: Instrument,
    order_type: OrderType,
) -> None:
    with pytest.raises(TickRuleError):
        _order(krx_instrument, order_type=order_type, limit_price=None)
    with pytest.raises(TickRuleError):
        _order(krx_instrument, order_type=order_type, limit_price=Decimal("10001"))

    assert _order(
        krx_instrument,
        order_type=order_type,
        limit_price=Decimal("10005"),
    ).limit_price == Decimal("10005")


@pytest.mark.parametrize("order_type", [OrderType.MARKET, OrderType.MOO, OrderType.MOC])
def test_non_price_order_types_forbid_limit_price(
    krx_instrument: Instrument,
    order_type: OrderType,
) -> None:
    with pytest.raises(TickRuleError):
        _order(krx_instrument, order_type=order_type, limit_price=Decimal("10000"))

    assert _order(krx_instrument, order_type=order_type, limit_price=None).limit_price is None


def test_order_status_changes_only_through_transition_to(
    krx_instrument: Instrument,
) -> None:
    order = _order(krx_instrument)

    with pytest.raises(InvariantViolation):
        order.status = OrderStatus.PENDING
    assert order.status is OrderStatus.SUBMITTING

    order.transition_to(OrderStatus.PENDING)
    assert order.model_dump(mode="json")["status"] == "PENDING"
    order.transition_to(OrderStatus.PENDING)
    assert isinstance(order.status, OrderStatus)
    assert "status" in order.model_dump(exclude_unset=True)

    with pytest.raises(InvariantViolation):
        order.transition_to("FILLED")  # type: ignore[arg-type]

    with pytest.raises(TransitionError):
        order.transition_to(OrderStatus.REJECTED)
    assert order.model_dump(mode="json")["status"] == "PENDING"


@pytest.mark.parametrize(
    ("field", "bad"),
    [
        ("qty", Decimal("0")),
        ("limit_price", None),
        ("order_type", OrderType.MARKET),
        ("submitted_at_kst", datetime(2026, 8, 6, 9, 0)),
    ],
)
def test_order_rejects_invalid_assignment_atomically(
    krx_instrument: Instrument,
    field: str,
    bad: object,
) -> None:
    order = _order(krx_instrument)
    before = order.model_dump()

    with pytest.raises((InvariantViolation, LotStepError, TickRuleError)):
        setattr(order, field, bad)

    assert order.model_dump() == before


def test_order_model_copy_cannot_bypass_validation_or_status_transition(
    krx_instrument: Instrument,
) -> None:
    order = _order(krx_instrument)

    with pytest.raises(InvariantViolation):
        order.model_copy(update={"status": OrderStatus.FILLED})
    with pytest.raises(LotStepError):
        order.model_copy(update={"qty": Decimal("0")})


def test_order_valid_assignment_and_copy_remain_supported(
    krx_instrument: Instrument,
) -> None:
    order = _order(krx_instrument)
    order.qty = Decimal("4")
    order.limit_price = Decimal("10005")
    order.submitted_at_kst = datetime(2026, 8, 6, 0, 0, tzinfo=UTC)

    market = order.model_copy(
        update={"order_type": OrderType.MARKET, "limit_price": None},
        deep=True,
    )

    assert order.qty == Decimal("4")
    assert order.limit_price == Decimal("10005")
    assert market.order_type is OrderType.MARKET
    assert market.limit_price is None
    assert market.instrument == order.instrument
    assert market.instrument is not order.instrument
    assert "submitted_at_kst" in order.model_dump(exclude_unset=True)
    assert "broker_order_id" not in market.model_dump(exclude_unset=True)


def _status_mutation_violations(modules: tuple[astutil.SourceModule, ...]) -> list[str]:
    violations: list[str] = []

    def is_low_level_container(container: ast.expr) -> bool:
        return (isinstance(container, ast.Attribute) and container.attr == "__dict__") or (
            isinstance(container, ast.Call) and astutil.call_qualname(container) == "vars"
        )

    def has_status_payload(args: list[ast.expr], keywords: list[ast.keyword]) -> bool:
        if any(keyword.arg == "status" for keyword in keywords):
            return True
        return any(
            isinstance(arg, ast.Dict)
            and any(isinstance(key, ast.Constant) and key.value == "status" for key in arg.keys)
            for arg in args
        )

    def mutates_status(target: ast.expr) -> bool:
        if isinstance(target, ast.Attribute):
            return target.attr == "status"
        if not isinstance(target, ast.Subscript):
            return False
        if not isinstance(target.slice, ast.Constant) or target.slice.value != "status":
            return False
        return is_low_level_container(target.value)

    def update_call_mutates_status(call: ast.Call) -> bool:
        func = call.func
        if not isinstance(func, ast.Attribute) or func.attr != "update":
            return False
        if not is_low_level_container(func.value):
            return False
        return has_status_payload(call.args, call.keywords)

    for module in modules:

        class Visitor(ast.NodeVisitor):
            def __init__(self, source_module: astutil.SourceModule) -> None:
                self.module = source_module
                self.scope: list[str] = []

            def _visit_scope(self, node: ast.AST, name: str) -> None:
                self.scope.append(name)
                self.generic_visit(node)
                self.scope.pop()

            def visit_ClassDef(self, node: ast.ClassDef) -> None:
                self._visit_scope(node, node.name)

            def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
                self._visit_scope(node, node.name)

            def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
                self._visit_scope(node, node.name)

            def _record_targets(self, node: ast.AST, targets: list[ast.expr]) -> None:
                if any(mutates_status(target) for target in targets):
                    violations.append(f"{self.module.path}:{getattr(node, 'lineno', 0)}")

            def visit_Assign(self, node: ast.Assign) -> None:
                self._record_targets(node, node.targets)
                self.generic_visit(node)

            def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
                self._record_targets(node, [node.target])
                self.generic_visit(node)

            def visit_AugAssign(self, node: ast.AugAssign) -> None:
                self._record_targets(node, [node.target])
                self.generic_visit(node)

            def visit_Call(self, node: ast.Call) -> None:
                qualname = astutil.call_qualname(node)
                owner = ".".join(self.scope)
                if qualname == "object.__setattr__":
                    allowed = self.module.dotted == "omra.core.models" and owner in {
                        "Order.__setattr__",
                        "Order.transition_to",
                    }
                    if not allowed:
                        violations.append(f"{self.module.path}:{node.lineno}")
                if qualname in {"BaseModel.model_copy", "BaseModel.__setattr__"}:
                    violations.append(f"{self.module.path}:{node.lineno}")
                if (
                    isinstance(node.func, ast.Attribute)
                    and node.func.attr == "model_copy"
                    and isinstance(node.func.value, ast.Call)
                    and astutil.call_qualname(node.func.value) == "super"
                ):
                    safe_super_copy = (
                        self.module.dotted == "omra.core.models"
                        and owner in {"Order.model_copy", "Fill.model_copy"}
                        and all(keyword.arg != "update" for keyword in node.keywords)
                    )
                    if not safe_super_copy:
                        violations.append(f"{self.module.path}:{node.lineno}")
                if isinstance(node.func, ast.Attribute) and node.func.attr == "model_construct":
                    violations.append(f"{self.module.path}:{node.lineno}")
                if (
                    qualname == "dict.__setitem__"
                    and len(node.args) >= 2
                    and isinstance(node.args[1], ast.Constant)
                    and node.args[1].value == "status"
                ):
                    violations.append(f"{self.module.path}:{node.lineno}")
                if (
                    qualname == "dict.update"
                    and node.args
                    and is_low_level_container(node.args[0])
                    and has_status_payload(node.args[1:], node.keywords)
                ):
                    violations.append(f"{self.module.path}:{node.lineno}")
                if update_call_mutates_status(node):
                    violations.append(f"{self.module.path}:{node.lineno}")
                self.generic_visit(node)

        Visitor(module).visit(module.tree)
    return violations


def test_source_never_assigns_order_status_directly() -> None:
    assert _status_mutation_violations(astutil.source_modules()) == []


def test_status_mutation_scanner_detects_low_level_bypasses() -> None:
    text = """
object.__setattr__(order, "status", new)
order.__dict__.update(status=new)
vars(order)["status"] = new
BaseModel.model_copy(order, update={"status": new})
BaseModel.__setattr__(order, "status", new)
super(Order, order).model_copy(update={"status": new})
Order.model_construct(status=new)
dict.__setitem__(order.__dict__, "status", new)
dict.update(order.__dict__, status=new)
"""
    module = astutil.SourceModule(
        path=astutil.SRC_ROOT / "sample.py",
        dotted="omra.sample",
        tree=ast.parse(text),
        text=text,
    )

    assert len(_status_mutation_violations((module,))) == 9


def test_order_rejects_naive_submitted_timestamp(krx_instrument: Instrument) -> None:
    with pytest.raises(InvariantViolation):
        _order(krx_instrument, submitted_at_kst=datetime(2026, 8, 6, 9, 0))

    aware = datetime(2026, 8, 6, 0, 0, tzinfo=UTC)
    assert _order(krx_instrument, submitted_at_kst=aware).submitted_at_kst == aware


def test_order_json_round_trip_preserves_domain_types(krx_instrument: Instrument) -> None:
    order = _order(
        krx_instrument,
        broker_order_id="12345",
        broker_order_org_no="67890",
        plan_id="01PLAN",
        submitted_at_kst=datetime(2026, 8, 6, 0, 0, tzinfo=UTC),
    )
    order.transition_to(OrderStatus.PENDING)

    assert Order.model_validate_json(order.model_dump_json()) == order


def _fill(**updates: object) -> Fill:
    values: dict[str, object] = {
        "id": "01FILL",
        "order_id": "01ORDER",
        "qty": Decimal("0.000000001"),
        "price": Decimal("10001"),
        "filled_at_kst": datetime(2026, 8, 6, 0, 0, tzinfo=UTC),
        "settle_date": date(2026, 8, 10),
    }
    values.update(updates)
    return Fill.model_validate(values)


def test_fill_is_frozen_and_preserves_broker_fact_price_without_tick_snapping() -> None:
    fill = _fill()

    assert fill.qty == Decimal("0.000000001")
    assert fill.price == Decimal("10001")
    assert fill.fee is None
    assert fill.tax is None
    assert fill.broker_exec_id is None
    with pytest.raises(ValidationError):
        fill.price = Decimal("10005")  # type: ignore[misc]  # deliberate frozen violation


@pytest.mark.parametrize(
    ("field", "bad"),
    [
        ("qty", Decimal("0")),
        ("qty", Decimal("-1")),
        ("price", Decimal("0")),
        ("price", Decimal("-1")),
    ],
)
def test_fill_rejects_nonpositive_quantity_and_price(field: str, bad: Decimal) -> None:
    with pytest.raises(InvariantViolation):
        _fill(**{field: bad})


@pytest.mark.parametrize(
    ("field", "nonfinite"),
    [("qty", Decimal("NaN")), ("price", Decimal("Infinity"))],
)
def test_fill_rejects_nonfinite_facts(field: str, nonfinite: Decimal) -> None:
    with pytest.raises(ValidationError):
        _fill(**{field: nonfinite})


def test_fill_rejects_naive_filled_timestamp() -> None:
    with pytest.raises(InvariantViolation):
        _fill(filled_at_kst=datetime(2026, 8, 6, 9, 0))


def test_fill_json_round_trip_preserves_domain_types() -> None:
    fill = _fill(
        fee=Decimal("1.25"),
        tax=Decimal("0.50"),
        broker_exec_id="exec-1",
    )

    assert Fill.model_validate_json(fill.model_dump_json()) == fill


@pytest.mark.parametrize(
    ("update", "error"),
    [
        ({"qty": Decimal("0")}, InvariantViolation),
        ({"price": Decimal("-1")}, InvariantViolation),
        ({"filled_at_kst": datetime(2026, 8, 6, 9, 0)}, InvariantViolation),
        ({"qty": 1.5}, ValidationError),
    ],
)
def test_fill_model_copy_cannot_bypass_frozen_fact_validation(
    update: dict[str, object],
    error: type[Exception],
) -> None:
    fill = _fill()

    with pytest.raises(error):
        fill.model_copy(update=update)


def test_fill_model_copy_supports_valid_deep_copy() -> None:
    fill = _fill()

    copied = fill.model_copy(update={"fee": Decimal("1.25")}, deep=True)

    assert copied.fee == Decimal("1.25")
    assert copied.qty == fill.qty
    assert "fee" in copied.model_dump(exclude_unset=True)
    assert "broker_exec_id" not in copied.model_dump(exclude_unset=True)
