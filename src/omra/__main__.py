"""Package entry point for ``python -m omra``."""

from omra.cli import app


def main() -> None:
    """Run the canonical Typer command application."""
    app()


if __name__ == "__main__":
    main()
