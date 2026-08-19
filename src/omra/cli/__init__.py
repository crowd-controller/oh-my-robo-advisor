"""Command-line composition boundary."""

import os
from typing import Annotated

import typer
from pydantic import ValidationError

from omra import __version__
from omra.cli.runtime import register_runtime_commands
from omra.config import ConfigError, ExecEnv, Secrets, check_credential_placement

_RUNTIME_ROLE_ENV = "OMRA__RUNTIME__ROLE"

app = typer.Typer(
    name="omra",
    help="Oh My Robo Advisor operations CLI.",
    no_args_is_help=True,
    pretty_exceptions_enable=False,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit


@app.callback()
def main(
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            callback=_version_callback,
            is_eager=True,
            help="Show the installed OMRA version and exit.",
        ),
    ] = False,
) -> None:
    """Expose lifecycle commands as their owning milestones implement them."""


def _guard_credential_surface() -> None:
    role = os.environ.get(_RUNTIME_ROLE_ENV, "app")
    if role == "app":
        return
    if role != "tools":
        raise ConfigError(
            "unsupported runtime role",
            code="config.runtime_role",
        )
    secrets = Secrets(_env_file=None)
    check_credential_placement("tools", ExecEnv.DRY_RUN, secrets)


def run() -> None:
    """Enforce process credentials before Typer parses even eager options."""
    try:
        _guard_credential_surface()
    except ConfigError as error:
        typer.echo(f"startup_failed:{error.code}", err=True)
        raise SystemExit(2) from error
    except ValidationError as error:
        typer.echo("startup_failed:config.secret_invalid", err=True)
        raise SystemExit(2) from error
    app()


register_runtime_commands(app)

__all__ = ["app", "run"]
