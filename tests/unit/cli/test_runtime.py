"""CLI contracts for the M0 runtime and container readiness probe."""

import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
import pytest
import uvicorn
from typer.testing import CliRunner

from omra.cli import app
from omra.cli import runtime as runtime_cli

_ROOT = Path(__file__).resolve().parents[3]


def _transport(
    responder: Callable[[httpx.Request], httpx.Response],
) -> httpx.MockTransport:
    return httpx.MockTransport(responder)


def _report(status: str) -> dict[str, Any]:
    checks: list[dict[str, Any]] = [
        {"id": "config", "status": "pass", "code": None},
        {"id": "database", "status": "pass", "code": None},
        {"id": "schema", "status": "pass", "code": None},
        {"id": "volumes", "status": "pass", "code": None},
    ]
    if status == "not_ready":
        checks[0] = {
            "id": "config",
            "status": "fail",
            "code": "config_invalid",
        }
    return {
        "status": status,
        "checks": checks,
        "generated_at": "2026-08-19T00:00:00Z",
        "version": "0.1.0",
    }


def _inconsistent_report() -> dict[str, Any]:
    report = _report("ready")
    report["checks"][2] = {
        "id": "schema",
        "status": "fail",
        "code": "schema_revision_mismatch",
    }
    return report


@pytest.mark.parametrize(
    ("status_code", "payload", "expected"),
    [
        (200, _report("ready"), True),
        (200, _report("not_ready"), False),
        (503, _report("not_ready"), False),
        (503, _report("ready"), False),
        (200, _inconsistent_report(), False),
        (200, {"status": "ready"}, False),
    ],
)
def test_query_readiness_requires_both_http_and_schema_success(
    status_code: int,
    payload: dict[str, Any],
    expected: bool,
) -> None:
    transport = _transport(
        lambda request: httpx.Response(status_code, json=payload, request=request)
    )
    with httpx.Client(transport=transport) as client:
        assert runtime_cli.query_readiness(client, "http://127.0.0.1:8080/readyz") is expected


def test_query_readiness_bounds_connection_and_malformed_response_failures() -> None:
    def connection_error(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("secret host detail", request=request)

    with httpx.Client(transport=_transport(connection_error)) as client:
        assert not runtime_cli.query_readiness(client, "http://127.0.0.1:8080/readyz")

    with httpx.Client(
        transport=_transport(lambda request: httpx.Response(200, text="not-json", request=request))
    ) as client:
        assert not runtime_cli.query_readiness(client, "http://127.0.0.1:8080/readyz")


def test_ready_command_uses_strict_exit_codes(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = CliRunner()
    monkeypatch.setattr(runtime_cli, "query_readiness", lambda client, url: True)

    success = runner.invoke(app, ["ready"])

    assert success.exit_code == 0
    assert success.stdout == "ready\n"

    monkeypatch.setattr(runtime_cli, "query_readiness", lambda client, url: False)
    failure = runner.invoke(app, ["ready"])

    assert failure.exit_code == 1
    assert "not_ready" in failure.stderr
    assert failure.stdout == ""


def test_run_command_closes_bootstrap_context(monkeypatch: pytest.MonkeyPatch) -> None:
    events: list[object] = []

    class Readiness:
        def collect(self) -> None:
            return None

    class Context:
        readiness = Readiness()

        def close(self) -> None:
            events.append("closed")

    context = Context()
    application = object()
    monkeypatch.setattr(runtime_cli, "bootstrap", lambda paths, clock, version: context)
    monkeypatch.setattr(runtime_cli, "create_app", lambda collect: application)
    monkeypatch.setattr(
        uvicorn,
        "run",
        lambda application, host, port, access_log: events.append(
            (application, host, port, access_log)
        ),
    )
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "run",
            "--config-dir",
            str(Path("config")),
            "--db-path",
            str(Path("var/db/omra.sqlite")),
            "--data-dir",
            str(Path("var/data")),
            "--logs-dir",
            str(Path("var/logs")),
            "--policy-dir",
            str(Path("var/policy")),
            "--alembic-ini",
            str(Path("alembic.ini")),
        ],
    )

    assert result.exit_code == 0
    assert events == [(application, "0.0.0.0", 8080, False), "closed"]  # noqa: S104


def test_tools_cli_entrypoint_rejects_forbidden_credentials_before_help_parsing() -> None:
    raw_value = "must-never-appear"
    environment = os.environ.copy()
    environment.update(
        {
            "KIS_APP_KEY": raw_value,
            "OMRA__RUNTIME__ROLE": "tools",
            "PYTHONPATH": str(_ROOT / "src"),
        }
    )

    result = subprocess.run(
        [sys.executable, "-m", "omra.cli", "--help"],
        cwd=_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert "startup_failed:config.secret_placement" in result.stderr
    assert raw_value not in result.stdout
    assert raw_value not in result.stderr
