"""정적 품질 게이트 대조 — ruff·mypy 설정이 설계 16 §3과 일치하는지 검사한다.

설정 파일은 사람이 편집하고 설계서도 사람이 편집한다. 둘이 갈라지면 **문서가
약속한 것과 CI가 실제로 검사하는 것이 달라지고**, 그 차이는 조용하다. 이 테스트가
그 침묵을 깬다 (AT-13 "문서 ↔ 설정 대조"의 S01-2 범위).

검증 항목: V16-04 · V16-06 · V16-07
"""

from __future__ import annotations

import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PYPROJECT = REPO_ROOT / "pyproject.toml"
DESIGN_16 = REPO_ROOT / "docs" / "design" / "16-testing-and-quality.md"

# 설계 16 §3.1 [DD-16-2] strict 섬 완전열거.
# 이 집합을 바꾸려면 16 §3.1 표를 먼저 고쳐야 한다 — 순서가 반대면 문서가 사후 정당화가 된다.
EXPECTED_STRICT_MODULES: frozenset[str] = frozenset(
    {
        "omra.core.money",
        "omra.core.tick",
        "omra.core.models",
        "omra.core.ids",
        "omra.core.accounts",
        "omra.core.states",
        "omra.core.errors",
        "omra.core.clock",
        "omra.engine.optimizer",
        "omra.engine.rebalancer",
        "omra.tax.*",
        "omra.execution.*",
        "omra.portfolio.*",
        "omra.protections.*",
        "omra.persistence.repos.*",
    }
)

# 설계 16 §3.3 [DD-16-3] banned-api 4종.
# `print`는 banned-api가 아니라 T20 룰로 막는다 — 중복 정의하지 않는다.
EXPECTED_BANNED_API: frozenset[str] = frozenset(
    {
        "datetime.datetime.now",
        "datetime.date.today",
        "time.sleep",
        "random.random",
    }
)


def _pyproject() -> dict[str, object]:
    with PYPROJECT.open("rb") as fh:
        return tomllib.load(fh)


def _mypy_overrides() -> list[dict[str, object]]:
    tool = _pyproject()["tool"]
    assert isinstance(tool, dict)
    mypy = tool["mypy"]
    assert isinstance(mypy, dict)
    overrides = mypy["overrides"]
    assert isinstance(overrides, list)
    return overrides


@pytest.mark.arch
def test_mypy_strict_island_matches_design() -> None:
    """V16-07 — strict 섬 목록이 설계 16 §3.1 표와 일치한다."""
    strict_blocks = [o for o in _mypy_overrides() if o.get("strict") is True]
    assert len(strict_blocks) == 1, "strict 섬은 단일 override 블록이어야 한다"
    modules = strict_blocks[0]["module"]
    assert isinstance(modules, list)
    found = frozenset(str(m) for m in modules)
    assert found == EXPECTED_STRICT_MODULES, (
        f"누락: {sorted(EXPECTED_STRICT_MODULES - found)} / "
        f"초과: {sorted(found - EXPECTED_STRICT_MODULES)}"
    )


@pytest.mark.arch
def test_mypy_strict_island_forbids_any() -> None:
    """섬 안에서 `Any`를 '쓰겠다'는 선언조차 금지한다 (16 §3.1)."""
    block = next(o for o in _mypy_overrides() if o.get("strict") is True)
    assert block.get("disallow_any_explicit") is True
    assert block.get("disallow_any_unimported") is True


@pytest.mark.arch
def test_mypy_baseline_covers_all_modules() -> None:
    """strict 밖 모듈도 검사 **대상에서 빼지 않는다** (16 §3.1 결정 ②)."""
    tool = _pyproject()["tool"]
    assert isinstance(tool, dict)
    mypy = tool["mypy"]
    assert isinstance(mypy, dict)
    assert mypy["files"] == ["src/omra", "tests"]
    assert mypy["disallow_untyped_defs"] is True


