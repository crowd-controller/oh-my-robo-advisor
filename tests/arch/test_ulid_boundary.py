"""All process-monotonic ULID generation goes through core.ids.new_id."""

import ast
from pathlib import Path

_SOURCE_ROOT = Path(__file__).resolve().parents[2] / "src" / "omra"
_OWNER = Path("core/ids.py")


def test_only_core_ids_imports_the_ulid_library() -> None:
    violations: list[str] = []
    for path in sorted(_SOURCE_ROOT.rglob("*.py")):
        relative = path.relative_to(_SOURCE_ROOT)
        if relative == _OWNER:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                if any(
                    alias.name == "ulid" or alias.name.startswith("ulid.") for alias in node.names
                ):
                    violations.append(f"{relative}:{node.lineno}")
            elif (
                isinstance(node, ast.ImportFrom)
                and node.module
                and (node.module == "ulid" or node.module.startswith("ulid."))
            ):
                violations.append(f"{relative}:{node.lineno}")

    assert violations == []
