# oh-my-robo-advisor

대한민국 개인 투자자가 **본인 명의 계좌**(한국투자증권 + 업비트)를 API로 연결해, 검증된
자산배분 방법론과 한국 세제 최적화를 결합한 포트폴리오를 **VPS 서버에서 무인 운용**하는
자가 호스팅 시스템.

> 개인용이며 타인 자산을 수탁하지 않는다(투자일임업 등록 불필요 영역 — 계획 [00 §7](docs/plan/00-overview.md)).

## 문서

| 세트 | 위치 | 성격 |
|---|---|---|
| **계획** | [`docs/plan/00~07`](docs/plan/) | 구현의 **단일 정본**. 설계와 충돌하면 언제나 계획이 이긴다 |
| **설계** | [`docs/design/00~16`](docs/design/) | 계획을 구현 착수 가능한 수준으로 구체화한 설계 정본 |
| **진행 관리** | [`docs/design/17-implementation-progress.md`](docs/design/17-implementation-progress.md) | 단위 분해·착수 순서·진행 상태 |
| **런북** | [`docs/runbook/`](docs/runbook/) | 운영 절차서 |

읽는 순서는 [`docs/design/00-design-overview.md` §2](docs/design/00-design-overview.md)를 따른다.

## 핵심 가치

1. **검증된 것만** — 학술·실무적으로 검증된 알고리즘(Black-Litterman, Ledoit-Wolf, 밴드
   리밸런싱)만 자동 집행 경로에 넣는다.
2. **한국 특화** — 계좌 유형별 세제(일반위탁/ISA/연금저축/IRP), 해외주식 양도세 공제,
   금융소득종합과세·건강보험료 임계, KRX/미국 장 운영시간, KIS API 제약을 1급 시민으로 설계.
3. **잠을 잘 수 있는 무인 운용** — 확장성보다 견고함. 불확실하면 거래하지 않고 사람을
   부른다(fail-safe). 모든 결정은 감사로그로 재구성 가능하다.

## 개발

```bash
uv sync                      # 의존성 설치 (uv.lock 고정)
uv run ruff check .          # 린트
uv run mypy                  # 타입 검사
uv run lint-imports          # 의존 방향 계약
uv run pytest -m "unit or property or arch"
```

상세 절차는 [`docs/runbook/`](docs/runbook/)에 있다.

## 라이선스

Proprietary — 개인 사용 목적.
