"""Static production contracts for Docker, Compose, and Litestream."""

from pathlib import Path
from typing import Any

import yaml

_ROOT = Path(__file__).resolve().parents[2]
_PYTHON_IMAGE = (
    "python:3.12.13-slim-bookworm"
    "@sha256:4766d8b510c428e595d74b9cc5bbb2fae8e26316fffb4adc89908d79aacd58a2"
)
_UV_IMAGE = (
    "ghcr.io/astral-sh/uv:0.12.5"
    "@sha256:e85be844203885286c60ffad8a858d48afb6c5a5c237ca0e67f12e74b8f174b1"
)
_LITESTREAM_IMAGE = (
    "litestream/litestream:0.5.16"
    "@sha256:f085f8bce71a5ad4ce8e28b28ea522de1d9e0d7dd0af3ea5c1bd626d0f341954"
)


def _yaml(path: str) -> dict[str, Any]:
    rendered = (_ROOT / path).read_text(encoding="utf-8")
    parseable = rendered.replace("!reset []", "[]")
    value = yaml.safe_load(parseable)
    assert isinstance(value, dict)
    return value


def _volume_targets(service: dict[str, Any]) -> set[str]:
    targets: set[str] = set()
    for volume in service.get("volumes", []):
        if isinstance(volume, str):
            parts = volume.split(":")
            assert len(parts) >= 2
            targets.add(parts[1])
        else:
            targets.add(volume["target"])
    return targets


