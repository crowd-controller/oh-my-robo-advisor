"""The configuration foundation may only depend on core inside OMRA."""

import ast
from pathlib import Path

_CONFIG_ROOT = Path(__file__).resolve().parents[2] / "src" / "omra" / "config"
_ALLOWED_INTERNAL_ROOTS = frozenset({"omra.config", "omra.core"})


def _internal_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names if alias.name.startswith("omra."))
        elif isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("omra."):
            imported.add(node.module)
    return imported


def test_config_only_imports_config_or_core_inside_omra() -> None:
    violations: list[str] = []
    for path in sorted(_CONFIG_ROOT.rglob("*.py")):
        for module in sorted(_internal_imports(path)):
            if not any(
                module == root or module.startswith(f"{root}.") for root in _ALLOWED_INTERNAL_ROOTS
            ):
                violations.append(f"{path.relative_to(_CONFIG_ROOT)} -> {module}")

    assert violations == []
