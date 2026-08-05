"""core 계층 계약 — 식별자와 계좌 비밀 경계.

검증 항목: 설계 01 §8.3, 설계 02 §3.1~§3.3
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tests.arch import astutil


def _module(dotted: str, text: str) -> astutil.SourceModule:
    return astutil.SourceModule(
        path=Path(*dotted.split(".")).with_suffix(".py"),
        dotted=dotted,
        tree=ast.parse(text),
        text=text,
    )


def _absolute_import_target(module: astutil.SourceModule, target: str) -> str:
    if not target.startswith("."):
        return target

    level = len(target) - len(target.lstrip("."))
    suffix = target[level:]
    base = module.dotted.split(".")[:-level]
    if suffix:
        base.extend(suffix.split("."))
    return ".".join(base)


def _format_import_site(site: astutil.ImportSite, absolute_target: str) -> str:
    return f"{site.module.dotted}:{site.lineno} → import {absolute_target}"


def _core_ids_aliases(module: astutil.SourceModule) -> set[str]:
    aliases: set[str] = set()
    for node in ast.walk(module.tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "omra.core.ids":
                    aliases.add(alias.asname or "omra.core.ids")
        elif isinstance(node, ast.ImportFrom):
            target_module = "." * node.level + (node.module or "")
            absolute_module = _absolute_import_target(module, target_module)
            if absolute_module == "omra.core":
                for alias in node.names:
                    if alias.name == "ids":
                        aliases.add(alias.asname or alias.name)
            elif absolute_module == "omra.core.ids":
                for alias in node.names:
                    if alias.name == "_GENERATOR":
                        aliases.add(alias.asname or alias.name)
    return aliases


def _ulid_entrypoint_offenders(modules: tuple[astutil.SourceModule, ...]) -> list[str]:
    offenders = []
    for site in astutil.find_imports(modules):
        absolute_target = _absolute_import_target(site.module, site.target)
        if site.module.dotted != "omra.core.ids" and (
            absolute_target == "ulid"
            or absolute_target.startswith("ulid.")
            or absolute_target == "omra.core.ids._GENERATOR"
        ):
            offenders.append(_format_import_site(site, absolute_target))
    for module in modules:
        if module.dotted == "omra.core.ids":
            continue
        aliases = _core_ids_aliases(module)
        if not aliases:
            continue
        for node in ast.walk(module.tree):
            if not isinstance(node, ast.Attribute) or node.attr != "_GENERATOR":
                continue
            chain = astutil.attribute_chain(node)
            owner = chain.removesuffix("._GENERATOR")
            if owner in aliases:
                offenders.append(f"{module.dotted}:{node.lineno} → access {chain}")
    return offenders


def _core_ids_dependency_offenders(modules: tuple[astutil.SourceModule, ...]) -> list[str]:
    offenders = []
    for site in astutil.find_imports(modules):
        if site.module.dotted != "omra.core.ids":
            continue
        absolute_target = _absolute_import_target(site.module, site.target)
        if (
            absolute_target.startswith("omra.")
            and absolute_target != "omra.core.errors.IdentifierError"
        ):
            offenders.append(_format_import_site(site, absolute_target))
    return offenders


@pytest.mark.arch
def test_core_source_contains_no_broker_account_literals() -> None:
    assert astutil.find_string_literals(astutil.modules_in("core"), "CANO", "ACNT_PRDT_CD") == []


@pytest.mark.arch
def test_core_ids_is_only_ulid_creation_entrypoint() -> None:
    assert _ulid_entrypoint_offenders(astutil.source_modules()) == []


@pytest.mark.arch
def test_core_ids_imports_no_internal_module_except_core_errors() -> None:
    assert _core_ids_dependency_offenders(astutil.source_modules()) == []


@pytest.mark.arch
def test_core_ids_dependency_guard_rejects_forbidden_relative_import() -> None:
    modules = (
        _module(
            "omra.core.ids",
            "from .errors import IdentifierError\nfrom .money import Dec\n",
        ),
    )
    assert _core_ids_dependency_offenders(modules) != []


@pytest.mark.arch
def test_ulid_entrypoint_guard_rejects_private_generator_access() -> None:
    modules = (
        _module("omra.core.ids", "_GENERATOR = object()\n"),
        _module(
            "omra.audit.events",
            "from omra.core.ids import _GENERATOR\n\nvalue = _GENERATOR.generate()\n",
        ),
    )
    assert _ulid_entrypoint_offenders(modules) != []
