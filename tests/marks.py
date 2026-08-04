"""검증 항목 결선 마커 — 설계서의 `V<문서번호>-<일련>` 항목을 테스트에 묶는다.

RTM(요구사항 추적 매트릭스) 커버리지 테스트가 이 마커를 수거해 "설계서가
검증하겠다고 적은 항목 중 실제로 검사되는 것이 무엇인가"를 산출한다.
마커가 없으면 그 대조 자체가 불가능하다.

정본: 설계 16 §2.3 · §13
"""

from __future__ import annotations

import re

import pytest

# `V<문서번호>-<일련번호>` — 예: V5-07, V16-01
_ID_PATTERN = re.compile(r"^V\d{1,2}-\d{2,3}$")


def verifies(*ids: str) -> pytest.MarkDecorator:
    """설계서 검증 항목 ID를 테스트에 결선한다.

    형식 위반은 **import 시점에** 걸린다 — 오타난 ID는 RTM 대조에서 조용히
    미커버로 남기 때문이다.
    """
    if not ids:
        raise ValueError("verifies()는 최소 1개의 검증 항목 ID를 요구한다")
    for i in ids:
        if not _ID_PATTERN.match(i):
            raise ValueError(f"검증 항목 ID 형식 위반: {i!r} (예: V16-01)")
    return pytest.mark.verifies(*ids)
