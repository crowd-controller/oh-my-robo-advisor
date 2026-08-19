"""Shared credential masking contracts."""

from __future__ import annotations

import copy
import json

import pytest
from tests.support.masking import MASKING_CASES, MaskingCase

from omra.brokers.masking import MASKED, Masker, mask_payload


@pytest.mark.parametrize("case", MASKING_CASES, ids=lambda case: case.case_id)
def test_shared_masking_vectors_remove_every_forbidden_value(case: MaskingCase) -> None:
    original = copy.deepcopy(case.payload)

    masked = Masker([case.registered_value]).mask(
        case.payload,
        direction=case.direction,
    )

    assert case.forbidden not in json.dumps(masked, ensure_ascii=False)
    assert case.payload == original
    assert masked != case.payload


def test_masker_normalizes_sensitive_key_spelling_and_masks_nested_tuples() -> None:
    masked = Masker().mask(
        {"nested": ({"upbit-secret-key": "DUMMY"},)},
        direction="req",
    )

    assert masked == {"nested": [{"upbit-secret-key": MASKED}]}


def test_masker_filters_empty_registered_values_without_rewriting_text() -> None:
    masked = Masker([""]).mask({"safe": "unchanged"}, direction="res")

    assert masked == {"safe": "unchanged"}


def test_public_mask_payload_uses_the_shared_key_filter() -> None:
    masked = mask_payload({"CANO": "DUMMY_ACCOUNT"}, direction="req")

    assert masked == {"CANO": MASKED}


@pytest.mark.parametrize(
    "key",
    [
        "CANO",
        "ACNT_PRDT_CD",
        "HTS_ID",
        "appkey",
        "appsecret",
        "access_token",
        "approval_key",
        "upbit_access_key",
        "upbit_secret_key",
    ],
)
def test_every_canonical_credential_key_is_masked(key: str) -> None:
    value = f"DUMMY_{key}"
    masked = mask_payload({key: value}, direction="res")

    assert masked == {key: MASKED}
