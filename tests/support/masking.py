"""One canonical masking-vector loader shared by every serialization boundary test."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from typing import Literal

    from pydantic import JsonValue

_CASES_PATH = (
    Path(__file__).resolve().parents[2] / "tests" / "data" / "vectors" / "masking" / "cases.tsv"
)


@dataclass(frozen=True, slots=True)
class MaskingCase:
    case_id: str
    direction: Literal["req", "res"]
    payload: dict[str, JsonValue]
    registered_value: str
    forbidden: str


def load_masking_cases() -> tuple[MaskingCase, ...]:
    """Load dummy-only vectors used by audit and broker masking tests."""
    cases: list[MaskingCase] = []
    with _CASES_PATH.open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream, delimiter="\t"):
            decoded = json.loads(row["payload_json"])
            if not isinstance(decoded, dict):
                raise AssertionError(f"{row['case_id']}: payload_json root must be an object")
            direction = row["direction"]
            if direction not in {"req", "res"}:
                raise AssertionError(f"{row['case_id']}: invalid masking direction")
            cases.append(
                MaskingCase(
                    case_id=row["case_id"],
                    direction=cast("Literal['req', 'res']", direction),
                    payload=cast("dict[str, JsonValue]", decoded),
                    registered_value=row["registered_value"],
                    forbidden=row["forbidden"],
                )
            )
    if not cases:
        raise AssertionError("masking vector set must not be empty")
    return tuple(cases)


MASKING_CASES = load_masking_cases()
