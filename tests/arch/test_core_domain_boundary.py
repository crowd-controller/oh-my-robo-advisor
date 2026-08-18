"""Core domain modules remain credential-free and follow their internal DAG."""

import ast
from pathlib import Path

_CORE_ROOT = Path(__file__).resolve().parents[2] / "src" / "omra" / "core"
_LAYERS = {
    "errors": 0,
    "clock": 1,
    "ids": 1,
    "money": 1,
    "tick": 1,
    "models": 2,
    "states": 2,
    "accounts": 3,
}


def _omra_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(
                alias.name
                for alias in node.names
                if alias.name == "omra" or alias.name.startswith("omra.")
            )
        elif isinstance(node, ast.ImportFrom):
            if node.level == 1:
                if node.module:
                    imported.add(f"omra.core.{node.module}")
                else:
                    imported.update(f"omra.core.{alias.name}" for alias in node.names)
            elif node.level > 1:
                imported.add(f"<relative-level-{node.level}>")
            elif node.module and (node.module == "omra" or node.module.startswith("omra.")):
                imported.add(node.module)
    return imported


def test_core_imports_do_not_leave_package_and_only_point_to_lower_layers() -> None:
    violations: list[str] = []
    for source, source_layer in _LAYERS.items():
        for module in sorted(_omra_imports(_CORE_ROOT / f"{source}.py")):
            parts = module.split(".")
            target = parts[2] if module.startswith("omra.core.") else "<outside-core>"
            target_layer = _LAYERS.get(target)
            if target_layer is None or target_layer >= source_layer:
                violations.append(f"{source} -> {module}")

    assert violations == []


def test_core_sources_contain_no_external_credential_vocabulary() -> None:
    forbidden = ("CANO", "ACNT_PRDT_CD", "appkey", "appsecret", "account_number")
    violations: list[str] = []
    for path in sorted(_CORE_ROOT.glob("*.py")):
        source = path.read_text(encoding="utf-8")
        violations.extend(f"{path.name}:{token}" for token in forbidden if token in source)

    assert violations == []
