"""AT-1 · AT-7 — import-linter 계약의 동기화와 실차단을 검사한다.

**왜 계약만으로 부족한가**: import-linter의 `forbidden` 계약은 열거되지 않은
간선을 **허용**한다(default-allow). 새 repo 파일이 생기면 세 화이트리스트 계약
(C04b·C05b·C07b)에 자동으로 들어가지 않으므로, 관측 3레이어가 그 테이블을
조용히 쓸 수 있게 된다. AT-1이 파일 집합과 계약 열거를 **양방향** 대조해 그
구멍을 막는다 (설계 01 §8.1.1 [DD-01-7] · §8.3).

AT-7은 계약 파일 오등록을 잡는다 — 계약이 등록만 되고 실제로 아무것도 막지
않는 상태는 조용히 통과하기 때문이다.

검증 항목: AT-1 · AT-7 · V01-계약 실차단 6건
"""

from __future__ import annotations

import os
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PYPROJECT = REPO_ROOT / "pyproject.toml"
REPOS_DIR = REPO_ROOT / "src" / "omra" / "persistence" / "repos"

# 관측 레이어별 쓰기 화이트리스트 — 유일 원문은 계획 01 §2.2다.
#   research → research_extractions 1개
#   surveillance → surveillance_flags · pending_tax_events 2개
#   labs → experiments · budget 2개
#   realtime → 0개 (C06b가 persistence 전체를 금지한다)
WRITE_WHITELIST: dict[str, frozenset[str]] = {
    "C04b": frozenset({"research_extractions"}),
    "C05b": frozenset({"surveillance_flags", "pending_tax_events"}),
    "C07b": frozenset({"experiments", "budget"}),
}

# `TABLES`를 선언하지 않는 모듈 — 테이블 쓰기 모듈이 아니므로 대조 집합에서 제외한다.
NON_TABLE_MODULES: frozenset[str] = frozenset({"__init__", "base"})


def _contracts() -> list[dict[str, object]]:
    with PYPROJECT.open("rb") as fh:
        data = tomllib.load(fh)
    tool = data["tool"]
    assert isinstance(tool, dict)
    linter = tool["importlinter"]
    assert isinstance(linter, dict)
    contracts = linter["contracts"]
    assert isinstance(contracts, list)
    return contracts


def _contract_by_prefix(prefix: str) -> dict[str, object]:
    for c in _contracts():
        name = c.get("name")
        if isinstance(name, str) and name.startswith(prefix):
            return c
    pytest.fail(f"계약 {prefix} 가 등록되어 있지 않다")


def _repo_modules_on_disk() -> frozenset[str]:
    return frozenset(p.stem for p in REPOS_DIR.glob("*.py") if p.stem not in NON_TABLE_MODULES)


def _forbidden_repos(contract: dict[str, object]) -> frozenset[str]:
    modules = contract["forbidden_modules"]
    assert isinstance(modules, list)
    prefix = "omra.persistence.repos."
    return frozenset(str(m).removeprefix(prefix) for m in modules if str(m).startswith(prefix))


@pytest.mark.arch
def test_all_expected_contracts_registered() -> None:
    """설계 01 §8.2가 정의한 계약 19종이 전부 등록되어 있다."""
    names = [str(c["name"]) for c in _contracts()]
    expected_prefixes = [
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
    ]
    for prefix in expected_prefixes:
        assert any(n.startswith(prefix) for n in names), f"계약 {prefix} 누락"
    assert len(names) == len(expected_prefixes), f"예정에 없는 계약: {names}"


@pytest.mark.arch
@pytest.mark.parametrize("contract_id", sorted(WRITE_WHITELIST))
def test_at1_write_whitelist_enumeration_is_complete(contract_id: str) -> None:
    """AT-1 (→ 방향) — 디스크의 repo 모듈이 전부 계약에 반영되어 있다.

    계약에 없는 repo 모듈은 default-allow로 열려 있다는 뜻이다.
    """
    on_disk = _repo_modules_on_disk()
    whitelist = WRITE_WHITELIST[contract_id]
    expected_forbidden = on_disk - whitelist
    actual_forbidden = _forbidden_repos(_contract_by_prefix(contract_id))
    missing = expected_forbidden - actual_forbidden
    assert not missing, (
        f"{contract_id} 금지 열거에 없는 repo 모듈: {sorted(missing)} — "
        "새 repo를 추가하면 같은 커밋에서 세 계약을 갱신해야 한다"
    )


@pytest.mark.arch
@pytest.mark.parametrize("contract_id", sorted(WRITE_WHITELIST))
def test_at1_write_whitelist_enumeration_has_no_phantom(contract_id: str) -> None:
    """AT-1 (← 방향) — 계약이 존재하지 않는 모듈을 열거하지 않는다.

    존재하지 않는 모듈을 계약이 참조하면 `lint-imports` 자체가 에러를 낸다
    (설계 01 §2.4).
    """
    on_disk = _repo_modules_on_disk()
    phantom = _forbidden_repos(_contract_by_prefix(contract_id)) - on_disk
    assert not phantom, f"{contract_id} 가 실재하지 않는 모듈을 참조한다: {sorted(phantom)}"


@pytest.mark.arch
@pytest.mark.parametrize("contract_id", sorted(WRITE_WHITELIST))
def test_at1_whitelist_modules_are_not_forbidden(contract_id: str) -> None:
    """화이트리스트 모듈이 실수로 금지 열거에 들어가 있지 않다."""
    forbidden = _forbidden_repos(_contract_by_prefix(contract_id))
    overlap = WRITE_WHITELIST[contract_id] & forbidden
    assert not overlap, f"{contract_id} 가 자기 화이트리스트를 금지했다: {sorted(overlap)}"


