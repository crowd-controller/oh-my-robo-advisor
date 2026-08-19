"""Unit contracts for the human-maintained open-question registry."""

from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from omra.config import ConfigValidationError
from omra.config.files import OpenQuestion, OpenQuestionsFile, RecordFile


def _question_values(
    question_id: str = "05 §4.5.3",
    *,
    status: str = "OPEN",
    opened_at: date = date(2026, 8, 1),
    resolved_at: date | None = None,
) -> dict[str, object]:
    return {
        "id": question_id,
        "text": "한국 세제 보정(추론)",
        "status": status,
        "spike": "SP-E3",
        "opened_at": opened_at,
        "resolved_at": resolved_at,
        "note": "",
    }


def _file_values(*questions: dict[str, object]) -> dict[str, object]:
    rows = questions or (_question_values(),)
    return {"version": 1, "questions": list(rows)}


def test_fields_match_the_human_owned_file_contract_exactly() -> None:
    assert tuple(OpenQuestion.model_fields) == (
        "id",
        "text",
        "status",
        "spike",
        "opened_at",
        "resolved_at",
        "note",
    )
    assert tuple(OpenQuestionsFile.model_fields) == ("version", "questions")
    assert "related_count_this_month" not in OpenQuestion.model_fields


def test_optional_fields_use_the_canonical_defaults() -> None:
    question = OpenQuestion.model_validate(
        {
            "id": "unassigned-spike",
            "text": "아직 스파이크가 배정되지 않음",
            "status": "OPEN",
            "opened_at": date(2026, 8, 1),
        }
    )

    assert question.spike is None
    assert question.resolved_at is None
    assert question.note == ""


def test_open_and_resolved_questions_preserve_human_state() -> None:
    opened = OpenQuestion.model_validate(_question_values())
    resolved = OpenQuestion.model_validate(
        _question_values(
            "SP-E3 outcome",
            status="RESOLVED",
            resolved_at=date(2026, 8, 2),
        )
    )

    assert opened.status == "OPEN"
    assert opened.resolved_at is None
    assert resolved.status == "RESOLVED"
    assert resolved.resolved_at == date(2026, 8, 2)


@pytest.mark.parametrize(
    ("status", "resolved_at", "message"),
    [
        ("OPEN", date(2026, 8, 2), "must not have resolved_at"),
        ("RESOLVED", None, "require resolved_at"),
    ],
)
def test_status_and_resolved_at_must_be_equivalent(
    status: str,
    resolved_at: date | None,
    message: str,
) -> None:
    with pytest.raises(ValidationError, match=message) as raised:
        OpenQuestion.model_validate(_question_values(status=status, resolved_at=resolved_at))

    assert raised.value.errors()[0]["loc"] == ("resolved_at",)


def test_resolved_at_must_not_precede_opened_at() -> None:
    with pytest.raises(ValidationError, match="on or after opened_at"):
        OpenQuestion.model_validate(
            _question_values(
                status="RESOLVED",
                opened_at=date(2026, 8, 2),
                resolved_at=date(2026, 8, 1),
            )
        )

    same_day = OpenQuestion.model_validate(
        _question_values(status="RESOLVED", resolved_at=date(2026, 8, 1))
    )
    assert same_day.resolved_at == same_day.opened_at


@pytest.mark.parametrize("status", ["open", "resolved", "CLOSED", ""])
def test_status_is_the_exact_closed_vocabulary(status: str) -> None:
    with pytest.raises(ValidationError) as raised:
        OpenQuestion.model_validate(_question_values(status=status))

    assert raised.value.errors()[0]["loc"] == ("status",)


@pytest.mark.parametrize("spike", ["SP-A1", "SP-E3", "SP-Z9", None])
def test_spike_accepts_only_the_canonical_optional_shape(spike: str | None) -> None:
    values = _question_values()
    values["spike"] = spike

    assert OpenQuestion.model_validate(values).spike == spike


@pytest.mark.parametrize("spike", ["SP-E03", "SP-e3", "SPE3", "SP-E", "SP-E3-x", "SP-E٣"])
def test_spike_rejects_every_noncanonical_shape(spike: str) -> None:
    values = _question_values()
    values["spike"] = spike

    with pytest.raises(ValidationError) as raised:
        OpenQuestion.model_validate(values)

    assert raised.value.errors()[0]["loc"] == ("spike",)


