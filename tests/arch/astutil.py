"""아키텍처 테스트 공용 AST 유틸.

import-linter가 막을 수 있는 것은 **모듈 간선**뿐이다. 호출 순서(AT-2),
값 공간 제약(AT-3), 같은 모듈 안의 심볼 구분(AT-4), 공개 시그니처의 타입
(AT-8) 같은 규율은 소스를 직접 읽어야 강제된다. 그 읽기를 한 곳에 모은다.

정본: 설계 16 §6.1·§6.3 / 01 §8.3
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src" / "omra"


@dataclass(frozen=True)
class SourceModule:
    """파싱된 소스 모듈 하나."""

    path: Path
    dotted: str  # "omra.core.money"
    tree: ast.Module
    text: str

    @property
    def package(self) -> str:
        """1차 패키지명. `omra.core.money` → `core`."""
        parts = self.dotted.split(".")
        return parts[1] if len(parts) > 1 else ""


def _dotted_name(path: Path) -> str:
    rel = path.relative_to(SRC_ROOT.parent)
    parts = list(rel.with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


@lru_cache(maxsize=1)
def source_modules() -> tuple[SourceModule, ...]:
    """`src/omra/` 전체를 파싱한다. 캐시되므로 테스트마다 재파싱하지 않는다."""
    out: list[SourceModule] = []
    for path in sorted(SRC_ROOT.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        out.append(
            SourceModule(
                path=path,
                dotted=_dotted_name(path),
                tree=ast.parse(text, filename=str(path)),
                text=text,
            )
        )
    return tuple(out)


def modules_in(*packages: str) -> tuple[SourceModule, ...]:
    """지정한 1차 패키지의 모듈만 고른다."""
    wanted = frozenset(packages)
    return tuple(m for m in source_modules() if m.package in wanted)


def modules_except(*packages: str) -> tuple[SourceModule, ...]:
    excluded = frozenset(packages)
    return tuple(m for m in source_modules() if m.package not in excluded)


# ══════════════════════════════════════════════════════════════════════
# 호출 탐지 — AT-9(Clock)·AT-10(assert)·[DD-02-21](asyncio.sleep) 등
# ══════════════════════════════════════════════════════════════════════
def call_qualname(node: ast.Call) -> str:
    """`a.b.c(...)` → `"a.b.c"`, `f(...)` → `"f"`. 판정 불가면 빈 문자열."""
    return attribute_chain(node.func)


def attribute_chain(node: ast.expr) -> str:
    """`ast.Attribute`/`ast.Name` 체인을 점 표기 문자열로 복원한다."""
    parts: list[str] = []
    cur: ast.expr = node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
    else:
        return ""
    return ".".join(reversed(parts))


@dataclass(frozen=True)
class CallSite:
    module: SourceModule
    qualname: str
    lineno: int

    def __str__(self) -> str:
        rel = self.module.path.relative_to(REPO_ROOT)
        return f"{rel}:{self.lineno} → {self.qualname}()"


def find_calls(modules: tuple[SourceModule, ...], *suffixes: str) -> list[CallSite]:
    """지정 접미사로 끝나는 호출을 전부 찾는다.

    `find_calls(mods, "datetime.now", "date.today")` 처럼 쓴다. import 별칭
    (`from datetime import datetime as dt`)은 잡지 못하므로 ruff의 banned-api와
    **이중 방어**로 쓴다 — 어느 한쪽만으로는 구멍이 남는다.
    """
    hits: list[CallSite] = []
    for mod in modules:
        for node in ast.walk(mod.tree):
            if not isinstance(node, ast.Call):
                continue
            qual = call_qualname(node)
            if any(qual == s or qual.endswith("." + s) for s in suffixes):
                hits.append(CallSite(mod, qual, node.lineno))
    return hits


# ══════════════════════════════════════════════════════════════════════
# import 탐지
# ══════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class ImportSite:
    module: SourceModule
    target: str
    lineno: int
    type_checking_only: bool

    def __str__(self) -> str:
        rel = self.module.path.relative_to(REPO_ROOT)
        suffix = " (TYPE_CHECKING)" if self.type_checking_only else ""
        return f"{rel}:{self.lineno} → import {self.target}{suffix}"


def _is_type_checking_guard(node: ast.If) -> bool:
    test = node.test
    if isinstance(test, ast.Name) and test.id == "TYPE_CHECKING":
        return True
    return attribute_chain(test).endswith("TYPE_CHECKING")


def find_imports(modules: tuple[SourceModule, ...]) -> list[ImportSite]:
    """모듈별 import 대상을 전부 나열한다.

    `TYPE_CHECKING` 블록 안의 import를 구분해 표시한다 — 타입 주석 전용
    참조는 런타임 간선이 아니므로 계약 판정에서 달리 취급해야 한다
    (예: `tax → execution.assembler.OrderDraft`, 설계 10 §2.1).
    """
    hits: list[ImportSite] = []

    def visit(node: ast.AST, *, guarded: bool, mod: SourceModule) -> None:
        if isinstance(node, ast.Import):
            for alias in node.names:
                hits.append(ImportSite(mod, alias.name, node.lineno, guarded))
            return
        if isinstance(node, ast.ImportFrom):
            # `from . import money` 는 module=None·level=1 이므로 prefix가 "."로
            # 끝난다 — 이때 점을 한 번 더 붙이면 ".money" 가 "..money" 가 된다.
            prefix = "." * node.level + (node.module or "")
            sep = "" if prefix.endswith(".") else "."
            for alias in node.names:
                hits.append(ImportSite(mod, f"{prefix}{sep}{alias.name}", node.lineno, guarded))
            return
        inner_guard = guarded or (isinstance(node, ast.If) and _is_type_checking_guard(node))
        for child in ast.iter_child_nodes(node):
            visit(child, guarded=inner_guard, mod=mod)

    for mod in modules:
        visit(mod.tree, guarded=False, mod=mod)
    return hits


# ══════════════════════════════════════════════════════════════════════
# 공개 시그니처 — AT-8 (strict 섬에 Any·float 유입 금지)
# ══════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class Annotation:
    module: SourceModule
    owner: str  # "함수명" 또는 "클래스명.필드명"
    text: str
    lineno: int

    def __str__(self) -> str:
        rel = self.module.path.relative_to(REPO_ROOT)
        return f"{rel}:{self.lineno} {self.owner}: {self.text}"


def _is_public(name: str) -> bool:
    """`_`로 시작하는 사설 심볼은 검사 대상이 아니다 (설계 16 §3.2)."""
    return not name.startswith("_")


def public_annotations(modules: tuple[SourceModule, ...]) -> list[Annotation]:
    """공개 함수 시그니처와 pydantic 필드의 어노테이션을 수집한다.

    반환값에는 **미어노테이션 인자**도 `text=""` 로 포함된다 — mypy가
    비-strict 모듈에서 흘러든 `Any`를 잡지 못하는 구멍을 메우려면 "없음"도
    위반으로 볼 수 있어야 한다.
    """
    out: list[Annotation] = []

    def record(mod: SourceModule, owner: str, ann: ast.expr | None, lineno: int) -> None:
        out.append(Annotation(mod, owner, "" if ann is None else ast.unparse(ann), lineno))

    def walk_scope(mod: SourceModule, node: ast.AST, prefix: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef):
                if not _is_public(child.name):
                    continue
                qualified = f"{prefix}{child.name}"
                for stmt in child.body:
                    if (
                        isinstance(stmt, ast.AnnAssign)
                        and isinstance(stmt.target, ast.Name)
                        and _is_public(stmt.target.id)
                    ):
                        record(
                            mod,
                            f"{qualified}.{stmt.target.id}",
                            stmt.annotation,
                            stmt.lineno,
                        )
                walk_scope(mod, child, f"{qualified}.")
            elif isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef):
                if not _is_public(child.name):
                    continue
                qualified = f"{prefix}{child.name}"
                args = child.args
                positional = [*args.posonlyargs, *args.args, *args.kwonlyargs]
                for arg in positional:
                    if arg.arg in {"self", "cls"}:
                        continue
                    record(mod, f"{qualified}({arg.arg})", arg.annotation, arg.lineno)
                record(mod, f"{qualified}(->)", child.returns, child.lineno)

    for mod in modules:
        walk_scope(mod, mod.tree, "")
    return out


# ══════════════════════════════════════════════════════════════════════
# 문자열 리터럴 — AT-10(CANO 부재)·AT-12(상태 리터럴 비교 금지)
# ══════════════════════════════════════════════════════════════════════
def _docstring_node_ids(tree: ast.Module) -> set[int]:
    """docstring으로 쓰인 문자열 노드의 id 집합."""
    ids: set[int] = set()
    scopes = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
    for node in ast.walk(tree):
        if not isinstance(node, scopes):
            continue
        body = node.body
        if (
            body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            ids.add(id(body[0].value))
    return ids


def find_string_literals(
    modules: tuple[SourceModule, ...], *needles: str
) -> list[tuple[SourceModule, str, int]]:
    """지정 문자열을 **리터럴로** 포함하는 지점을 찾는다.

    주석·docstring은 제외한다 — 설계 근거를 주석에 적는 것은 권장되는
    일이므로, 원문 검색으로 잡으면 문서화를 막는다.
    """
    hits: list[tuple[SourceModule, str, int]] = []
    for mod in modules:
        doc_nodes = _docstring_node_ids(mod.tree)
        for node in ast.walk(mod.tree):
            if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                continue
            if id(node) in doc_nodes:
                continue
            for needle in needles:
                if needle in node.value:
                    hits.append((mod, needle, node.lineno))
    return hits
