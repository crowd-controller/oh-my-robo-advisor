"""Execution environment bootstrap types."""

from enum import StrEnum


class ExecEnv(StrEnum):
    """The three execution environments allowed by the architecture."""

    DRY_RUN = "dry_run"
    PAPER = "paper"
    LIVE = "live"