def test_id_and_text_length_contracts_are_enforced() -> None:
    for question_id in ("x", "x" * 64):
        values = _question_values(question_id)
        assert OpenQuestion.model_validate(values).id == question_id

    for question_id in ("", "x" * 65):
        with pytest.raises(ValidationError) as raised:
            OpenQuestion.model_validate(_question_values(question_id))
        assert raised.value.errors()[0]["loc"] == ("id",)

    values = _question_values()
    values["text"] = ""
    with pytest.raises(ValidationError) as raised:
        OpenQuestion.model_validate(values)
    assert raised.value.errors()[0]["loc"] == ("text",)


def test_file_requires_positive_version_and_questions_key_but_allows_empty_registry() -> None:
    assert OpenQuestionsFile.model_validate({"version": 1, "questions": []}).questions == ()

    with pytest.raises(ValidationError) as version_error:
        OpenQuestionsFile.model_validate({"version": 0, "questions": []})
    assert version_error.value.errors()[0]["loc"] == ("version",)

    with pytest.raises(ValidationError) as questions_error:
        OpenQuestionsFile.model_validate({"version": 1})
    assert questions_error.value.errors()[0]["loc"] == ("questions",)


def test_question_ids_are_unique_without_reordering_human_input() -> None:
    registry = OpenQuestionsFile.model_validate(
        _file_values(_question_values("second"), _question_values("first"))
    )
    assert tuple(question.id for question in registry.questions) == ("second", "first")

    with pytest.raises(ValidationError, match="must be unique") as raised:
        OpenQuestionsFile.model_validate(
            _file_values(_question_values("same"), _question_values("same"))
        )
    assert raised.value.errors()[0]["loc"] == ("questions",)


def test_unknown_and_derived_fields_are_rejected_at_every_level() -> None:
    root = _file_values()
    root["generated_at"] = "2026-08-01"
    with pytest.raises(ValidationError) as root_error:
        OpenQuestionsFile.model_validate(root)
    assert root_error.value.errors()[0]["loc"] == ("generated_at",)

    row = _question_values()
    row["related_count_this_month"] = 3
    with pytest.raises(ValidationError) as row_error:
        OpenQuestionsFile.model_validate(_file_values(row))
    assert row_error.value.errors()[0]["loc"] == (
        "questions",
        0,
        "related_count_this_month",
    )


def test_registry_models_are_frozen() -> None:
    registry = OpenQuestionsFile.model_validate(_file_values())

    status_field = "status"
    with pytest.raises(ValidationError, match="frozen"):
        setattr(registry.questions[0], status_field, "RESOLVED")
    version_field = "version"
    with pytest.raises(ValidationError, match="frozen"):
        setattr(registry, version_field, 2)


def test_record_file_loads_registry_and_allows_optional_absence(tmp_path: Path) -> None:
    source = tmp_path / "research_open_questions.yaml"
    source.write_text(
        """version: 1
questions:
  - id: "05 §4.5.3"
    text: "한국 세제 보정(추론)"
    status: OPEN
    spike: SP-E3
    opened_at: 2026-08-01
    resolved_at: null
    note: ""
""",
        encoding="utf-8",
    )

    loaded = RecordFile.load(source, OpenQuestionsFile)

    assert loaded is not None
    assert loaded.model is OpenQuestionsFile
    assert loaded.data.questions[0].opened_at == date(2026, 8, 1)
    assert (
        RecordFile.load(
            tmp_path / "missing-research-open-questions.yaml",
            OpenQuestionsFile,
            required=False,
        )
        is None
    )


def test_record_file_reports_nested_source_and_path(tmp_path: Path) -> None:
    source = tmp_path / "research_open_questions.yaml"
    source.write_text(
        """version: 1
questions:
  - id: "open-question"
    text: "still open"
    status: CLOSED
    spike: null
    opened_at: 2026-08-01
    resolved_at: null
    note: ""
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigValidationError) as raised:
        RecordFile.load(source, OpenQuestionsFile)

    violation = raised.value.violations[0]
    assert violation.source == source
    assert violation.path == "questions[0].status"
