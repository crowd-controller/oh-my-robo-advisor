"""AST 유틸 자체의 검증.

이 유틸이 조용히 틀리면 그 위의 아키텍처 테스트 전부가 **아무것도 찾지 못한
채 통과**한다. `find_calls`가 빈 리스트를 돌려주면 "위반 0건"과 구분되지 않는다.

정본: 설계 16 §6.1·§6.3
"""

from __future__ import annotations

import ast

from tests.arch import astutil


def _parse(text: str, dotted: str = "omra.sample.mod") -> astutil.SourceModule:
    return astutil.SourceModule(
        path=astutil.SRC_ROOT / "sample" / "mod.py",
        dotted=dotted,
        tree=ast.parse(text),
        text=text,
    )


# ══════════════════════════════════════════════════════════════════════
# 모듈 수집
# ══════════════════════════════════════════════════════════════════════
def test_source_modules_covers_the_whole_package() -> None:
    """`src/omra/` 전체를 파싱한다 — 하나라도 빠지면 그 모듈은 무검사다."""
    mods = astutil.source_modules()
    assert mods, "소스 모듈을 하나도 찾지 못했다"
    dotted = {m.dotted for m in mods}
    assert "omra" in dotted
    assert "omra.core" in dotted
    assert "omra.persistence.repos.orders" in dotted


def test_package_attribute_is_first_level() -> None:
    mods = {m.dotted: m for m in astutil.source_modules()}
    assert mods["omra.persistence.repos.orders"].package == "persistence"
    assert mods["omra.core"].package == "core"
    assert mods["omra"].package == ""


def test_modules_in_and_except_are_complements() -> None:
    inside = set(astutil.modules_in("core", "audit"))
    outside = set(astutil.modules_except("core", "audit"))
    assert not inside & outside
    assert inside | outside == set(astutil.source_modules())


# ══════════════════════════════════════════════════════════════════════
# 호출 탐지
# ══════════════════════════════════════════════════════════════════════
def test_find_calls_detects_dotted_calls() -> None:
    mod = _parse("import datetime\n\n\ndef f():\n    return datetime.datetime.now()\n")
    hits = astutil.find_calls((mod,), "datetime.now")
    assert [h.qualname for h in hits] == ["datetime.datetime.now"]
    assert hits[0].lineno == 5


def test_find_calls_matches_bare_name() -> None:
    mod = _parse("def f():\n    return now()\n")
    assert [h.qualname for h in astutil.find_calls((mod,), "now")] == ["now"]


def test_find_calls_does_not_match_substring_of_attribute() -> None:
    """`snapshot_now()` 가 `now` 로 잡히면 오탐이 폭증한다."""
    mod = _parse("def f():\n    return snapshot_now()\n")
    assert astutil.find_calls((mod,), "now") == []


def test_find_calls_returns_empty_when_absent() -> None:
    mod = _parse("def f():\n    return 1\n")
    assert astutil.find_calls((mod,), "datetime.now") == []


def test_call_site_renders_a_locatable_string() -> None:
    mod = _parse("import time\n\n\ndef f():\n    time.sleep(1)\n")
    (hit,) = astutil.find_calls((mod,), "time.sleep")
    rendered = str(hit)
    assert "time.sleep()" in rendered
    assert ":5" in rendered


# ══════════════════════════════════════════════════════════════════════
# import 탐지
# ══════════════════════════════════════════════════════════════════════
def test_find_imports_collects_plain_and_from_imports() -> None:
    mod = _parse("import os\nfrom pathlib import Path\n")
    targets = {i.target for i in astutil.find_imports((mod,))}
    assert targets == {"os", "pathlib.Path"}


def test_find_imports_marks_type_checking_only() -> None:
    """타입 주석 전용 참조는 **런타임 간선이 아니다**.

    설계 10 §2.1이 `tax → execution.assembler.OrderDraft` 를 `TYPE_CHECKING`
    하에서만 허용하므로, 구분하지 못하면 계약 판정이 틀린다.
    """
    mod = _parse(
        "from typing import TYPE_CHECKING\n\n"
        "if TYPE_CHECKING:\n"
        "    from omra.execution.assembler import OrderDraft\n"
    )
    by_target = {i.target: i for i in astutil.find_imports((mod,))}
    assert by_target["typing.TYPE_CHECKING"].type_checking_only is False
    assert by_target["omra.execution.assembler.OrderDraft"].type_checking_only is True


def test_find_imports_handles_relative_imports() -> None:
    mod = _parse("from . import money\nfrom ..core import tick\n")
    targets = {i.target for i in astutil.find_imports((mod,))}
    assert targets == {".money", "..core.tick"}


# ══════════════════════════════════════════════════════════════════════
# 공개 시그니처
# ══════════════════════════════════════════════════════════════════════
def test_public_annotations_collects_args_and_return() -> None:
    mod = _parse("def f(a: int, b: str) -> bool:\n    return True\n")
    got = {(a.owner, a.text) for a in astutil.public_annotations((mod,))}
    assert got == {("f(a)", "int"), ("f(b)", "str"), ("f(->)", "bool")}


def test_public_annotations_records_missing_annotation_as_empty() -> None:
    """미어노테이션 인자는 `text=""` 로 기록된다 — "없음"도 위반일 수 있다."""
    mod = _parse("def f(a) -> None:\n    pass\n")
    by_owner = {a.owner: a.text for a in astutil.public_annotations((mod,))}
    assert by_owner["f(a)"] == ""


def test_public_annotations_skips_private_symbols() -> None:
    mod = _parse("def _hidden(a: float) -> None:\n    pass\n")
    assert astutil.public_annotations((mod,)) == []


def test_public_annotations_skips_self_and_cls() -> None:
    mod = _parse(
        "class C:\n    def m(self, x: int) -> None:\n        pass\n"
        "    @classmethod\n    def k(cls, y: int) -> None:\n        pass\n"
    )
    owners = {a.owner for a in astutil.public_annotations((mod,))}
    assert "C.m(self)" not in owners
    assert "C.k(cls)" not in owners
    assert "C.m(x)" in owners


def test_public_annotations_collects_pydantic_fields() -> None:
    """클래스 본문의 어노테이션(= pydantic 필드)도 검사 대상이다."""
    mod = _parse("class Order:\n    qty: float\n    _secret: int\n")
    by_owner = {a.owner: a.text for a in astutil.public_annotations((mod,))}
    assert by_owner["Order.qty"] == "float"
    assert "Order._secret" not in by_owner


# ══════════════════════════════════════════════════════════════════════
# 문자열 리터럴
# ══════════════════════════════════════════════════════════════════════
def test_find_string_literals_detects_code_literals() -> None:
    mod = _parse('X = {"CANO": "123"}\n')
    hits = astutil.find_string_literals((mod,), "CANO")
    assert [h[1] for h in hits] == ["CANO"]


def test_find_string_literals_ignores_docstrings() -> None:
    """설계 근거를 주석·docstring에 적는 것은 권장된다 — 그것까지 잡으면 문서화를 막는다."""
    mod = _parse('"""CANO 를 도메인 타입에 두지 않는다."""\n\nX = 1\n')
    assert astutil.find_string_literals((mod,), "CANO") == []


def test_find_string_literals_ignores_comments() -> None:
    mod = _parse("X = 1  # CANO 는 여기 없다\n")
    assert astutil.find_string_literals((mod,), "CANO") == []


def test_find_string_literals_ignores_function_docstrings() -> None:
    mod = _parse('def f() -> None:\n    """CANO 금지."""\n')
    assert astutil.find_string_literals((mod,), "CANO") == []
