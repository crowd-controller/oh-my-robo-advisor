"""전역 테스트 픽스처 — 결정론 3원칙과 계층·마커 강제.

**왜 전역 autouse인가**: 규약으로만 두면 언젠가 실호출 테스트가 섞이고, 시드
없는 난수가 "가끔 실패하는 테스트"를 만든다. 계획 07 §10.1의 롤백 트리거 R5는
property-based 실패 1건으로 즉시 발동하는데, **재현되지 않는 실패는 롤백 판정
자체를 불가능하게 만든다**. 결정론은 편의가 아니라 판정의 전제다.

정본: 설계 16 §2.1 [DD-16-1] · §4.3 · §11.2 [DD-16-11]
"""

from __future__ import annotations

import hashlib
import os
import random
import socket
from datetime import timedelta
from pathlib import Path

import numpy
import pytest
from hypothesis import HealthCheck, settings

# ── 계층 ↔ 디렉터리 1:1 매핑 (설계 16 §2.2 계층 정의 표) ──────────────
# 마커가 빠진 테스트는 **어떤 CI 잡에서도 실행되지 않은 채 조용히 통과**한다.
# 정확히 계획 01 §2.2가 경고한 default-allow와 같은 실패 모드다.
LAYER_BY_DIR: dict[str, str] = {
    "unit": "unit",
    "property": "property",
    "arch": "arch",
    "contract": "contract",
    "integration": "integration",
    "scenario": "scenario",
    "gates": "backtest_gate",
}

# 디렉터리로 계층이 결정되지 않는 보조 디렉터리 — 마커를 손으로 붙인다.
UNMANAGED_DIRS: frozenset[str] = frozenset({"rtm", "cassettes", "golden", "data"})

TESTS_ROOT = Path(__file__).parent


# ══════════════════════════════════════════════════════════════════════
# hypothesis 프로파일 (설계 16 §4.3)
# ══════════════════════════════════════════════════════════════════════
settings.register_profile("dev", max_examples=50, deadline=timedelta(seconds=1))
settings.register_profile(
    "ci",
    max_examples=300,
    deadline=None,
    # 재현성 — R5(계획 07 §10.1)가 property 실패 1건으로 롤백을 규정하므로
    # 재현되지 않는 실패는 판정 불가다.
    derandomize=True,
    suppress_health_check=[HealthCheck.too_slow],
)
settings.register_profile("nightly", max_examples=2000, deadline=None)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "dev"))


# ══════════════════════════════════════════════════════════════════════
# 계층 ↔ 마커 3중 일치 강제 (설계 16 §2.1 [DD-16-1])
# ══════════════════════════════════════════════════════════════════════
def _layer_of(item: pytest.Item) -> str | None:
    """테스트 파일 경로에서 계층을 판정한다."""
    try:
        rel = Path(str(item.fspath)).resolve().relative_to(TESTS_ROOT.resolve())
    except ValueError:
        return None
    if not rel.parts:
        return None
    top = rel.parts[0]
    if top in UNMANAGED_DIRS:
        return None
    return LAYER_BY_DIR.get(top)


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """경로 기반으로 계층 마커를 자동 부여하고, 수동 마커와의 불일치를 거부한다.

    V16-01 — 디렉터리와 마커가 불일치하는 테스트는 **수집 단계에서 실패**한다.
    V16-02 — 마커 없는 테스트 0건.
    """
    del config
    unmarked: list[str] = []
    for item in items:
        layer = _layer_of(item)
        own = {m.name for m in item.iter_markers()} & set(LAYER_BY_DIR.values())
        if layer is None:
            if not own:
                unmarked.append(item.nodeid)
            continue
        if own and own != {layer}:
            raise pytest.UsageError(
                f"{item.nodeid}: 디렉터리 계층은 '{layer}'인데 마커는 {sorted(own)}이다 "
                "(설계 16 §2.1 — 디렉터리·마커·CI 잡 3중 일치)"
            )
        if not own:
            item.add_marker(getattr(pytest.mark, layer))
    if unmarked:
        raise pytest.UsageError(
            "계층 마커가 없는 테스트가 있다 — 어떤 CI 잡에서도 실행되지 않는다:\n  "
            + "\n  ".join(unmarked)
        )


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "allow_socket: 소켓 차단 예외. record 마커와만 조합 가능하다 (16 §11.2)",
    )


