"""Unit contracts for independent record-file loading."""

import hashlib
from pathlib import Path

import pytest
from pydantic import BaseModel, ConfigDict, ValidationError

from omra.config import ConfigSyntaxError, ConfigValidationError
from omra.config.files import RecordFile


class ExampleRecord(BaseModel):
    """Small immutable model used to isolate the generic loader contract."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    count: int


def test_record_file_preserves_source_hash_model_and_validated_data(tmp_path: Path) -> None:
    source = tmp_path / "records.yaml"
    raw = b"name: alpha\ncount: 2\n"
    source.write_bytes(raw)

    loaded = RecordFile.load(source, ExampleRecord)

    assert loaded is not None
    assert loaded.path == source
    assert loaded.sha256 == hashlib.sha256(raw).hexdigest()
    assert loaded.model is ExampleRecord
    assert loaded.data == ExampleRecord(name="alpha", count=2)


def test_record_file_distinguishes_required_and_optional_absence(tmp_path: Path) -> None:
    source = tmp_path / "missing.yaml"

    with pytest.raises(ConfigValidationError) as raised:
        RecordFile.load(source, ExampleRecord)

    assert len(raised.value.violations) == 1
    assert raised.value.violations[0].code == "file_missing"
    assert raised.value.violations[0].source == source
    assert RecordFile.load(source, ExampleRecord, required=False) is None


def test_optional_record_file_still_rejects_an_existing_invalid_file(tmp_path: Path) -> None:
    source = tmp_path / "optional.yaml"
    source.write_text("name: alpha\ncount: nope\n", encoding="utf-8")

    with pytest.raises(ConfigValidationError):
        RecordFile.load(source, ExampleRecord, required=False)


@pytest.mark.parametrize(
    ("raw", "match"),
    [
        (b"name: [\n", "expected"),
        (b"name: alpha\nname: beta\ncount: 2\n", "duplicate key 'name'"),
        (b"\xff", "not valid UTF-8"),
    ],
)
def test_record_file_reuses_canonical_yaml_syntax_rules(
    tmp_path: Path,
    raw: bytes,
    match: str,
) -> None:
    source = tmp_path / "records.yaml"
    source.write_bytes(raw)

    with pytest.raises(ConfigSyntaxError, match=match) as raised:
        RecordFile.load(source, ExampleRecord)

    assert raised.value.source == source


def test_record_file_rejects_non_mapping_root_with_source(tmp_path: Path) -> None:
    source = tmp_path / "records.yaml"
    source.write_text("- alpha\n- beta\n", encoding="utf-8")

    with pytest.raises(ConfigValidationError) as raised:
        RecordFile.load(source, ExampleRecord)

    assert raised.value.violations[0].code == "invalid_root"
    assert raised.value.violations[0].path == "$"
    assert raised.value.violations[0].source == source


def test_record_file_flattens_all_pydantic_errors_with_yaml_paths(tmp_path: Path) -> None:
    source = tmp_path / "records.yaml"
    source.write_text("name: alpha\ncount: nope\nunexpected: true\n", encoding="utf-8")

    with pytest.raises(ConfigValidationError) as raised:
        RecordFile.load(source, ExampleRecord)

    violations = raised.value.violations
    assert [violation.path for violation in violations] == ["count", "unexpected"]
    assert all(violation.source == source for violation in violations)
    assert "count" in str(raised.value)
    assert "unexpected" in str(raised.value)


def test_record_file_and_validated_model_are_frozen(tmp_path: Path) -> None:
    source = tmp_path / "records.yaml"
    source.write_text("name: alpha\ncount: 2\n", encoding="utf-8")
    loaded = RecordFile.load(source, ExampleRecord)

    assert loaded is not None
    record_attribute = "sha256"
    with pytest.raises(AttributeError):
        setattr(loaded, record_attribute, "changed")
    model_attribute = "count"
    with pytest.raises(ValidationError, match="frozen"):
        setattr(loaded.data, model_attribute, 3)
