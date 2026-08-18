"""Property contracts for deterministic configuration merging."""

import string
from copy import deepcopy

import pytest
from hypothesis import given
from hypothesis import strategies as st

from omra.config import ConfigTypeConflict, deep_merge

_KEYS = st.text(
    alphabet=string.ascii_lowercase,
    min_size=1,
    max_size=12,
)
_SCALARS = st.none() | st.booleans() | st.integers() | st.text(max_size=30)
_LEAVES = _SCALARS | st.lists(_SCALARS, max_size=8)
_FLAT_MAPPINGS = st.dictionaries(_KEYS, _LEAVES, max_size=12)


@given(base=_FLAT_MAPPINGS, overlay=_FLAT_MAPPINGS)
def test_flat_overlay_wins_per_key_and_preserves_disjoint_keys(
    base: dict[str, object], overlay: dict[str, object]
) -> None:
    base_before = deepcopy(base)
    overlay_before = deepcopy(overlay)

    result = deep_merge(base, overlay)

    assert result == {**base, **overlay}
    assert base == base_before
    assert overlay == overlay_before


@given(base=st.lists(_SCALARS, max_size=10), overlay=st.lists(_SCALARS, max_size=10))
def test_lists_are_replaced_never_concatenated(base: list[object], overlay: list[object]) -> None:
    result = deep_merge({"items": base}, {"items": overlay})

    assert result["items"] == overlay
    assert result["items"] is not overlay


@given(mapping=_FLAT_MAPPINGS, scalar=_SCALARS)
def test_existing_mapping_cannot_be_replaced_by_scalar(
    mapping: dict[str, object], scalar: object
) -> None:
    with pytest.raises(ConfigTypeConflict):
        deep_merge({"node": mapping}, {"node": scalar})

    result = deep_merge({"node": scalar}, {"node": mapping})
    assert result == {"node": mapping}
