"""Execution environment bootstrap types."""

from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict


class ExecEnv(StrEnum):
    """The three execution environments allowed by the architecture."""

    DRY_RUN = "dry_run"
    PAPER = "paper"
    LIVE = "live"


class RunCfg(BaseModel):
    """Execution-mode controls that contain no broker credentials."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    env: ExecEnv = ExecEnv.DRY_RUN
    live_confirmation: str | None = None
    manual_approve: bool = False
    max_account_value: int | None = None
    kill_file: Path = Path("/app/var/db/KILL")
