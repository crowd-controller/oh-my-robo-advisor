# 문서 기준선 정규화 감사

> 이 문서는 한 번 수행한 문서 기준선 정규화의 증거다. 제품 설계, 로드맵, 활성 작업 목록 또는 진행 상태의 정본이 아니다.

## 1. 기준선과 범위

- 기준선 commit: `828a4d74b9a33f150dc3727e7cce5a74341848da`
- 삭제 대상: `docs/design/17-implementation-progress.md`
- 대상 문서는 일시적인 작업 상태, 일반 개발 workflow·commit 규칙, 이미 다른 정본이 소유하는 제품 불변식을 한 파일에 섞고 있었다.
- 53개 stage·307개 단위의 제목, 산출물, 완료 조건과 근거를 모두 검토했다. 세부 작업 지도는 복제하지 않고 Git history에만 남긴다.

## 2. 분류 방법

| 분류 | 판정 기준 | 처리 |
|---|---|---|
| A | 특정 기준선의 작업 분할·순서·상태에만 유효 | 폐기 |
| B | 계획 또는 소유 설계에 이미 같은 규칙이 존재 | 복제하지 않고 정본만 참조 |
| C | 제품과 무관하게 반복 적용되는 개발 완료 원칙 | [개발 workflow](development-workflow.md)로 이관 |
| D | 저장소 공통 commit·branch 규칙 | [기여 가이드](../../CONTRIBUTING.md)로 이관·정정 |
| E | 제품 불변식이면서 소유 정본에 없는 내용 | 소유 정본을 확인한 뒤에만 추가 |

상위 정본과 충돌하는 하위 문구는 E로 승격하지 않았다. 기존 소유 문서로 해소할 수 없는 새 제품 결정이 발견되면 삭제를 중단하는 기준을 적용했다.

## 3. 분류 결과

### 3.1 폐기한 일시적 내용

- stage와 단위의 크기·순서·상태·commit hash, 작업 위치 요약, 진행률과 갱신 절차
- 반나절 단위 time-box, 큰 작업의 의무 분할, 단위와 commit의 일대일 대응
- 파일별 산출물 목록, 작업별 완료 조건 표, 상태 변경 이력
- 폐기된 문서 자체를 code와 같은 commit에서 갱신하거나 push하도록 한 절차

이 내용은 현재 제품 의미나 안전 계약이 아니라 당시 작업 지도의 관리 정보이므로 다른 문서에 재현하지 않았다.

### 3.2 일반 workflow 이관

| 유지한 원칙 | 새 소유 문서 |
|---|---|
| 계획·소유 설계에 대한 추적성 없이 제품 구현을 시작하지 않음 | [개발 workflow](development-workflow.md) §1 |
| 기계적으로 판정 가능한 완료 조건을 착수 전에 정의 | [개발 workflow](development-workflow.md) §2 |
| 동작 변경과 검증 테스트를 같은 작업 범위에서 완료 | [개발 workflow](development-workflow.md) §3 |
| 영향 범위의 품질 gate·CI·review를 통과하고 실제 결과를 기록 | [개발 workflow](development-workflow.md) §§3~4 |
| 구현 완료와 시간 경과가 필요한 운영 gate를 구분 | [개발 workflow](development-workflow.md) §5 |
| 외부 미확인 값을 추측하지 않고 소유 정본의 조건과 fallback을 따름 | [개발 workflow](development-workflow.md) §6 |

제품별 테스트 명령, 품질 임계와 CI 판정은 [테스트·품질 설계](../design/16-testing-and-quality.md)가 계속 소유한다. 마일스톤 순서와 운영 관측 gate는 [개발 로드맵](../plan/04-roadmap.md)이 계속 소유하며 이 문서들에 복제하지 않았다.

### 3.3 Commit 규칙 이관

| 항목 | 처리 |
|---|---|
| Conventional Commits와 선택적 scope | 유지하되 type·scope의 소유 범위를 명확히 함 |
| 한국어 제목·본문 | 간결한 명령형 제목과 실제 변경 이유 중심의 본문으로 정리 |
| 추적 footer | 실제 참조가 있을 때만 `Task:` 또는 `Issue:`, `Refs:`를 사용하고 `Tests:`에 실제 결과를 기록 |
| 자동화 신원 | GitHub 계정과 유효 Author·Committer를 검증하고 AI 공동 저자 표기를 금지 |

세부 규칙은 [기여 가이드](../../CONTRIBUTING.md)가 소유한다. 과거 commit metadata는 감사 범위 밖의 불변 history로 두고 amend하거나 다시 쓰지 않았다.

### 3.4 복제하지 않은 기존 정본