@pytest.mark.arch
def test_strict_module_names_appear_in_design_doc() -> None:
    """열거된 모듈이 설계 16 §3.1 표에 실제로 등장한다 (문서 ↔ 설정 대조)."""
    doc = DESIGN_16.read_text(encoding="utf-8")
    for module in sorted(EXPECTED_STRICT_MODULES):
        stem = module.removesuffix(".*")
        assert stem in doc, f"{module} 가 설계 16 §3.1 표에 없다"


@pytest.mark.arch
def test_ruff_banned_api_matches_design() -> None:
    """banned-api 4종이 설계 16 §3.3과 일치한다 (Clock 주입 규율의 정적 절반)."""
    tool = _pyproject()["tool"]
    assert isinstance(tool, dict)
    ruff = tool["ruff"]
    assert isinstance(ruff, dict)
    lint = ruff["lint"]
    assert isinstance(lint, dict)
    tidy = lint["flake8-tidy-imports"]
    assert isinstance(tidy, dict)
    banned = tidy["banned-api"]
    assert isinstance(banned, dict)
    assert frozenset(banned) == EXPECTED_BANNED_API
    for name, spec in banned.items():
        assert isinstance(spec, dict)
        assert spec.get("msg"), f"{name} 에 대체 수단 안내가 없다"


@pytest.mark.arch
def test_ruff_excludes_markdown() -> None:
    """마크다운이 ruff 대상에서 제외된다.

    ruff는 ``` 코드 펜스 안의 파이썬을 포맷한다. `docs/`의 코드 블록은 **설계
    정본의 일부**이므로 도구가 재작성하면 "설계서와 코드가 다르다"는 판정이
    무의미해진다. 이 제외가 풀리면 설계서가 조용히 변형된다.
    """
    tool = _pyproject()["tool"]
    assert isinstance(tool, dict)
    ruff = tool["ruff"]
    assert isinstance(ruff, dict)
    excluded = ruff.get("extend-exclude", [])
    assert isinstance(excluded, list)
    assert "*.md" in excluded


@pytest.mark.arch
def test_ruff_selects_failure_mode_rules() -> None:
    """이 시스템의 알려진 실패 모드에 대응하는 룰셋이 선택되어 있다."""
    tool = _pyproject()["tool"]
    assert isinstance(tool, dict)
    ruff = tool["ruff"]
    assert isinstance(ruff, dict)
    lint = ruff["lint"]
    assert isinstance(lint, dict)
    selected = lint["select"]
    assert isinstance(selected, list)
    required = {
        "DTZ": "naive datetime — 02 §5.4 시각 직렬화 규약",
        "TID": "banned-api — 02 §8.1 Clock 주입 규율",
        "S": "bandit — 계획 01 §7 보안 목록",
        "T20": "print — structlog 규약",
        "ASYNC": "블로킹 호출 — 계획 01 §1.4 단일 루프 보호",
    }
    for code, why in required.items():
        assert code in selected, f"{code} 룰셋 누락 ({why})"


@pytest.mark.arch
def test_direct_clock_call_is_rejected_by_ruff(tmp_path: Path) -> None:
    """V16-06 — `datetime.now()` 직접 호출이 TID251로 차단된다.

    설정이 존재하는 것과 실제로 차단하는 것은 다르다. 위반 픽스처로 실증한다.
    """
    violation = tmp_path / "violation.py"
    violation.write_text(
        "import datetime\n\n\ndef f() -> datetime.datetime:\n    return datetime.datetime.now()\n",
        encoding="utf-8",
    )
    result = subprocess.run(  # noqa: S603
        [
            sys.executable,
            "-m",
            "ruff",
            "check",
            "--config",
            str(PYPROJECT),
            "--no-cache",
            str(violation),
        ],
        capture_output=True,
        text=True,
        # banned-api 안내문이 한국어라 UTF-8 고정이 필요하다 — Windows 기본
        # 코드페이지(cp949)로 디코딩하면 출력 자체를 읽지 못한다.
        encoding="utf-8",
        errors="replace",
        cwd=REPO_ROOT,
        check=False,
    )
    assert result.returncode != 0, "위반이 통과했다 — banned-api가 작동하지 않는다"
    assert "TID251" in (result.stdout or "") + (result.stderr or "")
