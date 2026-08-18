"""Cross-suite collection rules for deterministic CI placement."""

from pathlib import Path

import pytest

_LAYER_MARKERS = frozenset(
    {
        "unit",
        "property",
        "arch",
        "contract",
        "integration",
        "scenario",
        "backtest_gate",
    }
)


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Assign the canonical layer marker and reject conflicting manual markers."""
    for item in items:
        path = Path(str(item.path))
        try:
            tests_index = path.parts.index("tests")
            layer = path.parts[tests_index + 1]
        except (ValueError, IndexError):
            continue

        if layer not in _LAYER_MARKERS:
            continue

        declared_layers = {
            marker.name for marker in item.iter_markers() if marker.name in _LAYER_MARKERS
        }
        if declared_layers and declared_layers != {layer}:
            message = (
                f"{item.nodeid}: path layer {layer!r} conflicts with markers "
                f"{sorted(declared_layers)!r}"
            )
            raise pytest.UsageError(message)
        item.add_marker(getattr(pytest.mark, layer))
