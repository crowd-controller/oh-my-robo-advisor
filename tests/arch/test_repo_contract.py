"""Repository table ownership stays declared, disjoint, complete, and enforced."""

import ast
import re
from pathlib import Path
from typing import Final

import pytest

_ROOT: Final = Path(__file__).resolve().parents[2]
_REPOS_ROOT: Final = _ROOT / "src" / "omra" / "persistence" / "repos"
_SCHEMA_PATH: Final = _ROOT / "src" / "omra" / "persistence" / "models" / "schema.py"
_FIXTURES: Final = Path(__file__).with_name("fixtures") / "repo_contract"
_MUTATION_FUNCTIONS: Final[frozenset[str]] = frozenset({"delete", "insert", "update"})
_SQL_MUTATION = re.compile(
    r"^\s*(?:INSERT\s+INTO|UPDATE|DELETE\s+FROM)\s+[\"`\[]?([A-Za-z_][A-Za-z0-9_]*)",
    re.IGNORECASE,
)


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _frozenset_strings(expression: ast.expr, label: str) -> frozenset[str]:
    if not (
        isinstance(expression, ast.Call)
        and isinstance(expression.func, ast.Name)
        and expression.func.id == "frozenset"
        and not expression.keywords
    ):
        raise AssertionError(f"{label}: TABLES must be a literal frozenset")
    if not expression.args:
        return frozenset()
    if len(expression.args) != 1 or not isinstance(
        expression.args[0], (ast.Set, ast.List, ast.Tuple)
    ):
        raise AssertionError(f"{label}: TABLES must contain only literal table names")

    names: set[str] = set()
    for element in expression.args[0].elts:
        if not isinstance(element, ast.Constant) or not isinstance(element.value, str):
            raise AssertionError(f"{label}: TABLES must contain only literal table names")
        names.add(element.value)
    return frozenset(names)


def _declared_tables(tree: ast.Module, label: str) -> frozenset[str]:
    declarations: list[ast.expr] = []
    for statement in tree.body:
        if isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name):
            if statement.target.id == "TABLES" and statement.value is not None:
                declarations.append(statement.value)
        elif isinstance(statement, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "TABLES" for target in statement.targets
        ):
            declarations.append(statement.value)

    if len(declarations) != 1:
        raise AssertionError(f"{label}: expected exactly one TABLES declaration")
    return _frozenset_strings(declarations[0], label)


def _model_table_names() -> dict[str, str]:
    rows: dict[str, str] = {}
    for statement in _parse(_SCHEMA_PATH).body:
        if not isinstance(statement, ast.ClassDef):
            continue
        for child in statement.body:
            if not isinstance(child, ast.Assign):
                continue
            if not any(
                isinstance(target, ast.Name) and target.id == "__tablename__"
                for target in child.targets
            ):
                continue
            if not isinstance(child.value, ast.Constant) or not isinstance(child.value.value, str):
                raise AssertionError(f"{statement.name}: __tablename__ must be a string literal")
            rows[statement.name] = child.value.value
    return rows


def _model_target(expression: ast.expr, model_tables: dict[str, str], label: str) -> str:
    if isinstance(expression, ast.Name) and expression.id in model_tables:
        return model_tables[expression.id]
    if isinstance(expression, ast.Attribute) and expression.attr in model_tables:
        return model_tables[expression.attr]
    raise AssertionError(f"{label}: dynamic or unknown mutation target")


def _raw_sql_target(call: ast.Call, label: str) -> str | None:
    if not call.args:
        raise AssertionError(f"{label}: exec_driver_sql requires static SQL")
    statement = call.args[0]
    if not isinstance(statement, ast.Constant) or not isinstance(statement.value, str):
        raise AssertionError(f"{label}: dynamic raw SQL is forbidden")
    match = _SQL_MUTATION.match(statement.value)
    return match.group(1) if match is not None else None


def _mutation_targets(tree: ast.Module, model_tables: dict[str, str], label: str) -> frozenset[str]:
    targets: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name) and node.func.id in _MUTATION_FUNCTIONS:
            if not node.args:
                raise AssertionError(f"{label}: mutation call has no target")
            targets.add(_model_target(node.args[0], model_tables, label))
        elif isinstance(node.func, ast.Attribute) and node.func.attr == "exec_driver_sql":
            target = _raw_sql_target(node, label)
            if target is not None:
                targets.add(target)
    return frozenset(targets)


def _analyze(path: Path) -> tuple[frozenset[str], frozenset[str]]:
    tree = _parse(path)
    declared = _declared_tables(tree, path.name)
    targets = _mutation_targets(tree, _model_table_names(), path.name)
    undeclared = targets - declared
    if undeclared:
        raise AssertionError(f"{path.name}: undeclared mutation targets {sorted(undeclared)}")
    return declared, targets


def test_repo_ownership_is_declared_disjoint_and_complete() -> None:
    owners: dict[str, str] = {}
    repo_paths = sorted(path for path in _REPOS_ROOT.glob("*.py") if path.name != "__init__.py")

    for path in repo_paths:
        declared, _ = _analyze(path)
        for table_name in declared:
            assert table_name not in owners, (
                f"{table_name} is owned by both {owners[table_name]} and {path.stem}"
            )
            owners[table_name] = path.stem

    assert len(repo_paths) == 25
    assert frozenset(owners) == frozenset(_model_table_names().values())
    assert len(owners) == 34


@pytest.mark.parametrize(
    ("fixture_name", "expected_message"),
    [
        ("undeclared.py", "undeclared mutation targets ['orders']"),
        ("dynamic.py", "dynamic or unknown mutation target"),
    ],
)
def test_mutation_fixture_is_rejected(fixture_name: str, expected_message: str) -> None:
    with pytest.raises(AssertionError, match=re.escape(expected_message)):
        _analyze(_FIXTURES / fixture_name)