def test_dockerfile_pins_multiarch_inputs_and_runs_without_root() -> None:
    dockerfile = (_ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert f"ARG PYTHON_IMAGE={_PYTHON_IMAGE}" in dockerfile
    assert f"ARG UV_IMAGE={_UV_IMAGE}" in dockerfile
    assert dockerfile.count("@sha256:") == 2
    assert "latest" not in dockerfile
    assert "uv sync --locked --no-dev --no-install-project" in dockerfile
    assert "uv sync --locked --no-dev --no-editable" in dockerfile
    assert "USER 1000:1000" in dockerfile
    assert 'CMD ["python", "-m", "omra.cli", "run"]' in dockerfile
    assert "apt-get" not in dockerfile


def test_dockerignore_excludes_local_state_credentials_and_tooling() -> None:
    patterns = {
        line.strip()
        for line in (_ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }

    assert {".git", ".venv", ".env*", "var", ".omx", ".pytest_cache", "__pycache__"} <= patterns


def test_compose_enforces_three_service_least_privilege_topology() -> None:
    compose = _yaml("compose.yaml")
    assert compose["name"] == "omra"
    services = compose["services"]
    assert set(services) == {"app", "litestream", "tools"}

    for service in services.values():
        assert service["user"] == "1000:1000"
        assert service["read_only"] is True
        assert service["cap_drop"] == ["ALL"]
        assert service["security_opt"] == ["no-new-privileges:true"]
        assert service["tmpfs"]
        assert service["logging"]["options"] == {"max-size": "50m", "max-file": "3"}

    app = services["app"]
    assert app["init"] is True
    assert app["restart"] == "unless-stopped"
    assert app["stop_grace_period"] == "45s"
    assert app["env_file"] == [{"path": ".env", "required": False}]
    assert app["environment"] == {"OMRA__RUNTIME__ROLE": "app"}
    assert app["ports"] == ["${OMRA_BIND_ADDRESS:-127.0.0.1}:${OMRA_PORT:-8080}:8080"]
    assert app["healthcheck"] == {
        "test": ["CMD", "python", "-m", "omra.cli", "ready"],
        "interval": "60s",
        "timeout": "10s",
        "retries": 3,
        "start_period": "30s",
    }
    assert _volume_targets(app) == {
        "/app/config",
        "/app/var/db",
        "/app/var/data",
        "/app/var/logs",
        "/app/var/policy",
    }

    litestream = services["litestream"]
    assert litestream["image"] == _LITESTREAM_IMAGE
    assert litestream["restart"] == "unless-stopped"
    assert litestream["stop_grace_period"] == "45s"
    assert litestream["command"] == ["replicate", "-config", "/etc/litestream.yml"]
    assert litestream["env_file"] == [{"path": ".env.litestream", "required": False}]
    assert litestream["depends_on"] == {"app": {"condition": "service_healthy"}}
    assert _volume_targets(litestream) == {"/app/var/db", "/etc/litestream.yml"}

    tools = services["tools"]
    assert tools["profiles"] == ["tools"]
    assert tools["env_file"] == [{"path": ".env.tools", "required": False}]
    assert tools["environment"] == {"OMRA__RUNTIME__ROLE": "tools"}
    assert "entrypoint" not in tools
    assert tools["command"] == ["python", "-m", "omra.cli", "--help"]
    assert "/app/var/db" not in _volume_targets(tools)
    assert _volume_targets(tools) == {
        "/app/config",
        "/app/var/data",
        "/app/var/logs",
    }
    assert "ports" not in tools
    assert "restart" not in tools


def test_litestream_v05_uses_one_replica_and_global_snapshot_retention() -> None:
    config = _yaml("config/litestream.yml")
    rendered = (_ROOT / "config" / "litestream.yml").read_text(encoding="utf-8")

    assert "replicas:" not in rendered
    assert config["snapshot"] == {"interval": "24h", "retention": "720h"}
    assert config["retention"] == {"enabled": True}
    assert config["validation"] == {"interval": "1h"}
    assert config["dbs"] == [
        {
            "path": "/app/var/db/omra.sqlite",
            "replica": {
                "url": "${LITESTREAM_REPLICA_URL}",
                "sync-interval": "1s",
            },
        }
    ]

    smoke = _yaml("config/litestream.smoke.yml")
    assert smoke["dbs"][0]["replica"] == {
        "type": "file",
        "path": "/replica/omra",
        "sync-interval": "1s",
    }


def test_compose_smoke_override_uses_only_a_local_file_replica() -> None:
    rendered = (_ROOT / "compose.smoke.yaml").read_text(encoding="utf-8")
    smoke = _yaml("compose.smoke.yaml")
    app = smoke["services"]["app"]
    litestream = smoke["services"]["litestream"]

    assert rendered.count("env_file: !reset []") == 2
    assert app["env_file"] == []
    assert litestream["env_file"] == []
    assert "./config/litestream.smoke.yml:/etc/litestream.yml:ro" in litestream["volumes"]
    assert "./var/smoke/replica:/replica" in litestream["volumes"]
    assert "s3" not in rendered.lower()


def test_only_example_env_files_are_trackable_and_contain_placeholders() -> None:
    gitignore = (_ROOT / ".gitignore").read_text(encoding="utf-8")
    assert ".env.*" in gitignore
    assert "!.env.*.example" in gitignore

    app_env = (_ROOT / ".env.example").read_text(encoding="utf-8")
    litestream_env = (_ROOT / ".env.litestream.example").read_text(encoding="utf-8")
    tools_env = (_ROOT / ".env.tools.example").read_text(encoding="utf-8")

    assert "OMRA_BIND_ADDRESS=127.0.0.1" in app_env
    assert "LITESTREAM_REPLICA_URL=s3://CHANGE_ME/omra-db" in litestream_env
    assert "KIS_" not in tools_env
    assert "BROKER" not in tools_env
    assert "CHANGE_ME" in litestream_env


def test_container_smoke_script_is_bounded_restores_and_cleans_up() -> None:
    script_path = _ROOT / "scripts" / "container_smoke.sh"
    script = script_path.read_text(encoding="utf-8")

    assert "config --quiet" in script
    assert "config --format json" in script
    assert "credential environment leaked into smoke compose" in script
    assert "set -eu" in script
    assert "trap cleanup EXIT INT TERM" in script
    assert "--project-name omra-smoke" in script
    assert "config --quiet" in script
    assert "up --detach --wait --wait-timeout 180 app litestream" in script
    assert "replicate -config /etc/litestream.yml -once -force-snapshot" in script
    assert "restore -config /etc/litestream.yml -integrity-check full" in script
    assert "smoke-sentinel" in script
    assert "down --volumes --remove-orphans" in script
