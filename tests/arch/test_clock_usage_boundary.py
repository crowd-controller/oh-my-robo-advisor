"""AT-9: production code obtains timestamps and waits through the injected Clock."""

import ast
from pathlib import Path

import pytest

_SOURCE_ROOT = Path(__file__).resolve().parents[2] / "src" / "omra"
_CLOCK_PATH = Path("core/clock.py")
_FORBIDDEN_CALLS = frozenset(
    {
        "asyncio.sleep",
        "datetime.date.today",
        "datetime.datetime.now",
    }
)


def _import_aliases(tree: ast.AST) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for imported in node.names:
                bound = imported.asname or imported.name.split(".", maxsplit=1)[0]
                target = imported.name if imported.asname else bound
                aliases[bound] = target
        elif isinstance(node, ast.ImportFrom) and node.module:
            for imported in node.names:
                if imported.name == "*":
                    continue
                bound = imported.asname or imported.name
                aliases[bound] = f"{node.module}.{imported.name}"
    return aliases


def _qualified_name(node: ast.expr, aliases: dict[str, str]) -> str | None:
    if isinstance(node, ast.Name):
        return aliases.get(node.id, node.id)
    if isinstance(node, ast.Attribute):
        parent = _qualified_name(node.value, aliases)
        return None if parent is None else f"{parent}.{node.attr}"
    return None


def _forbidden_calls(source: str) -> tuple[tuple[int, str], ...]:
    tree = ast.parse(source)
    aliases = _import_aliases(tree)
    calls: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        qualified = _qualified_name(node.func, aliases)
        if qualified in _FORBIDDEN_CALLS:
            calls.append((node.lineno, qualified))
    return tuple(sorted(calls))


def test_production_sources_use_clock_instead_of_direct_time_or_sleep_calls() -> None:
    violations: list[str] = []
    for path in sorted(_SOURCE_ROOT.rglob("*.py")):
        relative = path.relative_to(_SOURCE_ROOT)
        if relative == _CLOCK_PATH:
            continue
        source = path.read_text(encoding="utf-8")
        violations.extend(
            f"{relative}:{line} -> {qualified}" for line, qualified in _forbidden_calls(source)
        )

    assert violations == []


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("import datetime as dt\ndt.datetime.now()\n", "datetime.datetime.now"),
        (
            "from datetime import datetime as instant\ninstant.now()\n",
            "datetime.datetime.now",
        ),
        ("from datetime import date as day\nday.today()\n", "datetime.date.today"),
        (
            "import asyncio as aio\nasync def wait():\n    await aio.sleep(1)\n",
            "asyncio.sleep",
        ),
        (
            "from asyncio import sleep as pause\nasync def wait():\n    await pause(1)\n",
            "asyncio.sleep",
        ),
    ],
)
def test_time_call_scanner_detects_import_aliases(source: str, expected: str) -> None:
    assert tuple(qualified for _, qualified in _forbidden_calls(source)) == (expected,)
