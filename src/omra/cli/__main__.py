"""Canonical entry point for ``python -m omra.cli``."""

from omra.cli import app


def main() -> None:
    """Run the OMRA command application."""
    app()


if __name__ == "__main__":
    main()
