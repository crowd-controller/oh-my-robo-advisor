"""AT-1: persistence repo modules and write-whitelist contracts stay synchronized."""

import tomllib
from pathlib import Path
from typing import cast

_ROOT = Path(__file__).resolve().parents[2]
_REPOS_ROOT = _ROOT / "src" / "omra" / "persistence" / "repos"

_WRITE_WHITELISTS = {
    "C04b": frozenset({"research_extractions"}),
    "C05b": frozenset({"pending_tax_events", "surveillance_flags"}),
    "C07b": frozenset({"budget", "experiments"}),
}


def _contracts() -> list[dict[str, object]]:
    document = tomllib.loads((_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    tool = cast("dict[str, object]", document["tool"])
    importlinter = cast("dict[str, object]", tool["importlinter"])
    return cast("list[dict[str, object]]", importlinter["contracts"])


def _contract_by_id(contract_id: str) -> dict[str, object]:
    for contract in _contracts():
        name = cast("str", contract["name"])
        if name.startswith(f"{contract_id} "):
            return contract
    raise AssertionError(f"missing import-linter contract {contract_id}")


def _repo_modules() -> frozenset[str]:
    return frozenset(
        path.stem for path in _REPOS_ROOT.glob("*.py") if path.stem not in {"__init__", "base"}
    )


def _forbidden_repo_modules(contract_id: str) -> frozenset[str]:
    contract = _contract_by_id(contract_id)
    forbidden = cast("list[str]", contract["forbidden_modules"])
    prefix = "omra.persistence.repos."
    return frozenset(
        module.removeprefix(prefix) for module in forbidden if module.startswith(prefix)
    )


def test_contract_catalog_is_complete() -> None:
    actual = {cast("str", contract["name"]).split(maxsplit=1)[0] for contract in _contracts()}
    expected = {
        "C01",
        "C02",
        "C03",
        "C04a",
        "C04b",
        "C05a",
        "C05b",
        "C06a",
        "C06b",
        "C07a",
        "C07b",
        "C08",
        "C09",
        "C10",
        "C11",
        "C12",
        "C13",
        "C14",
        "C15",
    }

    assert actual == expected


def test_repo_contract_forbidden_sets_are_bidirectionally_complete() -> None:
    repo_modules = _repo_modules()

    for contract_id, allowed in _WRITE_WHITELISTS.items():
        assert _forbidden_repo_modules(contract_id) == repo_modules - allowed