# ══════════════════════════════════════════════════════════════════════
# 결정론 3원칙 (설계 16 §11.2 [DD-16-11])
# ══════════════════════════════════════════════════════════════════════
@pytest.fixture(autouse=True)
def _no_network(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    """소켓 생성을 차단한다.

    "CI는 재생만"(계획 03 §4.2)을 규약으로만 두면 언젠가 실호출 테스트가 섞인다.
    소켓 차단은 그 규약의 물리적 표현이며, 동시에 **카세트 매칭 실패가 조용히
    실호출로 대체되는 경로**를 봉인한다.
    """
    if request.node.get_closest_marker("allow_socket"):
        assert request.node.get_closest_marker("record"), (
            "allow_socket은 record 마커와만 조합할 수 있다 (16 §11.2)"
        )
        return

    def _blocked(*_a: object, **_k: object) -> None:
        raise RuntimeError("네트워크 차단 — 카세트를 쓰거나 record 마커를 붙여라 (설계 16 §11.2)")

    monkeypatch.setattr(socket, "socket", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)


@pytest.fixture(autouse=True)
def _seeded(request: pytest.FixtureRequest) -> None:
    """전역 시드를 **테스트 노드 ID 해시**로 고정한다.

    실행 순서·병렬화와 무관하게 같은 테스트가 언제나 같은 시드를 받는다.
    벽시계나 실행 순서에 시드를 매면 재현이 깨진다.
    """
    digest = hashlib.blake2b(request.node.nodeid.encode(), digest_size=8).hexdigest()
    seed = int(digest, 16)
    random.seed(seed)
    numpy.random.seed(seed % (2**32))


# ══════════════════════════════════════════════════════════════════════
# 골든 파일 갱신 옵션 (설계 16 §11.4)
# ══════════════════════════════════════════════════════════════════════
def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--golden-update",
        action="store_true",
        default=False,
        help="골든 파일을 갱신한다. CI에서는 거부된다 (16 §11.4).",
    )


@pytest.fixture(scope="session")
def golden_update(request: pytest.FixtureRequest) -> bool:
    """골든 갱신 여부. CI 환경에서는 사용 자체를 거부한다.

    갱신이 CI에서 가능하면 "기준값이 스스로를 승인하는" 구조가 되어 스냅샷
    회귀 게이트가 무의미해진다.
    """
    enabled = bool(request.config.getoption("--golden-update"))
    if enabled and os.environ.get("CI"):
        raise pytest.UsageError(
            "--golden-update는 CI에서 쓸 수 없다 — 갱신은 사람이 diff를 보고 한다 (16 §11.4)"
        )
    return enabled


@pytest.fixture
def repo_root() -> Path:
    """저장소 루트. 설계서·설정 파일을 읽는 대조 테스트가 쓴다."""
    return TESTS_ROOT.parent


@pytest.fixture
def tmp_var(tmp_path: Path) -> dict[str, Path]:
    """`var/` 볼륨 레이아웃의 임시 복제본 (db/data/logs/policy).

    경로 규약은 계획 01 §6.1이 정본이다 — 입력물(`config/`)과 산출물(`var/`)의
    분리를 테스트에서도 지킨다.
    """
    layout: dict[str, Path] = {}
    for name in ("db", "data", "logs", "policy"):
        p = tmp_path / "var" / name
        p.mkdir(parents=True)
        layout[name] = p
    return layout


def pytest_report_header(config: pytest.Config) -> list[str]:
    del config
    profile = os.environ.get("HYPOTHESIS_PROFILE", "dev")
    return [f"omra: hypothesis profile={profile}, network=blocked, seed=nodeid-hash"]
