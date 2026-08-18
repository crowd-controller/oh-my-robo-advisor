"""Command-line composition boundary."""

from typing import Annotated

import typer

from omra import __version__

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
