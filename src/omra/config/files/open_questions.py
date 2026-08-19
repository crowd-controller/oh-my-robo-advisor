"""Strict schema for the human-maintained open-question registry."""

from collections import Counter
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator


class OpenQuestion(BaseModel):
    """One human-owned question whose resolution is never automated."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(min_length=1, max_length=64)
    text: str = Field(min_length=1)
    status: Literal["OPEN", "RESOLVED"]
    spike: str | None = Field(default=None, pattern=r"^SP-[A-Z][0-9]$")
    opened_at: date
    resolved_at: date | None = Field(default=None, validate_default=True)
    note: str = ""

    @field_validator("resolved_at")
    @classmethod
    def _validate_resolution(
        cls,
        value: date | None,
        info: ValidationInfo,
    ) -> date | None:
        status = info.data.get("status")
        if status == "RESOLVED" and value is None:
            raise ValueError("resolved questions require resolved_at")
        if status == "OPEN" and value is not None:
            raise ValueError("open questions must not have resolved_at")

        opened_at = info.data.get("opened_at")
        if value is not None and isinstance(opened_at, date) and value < opened_at:
            raise ValueError("resolved_at must be on or after opened_at")
        return value


class OpenQuestionsFile(BaseModel):
    """The optional research_open_questions.yaml record document."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    version: int = Field(ge=1)
    questions: tuple[OpenQuestion, ...]

    @field_validator("questions")
    @classmethod
    def _require_unique_ids(
        cls,
        value: tuple[OpenQuestion, ...],
    ) -> tuple[OpenQuestion, ...]:
        counts = Counter(question.id for question in value)
        duplicates = sorted(question_id for question_id, count in counts.items() if count > 1)
        if duplicates:
            raise ValueError(f"open question ids must be unique (duplicates={duplicates})")
        return value


__all__ = ["OpenQuestion", "OpenQuestionsFile"]