@pytest.mark.arch
@pytest.mark.parametrize("contract_id", sorted(WRITE_WHITELIST))
def test_at1_rw_session_is_forbidden(contract_id: str) -> None:
    """세 계약 모두 `persistence.session`(rw 세션 초크포인트)을 금지한다.

    repo 화이트리스트를 아무리 좁혀도 rw 세션을 직접 import하면 우회된다.
    """
    modules = _contract_by_prefix(contract_id)["forbidden_modules"]
    assert isinstance(modules, list)
    assert "omra.persistence.session" in [str(m) for m in modules]


@pytest.mark.arch
@pytest.mark.parametrize("contract_id", sorted(WRITE_WHITELIST))
def test_at1_indirect_imports_allowed(contract_id: str) -> None:
    """정당한 체인(레이어 → 자기 repo → session)이 오탐되지 않는다.

    `allow_indirect_imports` 없이는 `research → repos.research_extractions →
    persistence.session` 이 위반으로 잡혀 계약이 무력화된다(설계 01 §11-1).
    """
    contract = _contract_by_prefix(contract_id)
    assert contract.get("allow_indirect_imports") is True


@pytest.mark.arch
def test_repos_dir_matches_design_tree() -> None:
    """repos 모듈 집합이 설계 03 §2.1 트리(24종)와 일치한다."""
    expected = frozenset(
        {
            "approvals",
            "budget",
            "decomposition",
            "execution_state",
            "experiments",
            "fills",
            "holidays",
            "nav_snapshots",
            "notifications",
            "orders",
            "pending_tax_events",
            "pending_transfers",
            "plans",
            "policy_versions",
            "positions",
            "protections",
            "reconcile",
            "research_extractions",
            "run_ledger",
            "satellite",
            "state",
            "surveillance_flags",
            "tax_events",
            "tokens",
        }
    )
    found = _repo_modules_on_disk()
    assert found == expected, f"누락: {sorted(expected - found)} / 초과: {sorted(found - expected)}"


def _lint_imports_executable() -> Path:
    """설치된 `lint-imports` 콘솔 스크립트 경로.

    `python -m importlinter.cli` 는 `__main__` 가드가 없어 아무것도 하지 않고
    exit 0으로 끝난다 — 그 상태로 AT-7을 돌리면 **전 계약이 통과한 것처럼**
    보인다. 진입점을 명시적으로 찾는 이유다.
    """
    bindir = Path(sys.executable).parent
    for name in ("lint-imports.exe", "lint-imports"):
        candidate = bindir / name
        if candidate.exists():
            return candidate
    pytest.fail(f"lint-imports 실행 파일을 찾지 못했다 ({bindir})")


def _lint_imports(cwd: Path) -> subprocess.CompletedProcess[str]:
    # 계약 이름이 한국어라 rich 렌더러가 Windows 기본 코드페이지(cp949)에서
    # UnicodeEncodeError로 죽는다. 자식 프로세스의 출력 인코딩을 고정한다.
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
    return subprocess.run(  # noqa: S603
        [str(_lint_imports_executable())],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=cwd,
        env=env,
        check=False,
    )


@pytest.mark.arch
def test_at7_contracts_are_kept_on_clean_tree() -> None:
    """AT-7 (기준선) — 현재 트리에서 전 계약이 KEPT다."""
    result = _lint_imports(REPO_ROOT)
    out = (result.stdout or "") + (result.stderr or "")
    assert result.returncode == 0, out
    assert "0 broken" in out, out


@pytest.mark.arch
@pytest.mark.parametrize(
    ("violator", "victim", "contract"),
    [
        # 계획 01 §2.2 원문 계약
        ("realtime/_at7.py", "omra.execution", "C06a"),
        ("research/_at7.py", "omra.surveillance", "C04a"),
        ("surveillance/_at7.py", "omra.research", "C05a"),
        ("labs/_at7.py", "omra.brokers", "C07a"),
        ("collectors/_at7.py", "omra.data", "C03"),
        ("web/_at7.py", "omra.runtime", "C11"),
        # [DD-01-15] 소유 문서 자기부과 계약 6건
        ("data/_at7.py", "omra.engine", "C08"),
        ("protections/_at7.py", "omra.execution", "C09"),
        ("web/_at7.py", "omra.execution", "C12"),
        ("rpc/_at7.py", "omra.web", "C13"),
        ("backtest/_at7.py", "omra.brokers", "C14"),
        ("tax/_at7.py", "omra.execution", "C15"),
    ],
)
def test_at7_violation_is_actually_blocked(violator: str, victim: str, contract: str) -> None:
    """AT-7 — 위반 파일을 심으면 `lint-imports` 가 실제로 실패한다.

    계약 파일 오등록(이름은 있는데 아무것도 막지 않는 상태)은 조용히 통과한다.
    실차단을 실증하는 것 외에 그것을 잡을 방법이 없다.
    """
    path = REPO_ROOT / "src" / "omra" / violator
    assert not path.exists(), f"{path} 가 이미 존재한다 — 이전 실행이 정리되지 않았다"
    path.write_text(
        f'"""AT-7 위반 픽스처 — 테스트가 즉시 삭제한다."""\n\nimport {victim}\n\n'
        f"__all__ = ['{victim.rsplit('.', maxsplit=1)[-1]}']\n",
        encoding="utf-8",
    )
    try:
        result = _lint_imports(REPO_ROOT)
        out = (result.stdout or "") + (result.stderr or "")
        assert result.returncode != 0, f"{contract} 위반이 통과했다\n{out}"
        assert contract in out, f"{contract} 가 아닌 다른 계약이 잡았다\n{out}"
    finally:
        path.unlink(missing_ok=True)
