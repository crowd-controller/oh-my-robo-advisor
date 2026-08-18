"""M0 package and CLI smoke tests."""

import re

from typer.testing import CliRunner

from omra import __version__
from omra.cli import app


def test_version_is_semantic() -> None:
    assert re.fullmatch(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)", __version__)


def test_cli_reports_installed_version() -> None:
    result = CliRunner().invoke(app, ["--version"])

    assert result.exit_code == 0
    assert result.stdout.strip() == __version__
