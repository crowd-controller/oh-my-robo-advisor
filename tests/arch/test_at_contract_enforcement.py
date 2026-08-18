"""AT-7: mutation fixtures prove the configured import contracts actually block edges."""

# ruff: noqa: S603

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_FIXTURES = Path(__file__).with_name("fixtures") / "violations"

_VIOLATIONS = (
    ("v_research_to_surveillance.py", "research/__init__.py", "C04a"),
    ("v_labs_to_collectors.py", "labs/__init__.py", "C07a"),
    ("v_realtime_to_execution.py", "realtime/__init__.py", "C06a"),
    ("v_realtime_to_persistence.py", "realtime/__init__.py", "C06b"),
    ("v_web_to_runtime.py", "web/__init__.py", "C11"),
    ("v_engine_to_brokers.py", "engine/__init__.py", "C01"),
    ("v_optimizer_to_cov_monitor.py", "engine/optimizer.py", "C10"),
)


@pytest.mark.parametrize(("fixture_name", "target", "contract_id"), _VIOLATIONS)
def test_forbidden_import_fixture_is_rejected(
    fixture_name: str,
    target: str,
    contract_id: str,
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "src"
    shutil.copytree(_ROOT / "src" / "omra", source_root / "omra")
    shutil.copy2(_ROOT / "pyproject.toml", tmp_path / "pyproject.toml")

    target_path = source_root / "omra" / target
    violation = (_FIXTURES / fixture_name).read_text(encoding="utf-8")
    with target_path.open("a", encoding="utf-8") as stream:
        stream.write(f"\n{violation}\n")

    executable = str(Path(sys.executable).with_name("lint-imports"))
    assert Path(executable).is_file()
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(source_root)
    result = subprocess.run(
        [executable, "--config", str(tmp_path / "pyproject.toml")],
        cwd=tmp_path,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    output = result.stdout + result.stderr

    assert result.returncode != 0, output
    assert contract_id in output, output
