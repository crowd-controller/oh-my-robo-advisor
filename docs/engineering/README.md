# Engineering 문서 안내

이 디렉터리는 제품 정의가 아닌 일반 개발 정책과 일회성 문서 감사 기록을 보관한다.

| 문서 | 소유하는 내용 | 소유하지 않는 내용 |
|---|---|---|
| [CONTRIBUTING.md](../../CONTRIBUTING.md) | branch, 변경 범위, commit 형식·검증·자동화 신원 | 제품 의미, 구현 순서·상태 |
| [development-workflow.md](development-workflow.md) | 완결된 개발 작업, 추적성, 검증과 완료 판정의 일반 원칙 | 작업 목록·진행 상태, 제품별 품질 임계, 마일스톤 정의 |
| [document-baseline-migration.md](document-baseline-migration.md) | 이번 기준선 정규화의 일회성 감사 기록 | 활성 작업 목록·진행률, 제품 설계, 향후 구현 순서 |

정본 위계는 계획 `docs/plan/00~07` → 정의를 소유하는 설계 `docs/design/00~16` → 일반 engineering·기여 문서 순서다. 이 디렉터리의 어떤 문서도 제품 의미, 마일스톤 순서 또는 현재 작업 상태를 소유하지 않는다.

제품 범위와 순서는 [계획 총괄](../plan/00-overview.md)과 [개발 로드맵](../plan/04-roadmap.md)을, 구현 정의는 [설계 총괄](../design/00-design-overview.md)에서 지정한 소유 문서를 따른다.
