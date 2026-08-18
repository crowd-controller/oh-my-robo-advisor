"""Pure configuration-layer loading and precedence primitives."""

from __future__ import annotations

import copy
import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

import yaml
from yaml.constructor import ConstructorError
from yaml.resolver import BaseResolver

from omra.config.errors import (
    ConfigConflictError,
    ConfigSyntaxError,
    ConfigTypeConflict,
    ConfigValidationError,
    UnknownOverrideError,
    Violation,
)
from omra.config.schema.run import ExecEnv

if TYPE_CHECKING:
    from pathlib import Path

    from yaml.nodes import MappingNode

_ENV_PREFIX = "OMRA__"
_DEFAULT_SHAPE: Mapping[str, object] = {"run": {"env": ExecEnv.DRY_RUN.value}}
_MISSING = object()


class _UniqueKeyLoader(yaml.SafeLoader):
    """SafeLoader variant that rejects duplicate and non-string mapping keys."""


def _construct_unique_mapping(
    loader: _UniqueKeyLoader,
    node: MappingNode,
    *,
    deep: bool = False,
) -> dict[str, object]:
    loader.flatten_mapping(node)
    result: dict[str, object] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if not isinstance(key, str):
            raise ConstructorError(
                "while constructing a configuration mapping",
                node.start_mark,
                "configuration keys must be strings",
                key_node.start_mark,
            )
        if key in result:
            raise ConstructorError(
                "while constructing a configuration mapping",
                node.start_mark,
                f"duplicate key {key!r}",
                key_node.start_mark,
            )
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


_UniqueKeyLoader.add_constructor(BaseResolver.DEFAULT_MAPPING_TAG, _construct_unique_mapping)


@dataclass(frozen=True, slots=True)
class Override:
    """One normalized OMRA__ environment override."""

    variable: str
    path: tuple[str, ...]
    value: object


@dataclass(frozen=True, slots=True)
class LoadedLayer:
    """One file that participated in the effective scalar configuration."""

    kind: str
    path: Path


@dataclass(frozen=True, slots=True)
class LayeredMapping:
    """Result of the two-pass environment selection and scalar merge."""

    env: ExecEnv
    values: Mapping[str, object]
    sources: tuple[LoadedLayer, ...]


def _path(parent: str, child: str) -> str:
    return child if not parent else f"{parent}.{child}"


def _copy_mapping(value: Mapping[str, object]) -> dict[str, object]:
    return {key: copy.deepcopy(item) for key, item in value.items()}


def deep_merge(
    base: Mapping[str, object],
    overlay: Mapping[str, object],
    *,
    path: str = "",
) -> dict[str, object]:
    """Recursively merge mappings while replacing lists and scalar values.

    A mapping may only be overlaid by another mapping. This rejects accidental
    structural changes instead of silently discarding a subtree.
    """
    merged = _copy_mapping(base)
    for key, overlay_value in overlay.items():
        current_path = _path(path, key)
        if key not in merged:
            merged[key] = copy.deepcopy(overlay_value)
            continue

        base_value = merged[key]
        base_is_mapping = isinstance(base_value, Mapping)
        overlay_is_mapping = isinstance(overlay_value, Mapping)
        if base_is_mapping:
            if not overlay_is_mapping:
                raise ConfigTypeConflict(current_path, type(base_value), type(overlay_value))
            merged[key] = deep_merge(
                cast("Mapping[str, object]", base_value),
                cast("Mapping[str, object]", overlay_value),
                path=current_path,
            )
        else:
            merged[key] = copy.deepcopy(overlay_value)
    return merged


def parse_yaml_mapping(raw: bytes, *, source: Path) -> dict[str, object]:
    """Parse one UTF-8 YAML mapping using the canonical duplicate-key rules."""
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ConfigSyntaxError(source, "configuration file is not valid UTF-8") from error

    try:
        document = yaml.load(text, Loader=_UniqueKeyLoader)  # noqa: S506
    except yaml.MarkedYAMLError as error:
        mark = error.problem_mark
        raise ConfigSyntaxError(
            source,
            error.problem or str(error),
            line=None if mark is None else mark.line + 1,
            column=None if mark is None else mark.column + 1,
        ) from error

    if document is None:
        return {}
    if not isinstance(document, Mapping):
        raise ConfigValidationError(
            (
                Violation(
                    code="invalid_root",
                    message=f"expected a mapping, got {type(document).__name__}",
                    source=source,
                    line=1,
                    column=1,
                ),
            )
        )
    return _copy_mapping(cast("Mapping[str, object]", document))


def load_yaml_mapping(path: Path) -> dict[str, object]:
    """Load a UTF-8 YAML mapping and retain actionable parser locations."""
    try:
        raw = path.read_bytes()
    except OSError as error:
        raise ConfigValidationError(
            (
                Violation(
                    code="file_unreadable",
                    message=str(error),
                    source=path,
                ),
            )
        ) from error
    return parse_yaml_mapping(raw, source=path)


def _reject_json_constant(value: str) -> None:
    msg = f"non-standard JSON constant {value}"
    raise ValueError(msg)


def parse_override_value(raw: str) -> object:
    """Parse an override as strict JSON first, then fall back to a string."""
    try:
        return json.loads(raw, parse_constant=_reject_json_constant)
    except (json.JSONDecodeError, ValueError):
        return raw


