"""Structural contracts for the complete scalar AppConfig tree."""

from decimal import Decimal
from types import ModuleType
from typing import Annotated, get_args, get_origin

import pytest
from pydantic import BaseModel, ValidationError

from omra.config import AppConfig
from omra.config.schema import accounts as accounts_schema
from omra.config.schema import engine, execution, improve, observe, ops, policy, protections, taxcfg
from omra.config.schema import run as run_schema
from omra.core import AccountMode, AccountType, Broker, Dec

ROOT_FIELDS = (
    "run",
    "accounts",
    "risk",
    "core",
    "satellite",
    "cash",
    "bl",
    "mvo",
    "cov",
    "sanity",
    "band",
    "rebalance",
    "universe",
    "trade",
    "momentum",
    "crypto",
    "mc",
    "gk",
    "backtest",
    "order",
    "execution",
    "etf",
    "tax",
    "waterfall",
    "protections",
    "safe_mode",
    "presence",
    "tracking_error",
    "alerts",
    "ws",
    "quote",
    "fx",
    "guard",
    "realtime",
    "surveillance",
    "research",
    "labs",
    "policy",
    "canary",
    "data",
    "watchdog",
    "runtime",
    "tools",
    "web",
    "secrets",
    "jobs",
    "monitoring",
)

_SCHEMA_MODULES: tuple[ModuleType, ...] = (
    accounts_schema,
    engine,
    execution,
    improve,
    observe,
    ops,
    policy,
    protections,
    run_schema,
    taxcfg,
)


def minimal_app_config_payload() -> dict[str, object]:
    """Return every required root with only intentionally required nested keys."""
    values: dict[str, object] = {name: {} for name in ROOT_FIELDS}
    values["accounts"] = []
    values["backtest"] = {"snapshot": {}}
    return values


def _assert_error(
    error: ValidationError,
    *,
    error_type: str,
    location_suffix: tuple[str | int, ...],
) -> None:
    assert any(
        item["type"] == error_type
        and tuple(item["loc"])[-len(location_suffix) :] == location_suffix
        for item in error.errors()
    )


def _model_types(annotation: object) -> set[type[BaseModel]]:
    models: set[type[BaseModel]] = set()
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        models.add(annotation)
    for argument in get_args(annotation):
        models.update(_model_types(argument))
    return models


def _schema_models() -> set[type[BaseModel]]:
    models: set[type[BaseModel]] = {AppConfig}
    for module in _SCHEMA_MODULES:
        models.update(
            value
            for value in vars(module).values()
            if isinstance(value, type)
            and issubclass(value, BaseModel)
            and value.__module__ == module.__name__
            and not value.__name__.startswith("_")
        )
    return models


_DEC_FLOAT_GUARD = get_args(Dec)[1]


def _assert_decimal_is_float_guarded(
    annotation: object,
    metadata: tuple[object, ...] = (),
) -> int:
    if annotation is Decimal:
        assert _DEC_FLOAT_GUARD in metadata
        return 1
    if get_origin(annotation) is Annotated:
        nested, *nested_metadata = get_args(annotation)
        return _assert_decimal_is_float_guarded(nested, tuple(nested_metadata))
    return sum(_assert_decimal_is_float_guarded(argument) for argument in get_args(annotation))


def test_app_config_root_is_the_exact_canonical_union() -> None:
    assert tuple(AppConfig.model_fields) == ROOT_FIELDS
    assert "glide" not in AppConfig.model_fields


def test_minimal_complete_payload_materializes_every_root() -> None:
    config = AppConfig.model_validate(minimal_app_config_payload())

    assert tuple(config.model_dump()) == ROOT_FIELDS
    assert config.accounts == ()
    assert config.backtest.snapshot.tolerance_pct is None


def test_every_schema_model_is_frozen_and_forbids_extra_fields() -> None:
    declared_models = _schema_models()

    models: set[type[BaseModel]] = {AppConfig}
    pending: list[type[BaseModel]] = [AppConfig]
    while pending:
        model = pending.pop()
        for field in model.model_fields.values():
            for nested_model in _model_types(field.annotation):
                if nested_model not in models:
                    models.add(nested_model)
                    pending.append(nested_model)

    assert models == declared_models
    assert all(model.model_config.get("frozen") is True for model in models)
    assert all(model.model_config.get("extra") == "forbid" for model in models)


def test_every_decimal_schema_boundary_reuses_core_float_guard() -> None:
    decimal_annotations = 0
    for model in _schema_models():
        for field in model.model_fields.values():
            decimal_annotations += _assert_decimal_is_float_guarded(
                field.annotation,
                tuple(field.metadata),
            )

    assert decimal_annotations > 0


