"""HTTP readiness boundary contracts."""

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from omra.monitoring.readiness import (
    CheckStatus,
    ReadinessCheck,
    ReadinessReport,
)
from omra.web.app import create_app


def _report(*, ready: bool) -> ReadinessReport:
    config_check = (
        ReadinessCheck(id="config", status=CheckStatus.OK)
        if ready
        else ReadinessCheck(
            id="config",
            status=CheckStatus.FAIL,
            code="config_invalid",
        )
    )
    return ReadinessReport.from_checks(
        checks=(
            config_check,
            ReadinessCheck(id="database", status=CheckStatus.OK),
            ReadinessCheck(id="schema", status=CheckStatus.OK),
            ReadinessCheck(id="volumes", status=CheckStatus.OK),
        ),
        generated_at=datetime(2026, 8, 19, tzinfo=UTC),
        version="0.1.0",
    )


def test_readyz_returns_200_only_for_a_ready_report() -> None:
    client = TestClient(create_app(lambda: _report(ready=True)))

    response = client.get("/readyz")

    assert response.status_code == 200
    assert ReadinessReport.model_validate(response.json()).status.value == "ready"


def test_readyz_returns_503_with_the_bounded_failure_report() -> None:
    client = TestClient(create_app(lambda: _report(ready=False)))

    response = client.get("/readyz")

    assert response.status_code == 503
    assert response.json()["checks"][0] == {
        "id": "config",
        "status": "fail",
        "code": "config_invalid",
    }
    assert len(response.json()["checks"]) == 4


def test_m0_app_does_not_impersonate_the_final_operational_health_route() -> None:
    client = TestClient(create_app(lambda: _report(ready=True)))

    response = client.get("/healthz")

    assert response.status_code == 404
