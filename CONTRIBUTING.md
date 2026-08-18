# 기여 가이드

이 문서는 branch, 변경 범위, commit 작성과 검증에 관한 저장소 공통 규칙만 소유한다. 제품 의미와 구현 순서는 `docs/plan/`과 `docs/design/`의 정본을 따르며, 작업 목록이나 진행 상태는 이 문서에 기록하지 않는다. 일반 완료 원칙은 [개발 workflow](docs/engineering/development-workflow.md)를 따른다.

## 1. Branch와 변경 범위

- 기본 branch에 직접 commit하거나 push하지 않는다. 하나의 목적을 가진 변경은 별도 branch에서 수행한다.
- 서로 무관한 변경을 한 branch나 commit에 섞지 않는다. 발견한 별도 문제는 현재 변경과 분리한다.
- 기존 working tree 변경은 작성자의 작업으로 간주한다. 삭제하거나 덮어쓰지 말고, 필요하면 별도 worktree 또는 충돌하지 않는 branch를 사용한다.
- secret, 개인정보, runtime 산출물과 불필요한 binary를 commit하지 않는다.
- branch 이름은 변경 목적을 드러내는 `<주체>/<짧은-설명>` 형태를 권장한다.

## 2. Commit 전 검증

1. staged diff 전체를 읽고 의도한 변경과 관련 없는 파일이 없는지 확인한다.
2. `git diff --check`를 통과시킨다.
3. 변경 범위에 해당하는 로컬 품질 gate를 실행한다. 구체적인 제품 품질 기준과 CI job은 [테스트·품질 설계](docs/design/16-testing-and-quality.md)가 소유한다.
4. 예상하지 않은 binary·대용량 파일, secret, 개인정보가 없는지 확인한다.
5. 실제 검증 명령과 결과를 기록한다. 실패한 검증을 숨기거나 green으로 표현하지 않으며, 해결하지 못한 실패가 있으면 commit을 중단하고 원인과 영향을 남긴다.

## 3. Commit 메시지

Conventional Commits 형식을 사용한다.

```text
<type>(<scope>): <한국어 제목>

<무엇을 바꾸었고 왜 바꾸었는지 설명하는 한국어 본문>

Task: <작업 카드 URL 또는 식별자>
Refs: <정본 문서 경로와 절>
Tests: <실행한 검증 명령과 결과>
```

`scope`와 본문은 필요할 때만 쓴다. 실제 tracker 참조가 있을 때 `Task:` 또는 `Issue:` 중 하나를 사용하며 참조를 만들어 내지 않는다. `Refs:`는 판단 근거가 된 계획·설계 정본의 파일과 절이 있을 때 기록한다. `Tests:`는 필수이며 실제로 실행한 명령과 결과를 쓰고 명령별로 반복할 수 있다. 폐기된 구현 단위 식별자를 commit 추적 필드로 사용하지 않는다.

### 3.1 Type

| type | 용도 |
|---|---|
| `feat` | 사용자 또는 운영 기능 추가 |
| `fix` | 결함 수정 |
| `test` | 제품 동작 변경 없는 테스트 추가·수정 |
| `refactor` | 외부 동작 변경 없는 구조 개선 |
| `perf` | 성능 개선 |
| `docs` | 문서만 변경 |
| `build` | 빌드, 의존성, 패키징 변경 |
| `ci` | CI와 자동화 변경 |
| `chore` | 위 범주에 속하지 않는 유지보수 |
| `revert` | 이전 commit 되돌림 |

### 3.2 Scope

코드 변경의 scope는 [시스템 아키텍처의 현재 패키지 정의](docs/design/01-system-architecture.md)를 따른다.

- 패키지 scope: `runtime`, `cli`, `core`, `config`, `calendar`, `brokers`, `collectors`, `surveillance`, `realtime`, `data`, `engine`, `tax`, `execution`, `protections`, `portfolio`, `persistence`, `scheduler`, `rpc`, `web`, `research`, `labs`, `backtest`, `audit`, `monitoring`
- 저장소 영역 scope: `tests`, `docker`, `ci`, `docs`

여러 scope에 걸치면 대표 scope 하나를 고르거나 scope를 생략한다. scope는 새 package를 승인하지 않으며, package 구조는 시스템 아키텍처가 소유한다. 마일스톤, stage, 작업 상태는 scope로 사용하지 않는다.

### 3.3 제목과 본문

- 제목은 한국어 명령형으로 간결하게 쓰고, `: ` 뒤 제목 본문은 50자 이내를 권장하며 마침표를 붙이지 않는다.
- 본문은 한국어로 변경의 `무엇`과 `왜`를 설명한다. 구현 자체로 분명한 `어떻게`를 반복하지 않는다.
- 본문은 읽기 쉬운 폭으로 줄바꿈하며 72자를 권장 기준으로 삼는다.
- 실패했거나 실행하지 않은 검증을 성공한 것처럼 쓰지 않는다.

## 4. 자동화 commit 신원

자동화 에이전트가 이 저장소에 commit할 때는 commit 직전에 다음을 확인한다.

- GitHub CLI 로그인 계정은 `crowd-controller`여야 한다.
- `git var GIT_AUTHOR_IDENT`와 `git var GIT_COMMITTER_IDENT`의 이름은 모두 `crowd-controller`여야 한다.
- Author와 Committer email은 `crowd-controller` 계정에서 검증된 email 또는 GitHub가 제공한 정확한 noreply email이어야 한다. 주소를 추측하지 않는다.
- 신원, GitHub 계정 귀속 또는 push 권한을 검증할 수 없으면 변경을 보존하고 commit 전에 중단한다.
- AI 모델을 Author, Committer 또는 공동 저자로 기록하지 않으며 AI 공동 저자 trailer를 추가하지 않는다.

commit 후에는 로컬 Author·Committer metadata를 확인하고, push 후에는 원격 commit의 계정 귀속을 확인한다.

## 5. 관련 정본

- 제품·설계 정본 위계: [설계 총괄](docs/design/00-design-overview.md)
- 일반 개발 완료 원칙: [개발 workflow](docs/engineering/development-workflow.md)
- 품질 gate: [테스트·품질 설계](docs/design/16-testing-and-quality.md)
- 마일스톤·운영 gate: [개발 로드맵](docs/plan/04-roadmap.md)
