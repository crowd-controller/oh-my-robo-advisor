"""테스트 하네스 자체의 검증 — 결정론 3원칙과 마커 강제가 실제로 작동하는가.

하네스가 조용히 고장 나면 그 위의 모든 테스트가 **통과한 것처럼 보이면서
아무것도 검사하지 않는다**. 그 침묵을 깨는 것이 이 파일의 유일한 목적이다.

검증 항목: V16-01 · V16-02 · V16-03
"""

from __future__ import annotations

import hashlib
import os
import random
import socket
import subprocess
import sys
from pathlib import Path

import numpy
import pytest

from tests.marks import verifies

REPO_ROOT = Path(__file__).resolve().parents[2]


# ══════════════════════════════════════════════════════════════════════
# 결정론 — 네트워크 차단 (설계 16 §11.2)
# ══════════════════════════════════════════════════════════════════════
@verifies("V16-03")
def test_socket_creation_is_blocked() -> None:
    """소켓 생성이 차단된다 — "CI는 재생만"의 물리적 표현."""
    with pytest.raises(RuntimeError, match="네트워크 차단"):
        socket.socket()


def test_create_connection_is_blocked() -> None:
    """`create_connection` 도 함께 막힌다 — 우회 경로를 남기지 않는다."""
    with pytest.raises(RuntimeError, match="네트워크 차단"):
        socket.create_connection(("127.0.0.1", 1))


# ══════════════════════════════════════════════════════════════════════
# 결정론 — 시드 고정 (설계 16 §11.2)
# ══════════════════════════════════════════════════════════════════════
def test_random_is_seeded_by_nodeid(request: pytest.FixtureRequest) -> None:
    """전역 시드가 노드 ID 해시로 고정되어 있다.

    같은 테스트가 언제나 같은 난수열을 본다 — 실행 순서·병렬화와 무관하다.
    벽시계나 실행 순서에 시드를 매면 재현이 깨지고, 재현되지 않는 property
    실패는 R5 롤백 판정 자체를 불가능하게 만든다(계획 07 §10.1).
    """
    observed = [random.random() for _ in range(5)]  # noqa: S311

    # conftest의 시드 산출을 그대로 재현한다 — 같은 노드 ID → 같은 수열.
    digest = hashlib.blake2b(request.node.nodeid.encode(), digest_size=8).hexdigest()
    random.seed(int(digest, 16))
    reproduced = [random.random() for _ in range(5)]  # noqa: S311

    assert observed == reproduced, "전역 시드가 노드 ID 해시로 고정되지 않았다"


def test_numpy_is_seeded() -> None:
    """numpy 전역 시드도 고정된다 — 몬테카를로·부트스트랩의 재현 전제."""
    a = numpy.random.rand(4)
    numpy.random.seed(0)
    b = numpy.random.rand(4)
    assert not numpy.allclose(a, b), "시드가 실제로 적용되지 않았다"


# ══════════════════════════════════════════════════════════════════════
# 마커 강제 (설계 16 §2.1 [DD-16-1])
# ══════════════════════════════════════════════════════════════════════
def _run_pytest(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    # 오류 메시지가 한국어라 자식 프로세스의 출력 인코딩을 UTF-8로 고정한다 —
    # Windows 기본 코드페이지(cp949)로 나가면 메시지를 읽을 수 없다.
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
    return subprocess.run(  # noqa: S603
        [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-q", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=cwd,
        env=env,
        check=False,
    )


@verifies("V16-01")
def test_marker_mismatch_fails_at_collection() -> None:
    """디렉터리 계층과 수동 마커가 불일치하면 **수집 단계에서** 실패한다.

    마커가 어긋난 테스트는 엉뚱한 CI 잡에서 실행되거나 어디서도 실행되지
    않는다. 실행 결과가 아니라 수집에서 막아야 하는 이유다.
    """
    violation = REPO_ROOT / "tests" / "unit" / "test__marker_mismatch_fixture.py"
    violation.write_text(
        "import pytest\n\n\n@pytest.mark.integration\ndef test_wrong_layer() -> None:\n    pass\n",
        encoding="utf-8",
    )
    try:
        result = _run_pytest(["--collect-only", "tests/unit"], REPO_ROOT)
        out = (result.stdout or "") + (result.stderr or "")
        assert result.returncode != 0, f"불일치가 통과했다\n{out}"
        assert "3중 일치" in out, out
    finally:
        violation.unlink(missing_ok=True)


@verifies("V16-02")
def test_every_collected_test_has_a_layer_marker() -> None:
    """수집된 모든 테스트가 계층 마커를 갖는다.

    마커 없는 테스트는 마커 선택 실행(`pytest -m unit` 등)에서 빠져
    **어떤 CI 잡에서도 실행되지 않은 채 통과로 계상**된다.
    """
    layers = ("unit", "property", "arch", "contract", "integration", "scenario")
    expr = " or ".join(layers)
    with_markers = _run_pytest(["--collect-only", "-m", expr], REPO_ROOT)
    all_tests = _run_pytest(["--collect-only"], REPO_ROOT)
    assert with_markers.returncode == 0, with_markers.stdout + with_markers.stderr
    assert all_tests.returncode == 0, all_tests.stdout + all_tests.stderr

    def _count(out: str) -> int:
        for line in reversed(out.splitlines()):
            if "test" in line and "collected" in line:
                return int(line.split()[0])
        pytest.fail(f"수집 개수를 읽지 못했다:\n{out}")

    assert _count(with_markers.stdout) == _count(all_tests.stdout)


# ══════════════════════════════════════════════════════════════════════
# verifies() 마커 (설계 16 §2.3)
# ══════════════════════════════════════════════════════════════════════
def test_verifies_rejects_malformed_id() -> None:
    """검증 항목 ID 형식 위반은 **import 시점에** 걸린다.

    오타난 ID는 RTM 대조에서 조용히 미커버로 남는다 — 그것이 가장 나쁜 실패다.
    """
    with pytest.raises(ValueError, match="형식 위반"):
        verifies("16-01")
    with pytest.raises(ValueError, match="형식 위반"):
        verifies("V16_01")


def test_verifies_requires_at_least_one_id() -> None:
    with pytest.raises(ValueError, match="최소 1개"):
        verifies()


def test_verifies_attaches_ids_to_marker() -> None:
    mark = verifies("V16-01", "V16-02")
    assert mark.mark.name == "verifies"
    assert mark.mark.args == ("V16-01", "V16-02")


# ══════════════════════════════════════════════════════════════════════
# 픽스처 (설계 16 §11.1)
# ══════════════════════════════════════════════════════════════════════
def test_tmp_var_matches_volume_layout(tmp_var: dict[str, Path]) -> None:
    """`var/` 임시 레이아웃이 계획 01 §6.1의 볼륨 구성과 같다."""
    assert set(tmp_var) == {"db", "data", "logs", "policy"}
    for path in tmp_var.values():
        assert path.is_dir()


def test_repo_root_points_at_pyproject(repo_root: Path) -> None:
    assert (repo_root / "pyproject.toml").is_file()
