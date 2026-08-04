"""배포 토폴로지 불변식 — compose 파일이 격리 규율을 실제로 구현하는가.

**왜 스냅샷 테스트인가**: 이 파일의 몇 줄은 보안 경계 그 자체다. `tools`에
`omra-db`를 마운트하는 한 줄이나 `litestream`의 `env_file`을 `.env`로 바꾸는
한 줄이 계약을 조용히 무너뜨린다 — import-linter는 프로세스를 넘지 못하므로
그 실수를 잡을 다른 수단이 없다.

정본: 설계 01 §7.1~§7.5 / 계획 01 §1.6 · §6.1 · §7
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE = REPO_ROOT / "docker-compose.yml"
DOCKERFILE = REPO_ROOT / "Dockerfile"


@pytest.fixture(scope="module")
def compose() -> dict[str, Any]:
    with COMPOSE.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    assert isinstance(data, dict)
    return data


@pytest.fixture(scope="module")
def services(compose: dict[str, Any]) -> dict[str, Any]:
    svc = compose["services"]
    assert isinstance(svc, dict)
    return svc


def _volume_targets(service: dict[str, Any]) -> set[str]:
    """`- source:target[:mode]` 표기에서 소스 이름만 뽑는다."""
    out: set[str] = set()
    for entry in service.get("volumes", []):
        out.add(str(entry).split(":", 1)[0])
    return out


def test_service_set_is_exactly_three(services: dict[str, Any]) -> None:
    """상시 2개 + 일회성 1개. 사이드카를 추가하는 것은 아키텍처 변경이다."""
    assert set(services) == {"app", "litestream", "tools"}


def test_no_docker_socket_is_mounted(services: dict[str, Any]) -> None:
    """`/var/run/docker.sock`을 어느 서비스에도 주지 않는다.

    autoheal 류 사이드카는 컨테이너 제어 권한을 얻는다 — 재시작 유발은
    봇 내부 워치독이 담당하며(설계 01 §4.5), 외부에 그 권한을 위임하지 않는다.
    """
    for name, svc in services.items():
        for entry in svc.get("volumes", []):
            assert "docker.sock" not in str(entry), f"{name} 이 docker.sock 을 마운트한다"


def test_excluded_stack_is_absent(services: dict[str, Any]) -> None:
    """Redis·메시지큐·PostgreSQL 이 없다 (계획 00 §5-1·§6.3 의도적 배제).

    주석이 아니라 **실제 서비스 정의**를 본다 — 배제 사실을 주석으로 적는 것은
    권장되며, 그것까지 위반으로 잡으면 문서화를 막는다.
    """
    banned = ("redis", "rabbitmq", "kafka", "postgres", "celery", "mongo")
    for name, svc in services.items():
        haystack = f"{name} {svc.get('image', '')}".lower()
        for word in banned:
            assert word not in haystack, f"의도적으로 배제한 스택: {name} ({word})"


@pytest.mark.parametrize("name", ["app", "litestream", "tools"])
def test_containers_are_hardened(services: dict[str, Any], name: str) -> None:
    """세 서비스 모두 non-root · read_only 다 (계획 01 §7-6).

    쓰기는 named volume 으로만 나간다 — 위반하면 즉시 크래시로 발견된다.
    """
    svc = services[name]
    assert svc["user"] == "1000:1000"
    assert svc["read_only"] is True


def test_app_is_the_only_writer_of_the_database(services: dict[str, Any]) -> None:
    """`omra-db` 볼륨은 app 과 litestream 만 본다. **tools 는 보지 못한다.**

    tools 에 DB를 주면 단일 라이터 전제가 깨지고, `:ro` 로 주면 WAL 리더의
    조건부 실패가 "가끔 되는 경로"를 검증 게이트에 들여놓는다. 마운트 자체를
    없애는 것이 그 선택지를 제거하는 방법이다 (계획 01 §1.6).
    """
    assert "omra-db" in _volume_targets(services["app"])
    assert "omra-db" in _volume_targets(services["litestream"])
    assert "omra-db" not in _volume_targets(services["tools"])


def test_tools_has_no_broker_credentials(services: dict[str, Any]) -> None:
    """tools 는 `.env.tools` 만 읽는다 — 브로커 자격증명이 없다.

    import-linter 는 프로세스를 넘지 못한다. app 의 `.env` 를 상속하면
    `labs -/-> brokers` 계약이 프로세스 경계에서 무효화된다.
    """
    assert services["tools"]["env_file"] == [".env.tools"]
    assert services["tools"]["environment"] == ["OMRA__RUNTIME__ROLE=tools"]


def test_litestream_reads_only_its_own_env(services: dict[str, Any]) -> None:
    """복제 프로세스에 주문 권한을 주지 않는다 (계획 01 §6.5)."""
    assert services["litestream"]["env_file"] == [".env.litestream"]


def test_tools_is_not_started_by_default(services: dict[str, Any]) -> None:
    """`profiles` 로 기본 up 대상에서 제외한다 — 상시 tools 는 없다."""
    assert services["tools"]["profiles"] == ["tools"]
    assert "restart" not in services["tools"]


def test_app_shutdown_budget_has_margin(services: dict[str, Any]) -> None:
    """`stop_grace_period` 40s = 내부 예산 30s + 마진 10s ([DD-01-5])."""
    assert services["app"]["stop_grace_period"] == "40s"
    assert services["app"]["init"] is True
    assert services["app"]["restart"] == "unless-stopped"


def test_healthcheck_uses_cli_and_is_observation_only(
    services: dict[str, Any],
) -> None:
    """healthcheck 는 loopback `/healthz` 를 조회하는 CLI 를 쓴다.

    프로세스 존재 확인으로 대체하지 않는 이유는 **이벤트 루프가 실제로
    응답하는지**를 검사하는 것이 목적이기 때문이다 (설계 01 §7.4).
    """
    hc = services["app"]["healthcheck"]
    assert hc["test"] == ["CMD", "python", "-m", "omra.cli", "health"]
    # unhealthy 가 재시작을 유발하지 않는다는 사실을 파일 주석으로 고정한다 —
    # compose 스키마에는 그 의미를 표현할 자리가 없다.
    raw = COMPOSE.read_text(encoding="utf-8")
    assert "관측 전용" in raw


def test_config_is_mounted_read_only(services: dict[str, Any]) -> None:
    """`config/` 는 사람이 편집하는 **입력물**이므로 컨테이너에 :ro 로 준다."""
    for name in ("app", "tools"):
        mounts = [str(v) for v in services[name]["volumes"]]
        assert "./config:/app/config:ro" in mounts, f"{name} 의 config 마운트가 :ro 가 아니다"


def test_output_volumes_are_separate_from_config(compose: dict[str, Any]) -> None:
    """산출물(`var/`)이 입력물(`config/`)과 물리적으로 분리된다 (계획 01 §6.1)."""
    assert set(compose["volumes"]) == {
        "omra-db",
        "omra-data",
        "omra-logs",
        "omra-policy",
    }


def test_image_tag_is_parameterized(services: dict[str, Any]) -> None:
    """`latest` 단일 태그를 쓰지 않는다 — 직전 이미지를 파괴한다 ([DD-01-10])."""
    for name in ("app", "tools"):
        assert services[name]["image"] == "omra:${OMRA_TAG:-dev}"


def test_stdout_log_rotation_is_capped(services: dict[str, Any]) -> None:
    """컨테이너 stdout 상한 ([DD-01-13]) — 파일 로그 로테이션과 별개다."""
    opts = services["app"]["logging"]["options"]
    assert opts["max-size"] == "50m"
    assert opts["max-file"] == "3"


def test_dockerfile_runs_as_non_root_with_cli_entrypoint() -> None:
    """이미지가 non-root 로 끝나고 CMD 가 계획 01 §1.6 호출 형식을 쓴다."""
    raw = DOCKERFILE.read_text(encoding="utf-8")
    assert "USER omra" in raw
    assert 'CMD ["python", "-m", "omra.cli", "run"]' in raw
    # UID/GID 는 compose 의 `user: "1000:1000"` 및 volume 소유권과 맞아야 한다.
    assert "useradd -u 1000 -g 1000" in raw


def test_dockerignore_excludes_secrets_and_tests() -> None:
    """빌드 컨텍스트에 시크릿·테스트가 들어가지 않는다."""
    raw = (REPO_ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
    for entry in (".env", "tests/", "var/", ".venv/"):
        assert entry in raw, f".dockerignore 에 {entry} 가 없다"


def test_env_examples_carry_no_values() -> None:
    """예시 파일에 실제 값이 들어 있지 않다.

    `.env.example` 이 실키를 담는 것은 시크릿 유출의 가장 흔한 경로다.
    """
    for name in (".env.example", ".env.litestream.example", ".env.tools.example"):
        for line in (REPO_ROOT / name).read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, _, value = stripped.partition("=")
            value = value.split("#", 1)[0].strip()
            allowed = {
                "OMRA_TAG": {"dev"},
                "OMRA_BIND_ADDR": {"127.0.0.1"},
                "SMTP_PORT": {"587"},
            }
            assert value in allowed.get(key.strip(), {""}), (
                f"{name} 의 {key} 에 값이 들어 있다: {value!r}"
            )
