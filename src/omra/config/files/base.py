"""Reusable loading boundary for independently versioned YAML record files."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import TYPE_CHECKING

from pydantic import BaseModel, ValidationError

from omra.config.errors import (
    ConfigValidationError,
    Violation,
    validation_violations,
)
from omra.config.layers import parse_yaml_document, parse_yaml_mapping

if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True, slots=True)
class RecordFile[RecordT: BaseModel]:
    """A validated record file tied to the exact source bytes that produced it."""

    path: Path
    sha256: str
    model: type[RecordT]
    data: RecordT

    @classmethod
    def load(
        cls,
        path: Path,
        model: type[RecordT],
        *,
        required: bool = True,
    ) -> RecordFile[RecordT] | None:
        """Load one YAML document and flatten model failures into source-aware violations."""
        try:
            raw = path.read_bytes()
        except FileNotFoundError as error:
            if not required:
                return None
            raise ConfigValidationError(
                (
                    Violation(
                        code="file_missing",
                        message="required record file does not exist",
                        source=path,
                    ),
                )
            ) from error
        except OSError as error:
            raise ConfigValidationError(
                (
                    Violation(
                        code="file_unreadable",
                        message=str(error),
                        source=path,
                    ),
                )
            ) from error

        values = (
            parse_yaml_document(raw, source=path)
            if model.__pydantic_root_model__
            else parse_yaml_mapping(raw, source=path)
        )
        try:
            data = model.model_validate(values)
        except ValidationError as error:
            raise ConfigValidationError(validation_violations(error, source=path)) from error

        return cls(
            path=path,
            sha256=hashlib.sha256(raw).hexdigest(),
            model=model,
            data=data,
        )


__all__ = ["RecordFile"]