def parse_env_overrides(environ: Mapping[str, str] | None = None) -> tuple[Override, ...]:
    """Normalize all OMRA__ variables deterministically."""
    source = os.environ if environ is None else environ
    overrides: list[Override] = []
    seen: dict[tuple[str, ...], str] = {}
    for variable in sorted(source):
        if not variable.startswith(_ENV_PREFIX):
            continue
        suffix = variable.removeprefix(_ENV_PREFIX)
        parts = tuple(part.lower() for part in suffix.split("__"))
        if not parts or any(not part for part in parts):
            raise UnknownOverrideError(parts, variable=variable)
        previous = seen.get(parts)
        if previous is not None:
            dotted = ".".join(parts)
            raise ConfigConflictError(
                f"environment variables {previous} and {variable} both target {dotted}"
            )
        seen[parts] = variable
        overrides.append(
            Override(variable=variable, path=parts, value=parse_override_value(source[variable]))
        )
    return tuple(overrides)


def _lookup(values: Mapping[str, object], path: tuple[str, ...]) -> object:
    current: object = values
    for part in path:
        if not isinstance(current, Mapping) or part not in current:
            return _MISSING
        current = current[part]
    return current


def _set_known_path(
    values: dict[str, object],
    known_shape: Mapping[str, object],
    override: Override,
) -> None:
    if _lookup(known_shape, override.path) is _MISSING:
        raise UnknownOverrideError(override.path, variable=override.variable)

    target = values
    shape: object = known_shape
    for part in override.path[:-1]:
        if not isinstance(shape, Mapping):
            raise UnknownOverrideError(override.path, variable=override.variable)
        shape = shape[part]
        existing = target.get(part, _MISSING)
        if existing is _MISSING and isinstance(shape, Mapping):
            child: dict[str, object] = {}
            target[part] = child
            target = child
        elif isinstance(existing, Mapping):
            copied = _copy_mapping(cast("Mapping[str, object]", existing))
            target[part] = copied
            target = copied
        else:
            raise ConfigTypeConflict(".".join(override.path[:-1]), type(existing), dict)
    target[override.path[-1]] = copy.deepcopy(override.value)


def apply_overrides(
    values: Mapping[str, object],
    overrides: tuple[Override, ...],
    *,
    known_shape: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Apply normalized overrides after checking every path against a shape."""
    shape = values if known_shape is None else known_shape
    result = _copy_mapping(values)
    for override in overrides:
        _set_known_path(result, shape, override)
    return result


def _invalid_exec_env(value: object, origin: str) -> ConfigValidationError:
    return ConfigValidationError(
        (
            Violation(
                code="invalid_exec_env",
                path="run.env",
                message=f"{origin} supplied {value!r}; expected dry_run, paper, or live",
            ),
        )
    )


def resolve_exec_env(
    base: Mapping[str, object],
    *,
    environ: Mapping[str, str] | None = None,
    cli_overrides: Mapping[str, object] | None = None,
) -> ExecEnv:
    """Resolve the bootstrap environment using CLI > env > base > default."""
    candidates: list[tuple[str, object]] = []
    if cli_overrides is not None:
        cli_value = _lookup(cli_overrides, ("run", "env"))
        if cli_value is not _MISSING:
            candidates.append(("CLI", cli_value))

    for override in parse_env_overrides(environ):
        if override.path == ("run", "env"):
            candidates.append((override.variable, override.value))
            break

    base_value = _lookup(base, ("run", "env"))
    if base_value is not _MISSING:
        candidates.append(("config.yaml", base_value))
    candidates.append(("code default", ExecEnv.DRY_RUN.value))

    origin, value = candidates[0]
    if not isinstance(value, (str, ExecEnv)):
        raise _invalid_exec_env(value, origin)
    try:
        return ExecEnv(value)
    except ValueError as error:
        raise _invalid_exec_env(value, origin) from error


def _overlay_for(config_dir: Path, env: ExecEnv) -> Path | None:
    forbidden = config_dir / "config.dry_run.yaml"
    if forbidden.exists():
        raise ConfigConflictError(f"{forbidden} is forbidden; dry_run uses config.yaml only")
    if env is ExecEnv.DRY_RUN:
        return None
    return config_dir / f"config.{env.value}.yaml"


def load_layered_mapping(
    config_dir: Path,
    *,
    environ: Mapping[str, str] | None = None,
    cli_overrides: Mapping[str, object] | None = None,
    known_shape: Mapping[str, object] | None = None,
) -> LayeredMapping:
    """Load base and environment overlay, then apply env and CLI precedence."""
    base_path = config_dir / "config.yaml"
    base = load_yaml_mapping(base_path)
    env = resolve_exec_env(base, environ=environ, cli_overrides=cli_overrides)
    values = base
    sources = [LoadedLayer(kind="base", path=base_path)]

    overlay_path = _overlay_for(config_dir, env)
    if overlay_path is not None:
        overlay = load_yaml_mapping(overlay_path)
        declared_env = _lookup(overlay, ("run", "env"))
        if declared_env is not _MISSING and declared_env != env.value:
            raise ConfigConflictError(
                f"{overlay_path} declares run.env={declared_env!r}, expected {env.value!r}"
            )
        values = deep_merge(values, overlay)
        sources.append(LoadedLayer(kind="overlay", path=overlay_path))

    shape = deep_merge(_DEFAULT_SHAPE, values)
    if known_shape is not None:
        shape = deep_merge(shape, known_shape)
    values = apply_overrides(values, parse_env_overrides(environ), known_shape=shape)
    if cli_overrides is not None:
        values = deep_merge(values, cli_overrides)
    return LayeredMapping(env=env, values=values, sources=tuple(sources))