| 검토한 불변식 | 기존 소유 정본 |
|---|---|
| 거래 가능성 분리와 live 전 감시·안전 선행 | [개발 로드맵](../plan/04-roadmap.md), [실시간·감시 설계](../design/11-realtime-and-surveillance.md) |
| 미집행 판정의 반사실 감사와 주문·원장 대사 | [투자 엔진 계획](../plan/02-investment-engine.md), [데이터·영속성 설계](../design/03-data-and-persistence.md), [실행 설계](../design/08-execution.md) |
| SAFE_MODE와 복구·자가치유 | [안전·운영 계획](../plan/03-safety-operations.md), [안전 보호 설계](../design/09-safety-protections.md) |
| 정수 quantizer의 backtest·dry-run·live 공유 | [투자 엔진 계획](../plan/02-investment-engine.md), [포트폴리오 엔진 설계](../design/07-portfolio-engine.md) |
| 초기 세금 원장 schema와 이후 세금 engine 시점 | [아키텍처 계획](../plan/01-architecture.md), [데이터·영속성 설계](../design/03-data-and-persistence.md), [세금 엔진 설계](../design/10-tax-engine.md) |
| 실험 원장과 DSR 표본 수 | [자기개선 계획](../plan/07-self-improvement.md), [연구 설계](../design/14-research-and-labs.md), [백테스트 설계](../design/15-backtest-and-validation.md) |

### 3.5 고유 불변식과 충돌 처리

전체 단위를 대조한 결과 E로 추가할 고유하고 유효한 제품 불변식은 **없었다**. 대신 다음 하위 문구를 정본 위계에 따라 처리했다.

- `order_lock`을 보유한 동안 모든 다른 lock 대기를 금지한다는 문구는 허용 순서와 자기모순이었다. [시스템 아키텍처](../design/01-system-architecture.md)를 [실행 설계](../design/08-execution.md)의 단방향 `order_lock → token_lock` 규칙에 맞췄다.
- 02:00 batch가 독립적으로 당일 종목 master까지 쓴다는 축약과 data 설계의 미해결 표시는 [스케줄링 설계](../design/12-scheduling-and-operations.md) [DD-12-19]에 어긋났다. [아키텍처 계획](../plan/01-architecture.md)과 [시장 데이터 설계](../design/06-market-data-and-calendar.md)를 확정된 대기·퇴화 계약에 맞췄다.
- 세금 원장 schema 시점을 후반 milestone으로 적은 문구는 초기 migration 정본과 충돌해 폐기했다. schema는 M0, 세금 engine은 M6이라는 기존 정본을 유지했다.
- `MoveGuard` 최소 종목 해석과 단일 primary goal 제한은 각 소유 설계에서 여전히 calibration 또는 미지원 제약으로 명시되어 있어 확정 규칙으로 승격하지 않았다.
- 조건부 기능의 취소 범위 누락, 외부 data source의 조기 확정, 중복 enum 준비, 파일 수·인용·표 형식 오류는 작업 지도 결함으로 분류해 이관하지 않았다.

정본 결정이나 게시를 막는 잔여 blocker는 없다. GitHub 계정·verified email·유효 Author·Committer·저장소 push 권한을 [기여 가이드](../../CONTRIBUTING.md)에 따라 commit 전에 검증했다.

## 4. 검증

모든 편집을 마친 최종 tree에서 실행을 완료한 검증만 이 절에 기록한다.

| 검증 | 실제 실행 | 결과 |
|---|---|---|
| 퇴역 참조·추적 문구 | tree 전체 `grep -RIn` 패턴 감사 | 삭제 경로는 이 문서의 inline 역사 기록 1건뿐. 활성 link·절 참조·퇴역 identifier·상태 기호·과거 footer는 0건 |
| Markdown 무결성 | 임시 Python 표준 라이브러리 checker | 변경 문서 8개, 상대 link 178개, 표 59개 검사. link·anchor·fence·heading·표·공백 모두 PASS |
| 문서 맵·통계 | `wc -l`, DD 목록 행 counter, `[확인 필요]` marker counter | 01~16은 22,631줄, 00은 195줄, 합계 22,826줄. DD 313건, 미확인 157건 |
| 변경 범위·크기 | `git diff HEAD --name-status`, `--numstat`, untracked 목록 | Markdown만 생성 4·수정 4·삭제 1. 예상 밖 binary·대용량·제품 source 변경 0건 |
| 민감정보 | tracked 추가 행과 새 문서의 credential·key·token·email pattern 검사 | 0건 |
| Git 무결성 | `git diff HEAD --check`와 최종 전체 diff 검토 | whitespace 오류와 unrelated 변경 0건 |
| 게시 신원 | `gh auth status`, 계정·verified email·Author·Committer·push 권한 확인, `git push --dry-run origin HEAD:refs/heads/codex/docs-baseline-normalization` | `crowd-controller` 귀속과 새 원격 branch push 가능 여부 모두 PASS |

## 5. 정규화 후 정본 위계

1. `docs/plan/00~07`: 제품 범위, 원칙, milestone과 운영 gate
2. 정의를 소유하는 `docs/design/00~16`: 제품 계약과 구현 설계
3. `CONTRIBUTING.md`와 `docs/engineering/`: 일반 branch·commit·개발 완료 정책

이 감사 문서는 위계를 변경하거나 활성 상태를 소유하지 않는다. 이후 구현은 [설계 총괄](../design/00-design-overview.md)이 지정한 소유 문서와 [개발 workflow](development-workflow.md)를 따른다.
