"""스캐폴드 대조 — 설계 01 §2.1 트리의 전 패키지가 실재하는지 검사한다.

이 테스트가 필요한 이유는 [01 §2.4]가 명시한다: import-linter 계약이 참조하는
모듈은 **존재해야** 하므로, 전 패키지가 M0부터 빈 패키지로라도 존재해야 한다.
존재하지 않는 모듈을 계약이 참조하면 `lint-imports` 가 에러를 낸다.

검증 항목: S01-1 DoD
"""

from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path

import pytest

import omra

# 설계 01 §2.1 트리 — `src/omra/` 하위 1차 패키지 (알파벳 순).
# 이 집합을 줄이거나 늘리는 것은 아키텍처 변경이며 01 문서의 개정을 요구한다.
FIRST_LEVEL_PACKAGES: frozenset[str] = frozenset(
    {
        "audit",
        "backtest",
        "brokers",
        "calendar",
        "cli",
        "collectors",
        "config",
        "core",
        "data",
        "engine",
        "execution",
        "labs",
        "monitoring",
        "persistence",
        "portfolio",
        "protections",
        "realtime",
        "research",
        "rpc",
        "runtime",
        "scheduler",
        "surveillance",
        "tax",
        "web",
    }
)

# 하위 패키지 — 각 소유 설계서의 파일 트리가 정본이다.
SUBPACKAGES: frozenset[str] = frozenset(
    {
        "backtest.gates",  # 15 §2
        "backtest.stats",  # 15 §2
        "brokers.kis",  # 05 §2
        "brokers.kis.ws",  # 05 §2
        "brokers.upbit",  # 05 §2
        "brokers.upbit.ws",  # 05 §2
        "config.files",  # 04 §2
        "config.schema",  # 04 §2
        "engine.overlay",  # 07 §2.1
        "execution.windows",  # 08 §2
        "persistence.migrations",  # 03 §2.1
        "persistence.repos",  # 03 §2.1
        "protections.breakers",  # 09 §2.1
        "protections.state",  # 09 §2.1
        "research.sources",  # 14 §2.1
        "rpc.channels",  # 13 §2.1
        "rpc.commands",  # 13 §2.1
        "rpc.commands.handlers",  # 13 §2.1
        "surveillance.sources",  # 11 §2.1
        "web.routers",  # 13 §2.1
    }
)


def _package_root() -> Path:
    """`src/omra/` 디렉터리."""
    root = Path(omra.__file__).parent
    assert root.name == "omra"
    return root


@pytest.mark.arch
def test_first_level_packages_exist_exactly() -> None:
    """1차 패키지 집합이 설계 01 §2.1과 정확히 일치한다.

    누락은 import-linter 계약이 존재하지 않는 모듈을 참조하게 만들고,
    초과는 아키텍처 변경이 문서 없이 일어났다는 뜻이다.
    """
    found = {
        m.name for m in pkgutil.iter_modules([str(_package_root())]) if m.ispkg
    }
    assert found == FIRST_LEVEL_PACKAGES, (
        f"누락: {sorted(FIRST_LEVEL_PACKAGES - found)} / "
        f"초과: {sorted(found - FIRST_LEVEL_PACKAGES)}"
    )


@pytest.mark.arch
@pytest.mark.parametrize("name", sorted(FIRST_LEVEL_PACKAGES | SUBPACKAGES))
def test_package_is_importable(name: str) -> None:
    """전 패키지가 import 가능하다 — 빈 패키지라도 마찬가지다."""
    importlib.import_module(f"omra.{name}")


@pytest.mark.arch
@pytest.mark.parametrize("name", sorted(FIRST_LEVEL_PACKAGES | SUBPACKAGES))
def test_package_declares_owner_docstring(name: str) -> None:
    """모든 패키지가 소유 설계서를 docstring에 명시한다.

    "이 코드의 정본이 어느 문서인가"를 파일에서 바로 읽을 수 있어야
    설계서 개정 시 영향 범위를 찾을 수 있다 (00 §8 문서 유지 규칙 1).
    """
    mod = importlib.import_module(f"omra.{name}")
    doc = mod.__doc__ or ""
    assert "정본:" in doc, f"omra.{name} 의 __init__.py 에 정본 표기가 없다"


@pytest.mark.arch
def test_no_stray_top_level_modules() -> None:
    """`src/omra/` 최상위에 예정에 없는 모듈 파일이 생기지 않았다.

    M0 시점에 허용되는 최상위 모듈은 없다 — `__main__.py` 는 S07-1에서 추가된다.
    """
    allowed = {"__init__.py", "__main__.py", "py.typed"}
    stray = sorted(
        p.name
        for p in _package_root().glob("*.py")
        if p.name not in allowed
    )
    assert stray == [], f"설계 01 §2.1 트리에 없는 최상위 모듈: {stray}"