def test_unknown_root_is_rejected_with_its_exact_path() -> None:
    values = minimal_app_config_payload()
    values["glide"] = {"floor_level": 3}

    with pytest.raises(ValidationError) as raised:
        AppConfig.model_validate(values)

    _assert_error(raised.value, error_type="extra_forbidden", location_suffix=("glide",))


@pytest.mark.parametrize("root", ROOT_FIELDS)
def test_unknown_key_is_rejected_in_every_root_block(root: str) -> None:
    values = minimal_app_config_payload()
    if root == "accounts":
        values[root] = [
            {
                "id": "general_01",
                "type": "general",
                "broker": "KIS",
                "mode": "AUTO",
                "__typo__": True,
            }
        ]
        suffix: tuple[str | int, ...] = (root, 0, "__typo__")
    elif root == "backtest":
        values[root] = {"snapshot": {}, "__typo__": True}
        suffix = (root, "__typo__")
    else:
        values[root] = {"__typo__": True}
        suffix = (root, "__typo__")

    with pytest.raises(ValidationError) as raised:
        AppConfig.model_validate(values)

    _assert_error(raised.value, error_type="extra_forbidden", location_suffix=suffix)


def test_missing_root_and_backtest_snapshot_are_distinct_required_errors() -> None:
    missing_root = minimal_app_config_payload()
    missing_root.pop("run")
    missing_snapshot = minimal_app_config_payload()
    missing_snapshot["backtest"] = {}

    with pytest.raises(ValidationError) as root_error:
        AppConfig.model_validate(missing_root)
    with pytest.raises(ValidationError) as snapshot_error:
        AppConfig.model_validate(missing_snapshot)

    _assert_error(root_error.value, error_type="missing", location_suffix=("run",))
    _assert_error(
        snapshot_error.value,
        error_type="missing",
        location_suffix=("backtest", "snapshot"),
    )


def test_decimal_float_is_rejected_at_a_nested_app_config_boundary() -> None:
    values = minimal_app_config_payload()
    values["core"] = {"min_weight": 0.8}

    with pytest.raises(ValidationError, match="float input is forbidden"):
        AppConfig.model_validate(values)


@pytest.mark.parametrize(
    ("root", "value", "path"),
    [
        ("guard", {"oneway": False}, ("guard", "oneway")),
        (
            "surveillance",
            {"sources": {"candidate": {"enabled": True, "grade": "unofficial"}}},
            ("surveillance", "sources", "candidate", "grade"),
        ),
    ],
)
def test_type_locked_safety_invariants_cannot_be_disabled(
    root: str,
    value: object,
    path: tuple[str | int, ...],
) -> None:
    values = minimal_app_config_payload()
    values[root] = value

    with pytest.raises(ValidationError) as raised:
        AppConfig.model_validate(values)

    assert any(tuple(item["loc"]) == path for item in raised.value.errors())


@pytest.mark.parametrize(
    ("field", "value"),
    [("crypto", "8:55"), ("krx", "24:00"), ("us_loc", "PT30M")],
)
def test_presence_grace_caps_reject_ambiguous_time_formats(field: str, value: str) -> None:
    values = minimal_app_config_payload()
    values["presence"] = {"grace_cap_kst": {field: value}}

    with pytest.raises(ValidationError) as raised:
        AppConfig.model_validate(values)

    assert any(tuple(item["loc"])[-1] == field for item in raised.value.errors())


def test_account_config_reuses_core_vocabulary_and_projects_without_credentials() -> None:
    values = minimal_app_config_payload()
    values["accounts"] = [
        {
            "id": "pension_savings",
            "type": "pension",
            "broker": "KIS",
            "mode": "BROKER_SCHEDULED",
            "enabled": True,
            "forbidden_asset_classes": ["crypto"],
        }
    ]

    account = AppConfig.model_validate(values).accounts[0]
    domain = account.to_domain()

    assert domain.id == "pension_savings"
    assert domain.type is AccountType.PENSION
    assert domain.broker is Broker.KIS
    assert domain.mode is AccountMode.BROKER_SCHEDULED
    assert tuple(type(domain).model_fields) == ("id", "type", "broker", "mode")


def test_app_config_and_nested_models_reject_mutation() -> None:
    config = AppConfig.model_validate(minimal_app_config_payload())
    root_field = "risk"
    nested_field = "level"

    with pytest.raises(ValidationError, match="frozen"):
        setattr(config, root_field, config.risk)
    with pytest.raises(ValidationError, match="frozen"):
        setattr(config.risk, nested_field, 7)
