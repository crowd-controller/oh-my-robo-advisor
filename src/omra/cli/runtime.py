"""Typer commands for the M0 process shell and readiness probe."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import httpx
import typer
import uvicorn
from pydantic import ValidationError

from omra import __version__
from omra.core import SystemClock
from omra.monitoring.readiness import ReadinessReport, ReadinessStatus
from omra.runtime.bootstrap import BootstrapError, RuntimePaths, bootstrap
from omra.web.app import create_app

_READY_URL = "http://127.0.0.1:8080/readyz"
_HTTP_OK = 200


def query_readiness(client: httpx.Client, url: str) -> bool:
    """Return true only for a valid HTTP 200 ready report."""
    try:
        response = client.get(url)
        if response.status_code != _HTTP_OK:
            return False
        report = ReadinessReport.model_validate(response.json())
    except (httpx.HTTPError, ValidationError, ValueError):
        return False
    return report.status is ReadinessStatus.READY


def register_runtime_commands(application: typer.Typer) -> None:
    """Attach M0 lifecycle commands to the canonical CLI."""

    @application.command("ready")
    def ready_command(
        url: Annotated[
            str,
            typer.Option(help="Loopback readiness URL."),
        ] = _READY_URL,
        timeout: Annotated[
            float,
            typer.Option(min=0.1, help="Readiness timeout in seconds."),
        ] = 5.0,
    ) -> None:
        """Exit zero only when the local M0 readiness contract passes."""
        with httpx.Client(timeout=timeout) as client:
            is_ready = query_readiness(client, url)
        if not is_ready:
            typer.echo("not_ready", err=True)
            raise typer.Exit(code=1)
        typer.echo("ready")

    @application.command("run")
    def run_command(  # noqa: PLR0917 - explicit operator-controlled paths
        config_dir: Annotated[Path, typer.Option()] = Path("/app/config"),
        db_path: Annotated[Path, typer.Option()] = Path("/app/var/db/omra.sqlite"),
        data_dir: Annotated[Path, typer.Option()] = Path("/app/var/data"),
        logs_dir: Annotated[Path, typer.Option()] = Path("/app/var/logs"),
        policy_dir: Annotated[Path, typer.Option()] = Path("/app/var/policy"),
        alembic_ini: Annotated[Path, typer.Option()] = Path("/app/alembic.ini"),
        host: Annotated[str, typer.Option()] = "0.0.0.0",  # noqa: S104
        port: Annotated[int, typer.Option(min=1, max=65535)] = 8080,
    ) -> None:
        """Validate local prerequisites and serve the M0 readiness endpoint."""
        paths = RuntimePaths(
            config_dir=config_dir,
            db_path=db_path,
            data_dir=data_dir,
            logs_dir=logs_dir,
            policy_dir=policy_dir,
            alembic_ini=alembic_ini,
        )
        try:
            context = bootstrap(paths, clock=SystemClock(), version=__version__)
        except BootstrapError as error:
            typer.echo(f"startup_failed:{error.code}", err=True)
            raise typer.Exit(code=1) from error

        try:
            web_application = create_app(context.readiness.collect)
            uvicorn.run(
                web_application,
                host=host,
                port=port,
                access_log=False,
            )
        finally:
            context.close()


__all__ = ["query_readiness", "register_runtime_commands"]
