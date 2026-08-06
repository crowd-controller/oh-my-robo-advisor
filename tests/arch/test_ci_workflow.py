"""CI 워크플로 불변식 — 잡 구성과 시크릿 노출 금지를 검사한다.

**왜 검사하는가**: CI가 무엇을 검사하는지는 CI 자신이 검사하지 않는다. 잡이
빠지거나 마커가 어긋나면 그 계층은 **아무도 실행하지 않은 채 머지된다**.
그리고 워크플로에 브로커 시크릿이 한 번 들어가면 fork PR·로그·써드파티
액션까지 노출 표면이 된다 — 되돌릴 수 없는 종류의 실수다.

검증 항목: V16-29 · V16-30
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"

# M0 시점에 활성인 잡. 나머지(J5~J9·J11)는 해당 구현 단위에서 켠다 —
# 켜는 시점이 흐려지지 않도록 여기에 목록을 고정한다.
ACTIVE_JOBS: frozenset[str] = frozenset(
    {"j1-lint", "j2-typecheck", "j3-arch", "j4-unit", "j10-supply-chain"}
)

# 이 문자열이 워크플로에 등장하면 브로커 자격증명이 노출된 것이다.
BROKER_SECRET_MARKERS: tuple[str, ...] = (
    "KIS_APP_KEY",
    "KIS_APP_SECRET",
    "KIS_PAPER_APP_KEY",
    "KIS_PAPER_APP_SECRET",
    "UPBIT_ACCESS_KEY",
    "UPBIT_SECRET_KEY",
    "TELEGRAM_BOT_TOKEN",
    "SMTP_PASSWORD",
    "ANTHROPIC_API_KEY",
    "OMRA_TEST_LIVE",
)


@pytest.fixture(scope="module")
def workflow() -> dict[str, Any]:
    with WORKFLOW.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    assert isinstance(data, dict)
    return data


@pytest.fixture(scope="module")
def jobs(workflow: dict[str, Any]) -> dict[str, Any]:
    j = workflow["jobs"]
    assert isinstance(j, dict)
    return j


def test_active_job_set_is_exactly_as_declared(jobs: dict[str, Any]) -> None:
    """활성 잡 집합이 선언과 정확히 일치한다.

    잡을 늘리거나 줄이는 것은 "무엇을 검사하는가"의 변경이므로 조용히
    일어나서는 안 된다.
    """
    assert set(jobs) == ACTIVE_JOBS, (
        f"누락: {sorted(ACTIVE_JOBS - set(jobs))} / 초과: {sorted(set(jobs) - ACTIVE_JOBS)}"
    )


def _all_scalars(node: object) -> list[str]:
    """파싱된 YAML 트리의 모든 스칼라를 평탄화한다.

    원문이 아니라 **파싱 결과**를 보는 이유: 워크플로 주석에 "이 시크릿을
    쓰지 않는다"고 적는 것은 권장되는 문서화인데, 원문 검색은 그 주석까지
    위반으로 잡아 문서화를 막는다.
    """
    if isinstance(node, dict):
        out: list[str] = []
        for k, v in node.items():
            out.append(str(k))
            out.extend(_all_scalars(v))
        return out
    if isinstance(node, list):
        return [s for item in node for s in _all_scalars(item)]
    return [str(node)]


def test_no_broker_credentials_in_workflow(workflow: dict[str, Any]) -> None:
    """V16-29 — 워크플로에 브로커 자격증명 참조가 0건이다.

    `OMRA_TEST_LIVE` 도 금지 목록에 있다. 그 변수가 없으면 `record` 와
    `gate_evidence` 마커가 **물리적으로 skip** 되므로, 실호출 경로가 CI에서
    열릴 수 없다(16 §2.2).
    """
    haystack = "\n".join(_all_scalars(workflow))
    for marker in BROKER_SECRET_MARKERS:
        assert marker not in haystack, f"워크플로에 {marker} 가 등장한다"
    # GitHub 표현식 문법으로만 검사한다 — `scan_cassette_secrets.py` 같은
    # 파일명이 오탐되면 테스트가 의미를 잃는다.
    assert "secrets." not in haystack.replace("_secrets.", "_"), (
        "워크플로가 GitHub Secrets 를 참조한다"
    )


def test_hypothesis_profile_is_ci(workflow: dict[str, Any]) -> None:
    """CI 프로파일은 `derandomize=True` 다 — R5 롤백 판정의 전제.

    재현되지 않는 property 실패는 롤백 판정 자체를 불가능하게 만든다
    (계획 07 §10.1).
    """
    assert workflow["env"]["HYPOTHESIS_PROFILE"] == "ci"


def test_network_is_declared_blocked(workflow: dict[str, Any]) -> None:
    """`OMRA_TEST_NETWORK=blocked` 를 선언한다 (16 §11.2)."""
    assert workflow["env"]["OMRA_TEST_NETWORK"] == "blocked"


def test_lockfile_is_frozen(workflow: dict[str, Any]) -> None:
    """`UV_FROZEN=1` — lockfile 고정 (계획 01 §7-7).

    CI가 lock 을 갱신하면 "CI에서만 되는 조합"이 생긴다.
    """
    assert workflow["env"]["UV_FROZEN"] == "1"


def test_concurrency_cancels_stale_runs(workflow: dict[str, Any]) -> None:
    assert workflow["concurrency"]["cancel-in-progress"] is True


def _steps_text(job: dict[str, Any]) -> str:
    return "\n".join(
        str(step.get("run", "")) + " " + str(step.get("uses", "")) for step in job["steps"]
    )


def test_j1_runs_both_lint_and_format_check(jobs: dict[str, Any]) -> None:
    """포맷 검사를 빼면 포맷 차이가 diff 노이즈로 누적된다."""
    text = _steps_text(jobs["j1-lint"])
    assert "ruff check ." in text
    assert "ruff format --check ." in text


def test_j1_validates_compose_topology(jobs: dict[str, Any]) -> None:
    """compose 가 실제로 파싱되는지 CI에서 확인한다.

    불변식 자체(볼륨·env_file·non-root)는 J3의 아키텍처 테스트가 본다 —
    여기서는 "문법이 맞는가"만 본다.
    """
    assert "docker compose config" in _steps_text(jobs["j1-lint"])


def test_j3_runs_import_linter_and_arch_marker(jobs: dict[str, Any]) -> None:
    text = _steps_text(jobs["j3-arch"])
    assert "lint-imports" in text
    assert "pytest -m arch" in text


def test_j4_runs_unit_and_property_markers(jobs: dict[str, Any]) -> None:
    """마커로 선택 실행한다 — 마커가 빠진 테스트는 여기서 실행되지 않는다."""
    assert 'pytest -m "unit or property"' in _steps_text(jobs["j4-unit"])


def test_j4_depends_on_static_gates(jobs: dict[str, Any]) -> None:
    """정적 게이트가 먼저 돈다 — 타입 오류 위에서 로직 테스트를 돌리지 않는다."""
    assert set(jobs["j4-unit"]["needs"]) == {"j1-lint", "j2-typecheck", "j3-arch"}


def test_j10_checks_lock_and_audits_dependencies(jobs: dict[str, Any]) -> None:
    """공급망 — lock 정합 + 취약점 감사. **자동 업데이트 PR은 만들지 않는다.**"""
    text = _steps_text(jobs["j10-supply-chain"])
    assert "uv lock --check" in text
    assert "uv export --frozen --all-groups --no-emit-project" in text
    assert "pip-audit --strict --requirement" in text
    assert "dependabot" not in text.lower()


@pytest.mark.parametrize("name", sorted(ACTIVE_JOBS))
def test_every_job_has_a_timeout(jobs: dict[str, Any], name: str) -> None:
    """타임아웃 없는 잡은 러너를 무한 점유한다."""
    assert isinstance(jobs[name].get("timeout-minutes"), int)


def test_deferred_jobs_are_documented() -> None:
    """아직 켜지 않은 잡의 활성화 시점이 파일에 적혀 있다.

    "나중에 켠다"가 기록되지 않으면 영원히 켜지지 않는다.
    """
    raw = WORKFLOW.read_text(encoding="utf-8")
    for job in ("J5", "J6", "J7", "J8", "J9", "J11"):
        assert job in raw, f"{job} 의 활성화 시점이 문서화되지 않았다"
