# 기존 한국투자증권 KIS 기준선의 키움 REST 브로커 전환 설계

## 0. 상태, 권한과 전환 기록

| 항목 | 값 |
|---|---|
| 상태 | **승인됨(Approved)** |
| 승인 설계일 | 2026-08-21 |
| 추적 이슈 | GitHub issue #50 |
| 외부 사실 관찰일 | 2026-08-21 |
| 적용 범위 | 증권 브로커, 계좌 경계, 인증·전송, 주문·체결·대사, 외부 IRP 납입 입력, 관련 문서·구현 마이그레이션 |
| 제외 범위 | 이 카드에서 기존 계획·설계·소스·설정·스키마를 고치는 일, 실제 키 발급, 실계좌 호출, 주문 제출 |
| 현재 코드 상태 | 현재 소스는 **M0**다. 도메인·설정·초기 스키마 일부는 구현됐지만 역사적 `src/omra/brokers/kis/client.py`와 `ws/events.py`, `execution`·`tax`·`realtime`·`scheduler` 패키지는 좌표 또는 스텁이고 키움 어댑터는 아직 없다. 따라서 이 전환은 실거래 시스템 교체가 아니라 **실거래 전 아키텍처 기준선 교체**다. |

권한의 근원은 issue #50에서 사용자가 승인한 브로커 전환 지시다. 이 문서는 그 지시와 근거를 보존하는 **단일 감사 가능 전환 기록**이며, 이후 기존 문서 기준선 마이그레이션과 구현 계획이 소비할 설계 입력이다. 이 파일 자체가 저장소의 정상 문서 위계를 예외적으로 덮어쓰지는 않는다.

이 카드가 기존 계획·설계의 본문을 바꾸었거나 소스 구현을 승인했다고 해석해서는 안 된다. 현재도 제품 정의의 정상 위계는 `docs/plan` → 소유 `docs/design` → `docs/engineering`/`CONTRIBUTING.md`다. 다만 기존 `docs/plan/00~07`과 `docs/design/00~16`의 한국투자증권 KIS 조항 가운데 승인된 전환 지시와 충돌하는 부분은 **stale 역사적 마이그레이션 입력**으로 표시하고, 후속 기준선 마이그레이션 전까지 어느 브로커의 신규 구현 근거로도 사용하지 않는다. 즉 충돌 영역의 구현은 차단된다. 후속 카드가 plan과 소유 design을 함께 정합시켜 merge한 뒤 정상 위계 아래에서 구현 계획을 승인하며, 이 문서는 전환 결정과 근거의 감사 기록으로 남는다. 이 카드의 유일한 제품 산출물은 이 파일이다.

### 0.1 성공 기준

이 설계가 달성하려는 결과는 다음과 같다.

1. 증권 주문 경로는 키움 REST API 하나만 사용하고, 업비트 암호화폐 경로는 유지한다.
2. 계좌·시장·상품·연산의 네 축 모두 명시적으로 허용된 조합만 AUTO가 된다.
3. IRP는 관리 계좌가 아니라 외부 세금 입력으로만 존재한다.
4. 인증 자격증명과 반환 계좌의 결합을 검증하지 못하면 주문은 0건이다.
5. 응답 유실, 미확인 상품 적격성, 문서 불일치, 모의환경 범위의 미확인은 모두 거부 방향으로 닫힌다.
6. 실거래 전에 활성 영속 식별자에서 역사적 브로커 이름과 벤더 결합 슬리브 이름을 제거한다.

## 1. 범위, 접근 방식, 배제한 대안

### 1.1 승인한 접근 방식

> **[결정 D-01] 증권 브로커 완전 교체**
>
> 일반위탁·중개형 ISA·연금저축의 목표 증권 브로커는 `Broker.KIWOOM`이다. 업비트는 암호화폐 위성 경로의 `Broker.UPBIT`로 유지한다. 역사적 한국투자증권 KIS 런타임은 제거 대상이며 신규 주문, 조회, 토큰, 실시간 또는 폴백 경로로 남기지 않는다.

> **[결정 D-02] 단계적 기준선 교체**
>
> 문서 → 도메인/영속 식별자 → 설정/비밀정보 → read-only 전송 → 주문/체결/대사 → 계좌별 실거래 게이트 순으로 진행한다. 각 단계는 이전 단계의 검증 증거를 소비한다. 한 번에 전체 시스템을 바꾸는 big-bang 전환은 하지 않는다.

> **[결정 D-03] 설치형 OpenAPI+ 배제**
>
> 설치형 Windows COM/OCX 경로인 고전 OpenAPI+는 운영 런타임, 비상 폴백, 테스트 오라클 어느 역할도 맡지 않는다. 공식 키움 REST와 WebSocket만 증권 통신 경계다.

### 1.2 기각한 대안

| 대안 | 판정 | 이유 |
|---|---|---|
| 두 증권사 어댑터를 함께 유지하는 전환 브리지 | 기각 | 이중 인증·이중 유량·이중 대사·서로 다른 상품 의미론을 장기간 운영하게 하고, 잘못된 브로커로 라우팅할 표면을 늘린다. 일회성 오프라인 데이터 변환은 허용하지만 런타임 이중 제공자는 허용하지 않는다. |
| 모든 문서·스키마·전송·실거래를 한 카드에서 교체 | 기각 | M0라도 계좌 결합과 응답 계약의 외부 증거가 필요하다. 단계별 실패 격리와 독립 검증이 불가능해진다. |
| 고전 OpenAPI+를 REST 미지원 기능의 폴백으로 사용 | 기각 | Linux 자가 호스팅 경계와 배포 모델을 깨고 별도 운영·보안 표면을 만든다. 미지원 기능의 안전한 폴백은 주문 거부 또는 수동 외부 입력이다. |
| API가 노출한 모든 시장·상품을 자동 허용 | 기각 | 브로커 능력은 애플리케이션 투자 정책과 안전 증거를 대신하지 않는다. |

## 2. 사실·결정·추론·미확인 분류 규약

이 문서의 문장은 다음 네 종류 중 하나로 판정한다.

| 종류 | 표기 | 의미 | 후속 작업에서의 취급 |
|---|---|---|---|
| 공식 사실 | `[사실 F-nn]` | 관찰일에 공식 키움 페이지·공식 저장소가 직접 밝힌 내용 | 사실의 범위 안에서만 입력으로 사용한다. |
| 제품 결정 | `[결정 D-nn]` | 승인된 애플리케이션 정책·아키텍처 | 후속 기준선 마이그레이션에 반영한다. 정상 문서 위계가 정합된 뒤 구현 계획이 이를 구현하며, 공식 API가 더 넓어도 범위를 자동 확대하지 않는다. |
| 설계 추론 | `[추론 I-nn]` | 공식 사실에서 안전하게 도출한 구현 방향 | 검증 가능한 가설로 다루며 반증되면 수정한다. |
| 미확인 근거 | `[미확인 U-nn]` | 공식 답변·실호출·계약 카세트가 아직 없는 능력 | **거부가 기본값**이다. 확인 전에는 AUTO 또는 live를 켤 수 없다. |

규칙은 세 가지다.

- 공식 문서의 부재를 금지 사실로 바꾸지 않는다. 명시적 답변이 없으면 `미확인`이다.
- 공식 지원 범위를 애플리케이션 허용 범위로 바꾸지 않는다. 예를 들어 공식 FAQ가 ETF/ETN을 함께 언급해도 이 제품은 승인된 ETF만 자동화한다.
- 공식 답변이 계좌 **등록**을 말할 뿐이면 잔고조회·주문·취소·체결조회·상품 적격성까지 증명한 것으로 확대하지 않는다.

## 3. 2026-08-21 공식 근거 레지스터

아래 링크는 모두 키움 공식 자산이다. 제3자 자료는 이 설계의 근거로 사용하지 않는다.

| ID | 공식 사실 | 출처와 범위 |
|---|---|---|
| F-01 | 키움 REST API는 설치 없이 Linux를 포함한 여러 OS에서 사용할 수 있고, 포털의 현재 매매 가능 상품 표는 국내주식과 미국주식을 열거한다. | [REST API 소개·상품·유량](https://openapi.kiwoom.com/intro?dummyVal=0) |
| F-02 | 국내주식은 계좌별·토큰별 주문 TR과 조회 TR이 각각 초당 5회다. 미국주식 일반 구간은 주문 10회/초, 조회 5회/초, 환전 1회/초이고, KST 09:00~10:00 피크 구간은 주문·조회가 각각 3회/초다. 추가로 미국주식 전체는 50회/초, 차트는 20회/초, 공식 종목리스트 TR은 5회/분의 계좌별·토큰별 한도가 있다. | [REST API 소개·상품·유량](https://openapi.kiwoom.com/intro?dummyVal=0) |
| F-03 | 모의투자는 TR별 국내주식 1회/초, 미국주식 1회/초로 안내된다. 계좌별·토큰별 세션은 1개이고 세션당 실시간 시세 한도는 200종목이다. | [REST API 소개·상품·유량](https://openapi.kiwoom.com/intro?dummyVal=0) |
| F-04 | 서비스 가이드는 실제투자와 모의투자 App Key를 별도로 관리하고, 계좌 등록 뒤 계좌별 App Key·App Secret을 내려받는 흐름을 안내한다. App Key 발급 전 허용 IP를 등록하며, 실전·모의 각각 계좌를 등록한다. OAuth 2.0 Client Credentials 방식의 접근 토큰 유효기간은 24시간이다. | [REST API 이용안내](https://openapi.kiwoom.com/intro/serviceInfo) |
| F-05 | 공식 이벤트 FAQ는 위탁종합뿐 아니라 중개형 ISA, 연금저축, 비과세종합 계좌를 REST API 신청 가능 계좌로 열거하고, 당시 국내주식에 ETF/ETN이 포함된다고 설명한다. | [키움 REST API 공식 FAQ](https://www.kiwoom.com/e/m/home/event/VEvent20250074View) |
| F-06 | 2026-06-17 공식 답변은 등록 가능 계좌 목록에 연금저축과 중개형 ISA 등을 열거하면서 IRP는 등록 불가능하다고 명시한다. | [등록 계좌 공식 답변](https://bbn.kiwoom.com/bbs/VBbsBoardBOPAQApiDetailView?seqid=4400&dummyVal=0) |
| F-07 | 2026-07-13 공식 답변은 현재 키움 REST API가 IRP 계좌를 지원하지 않으며 추가 지원 여부와 일정은 확정해 말하기 어렵다고 명시한다. | [IRP 공식 답변](https://bbn.kiwoom.com/bbs/VBbsBoardBOPAQApiDetailView?seqid=4745&dummyVal=0) |
| F-08 | 2026-08-18 공식 답변은 중개형 ISA가 키움 REST API 이용 가능하고, 신규 계좌는 내부 실명 확인 완료 뒤 화면에 노출될 수 있다고 설명한다. | [중개형 ISA 공식 답변](https://bbn.kiwoom.com/bbs/VBbsBoardBOPAQApiDetailView?seqid=5416&dummyVal=0) |
| F-09 | 2026-07-01 공식 답변은 연금저축계좌가 REST API 신청 가능하다고 설명한다. 답변은 정확한 read-only 응답, 주문 성공, ETF 적격성까지 확정하지 않는다. | [연금저축 공식 답변](https://bbn.kiwoom.com/bbs/VBbsBoardBOPAQApiDetailView?seqid=4567&dummyVal=0) |
| F-10 | 관찰한 공식 GitHub revision `69642586f7d84ba9fd8a6faf1f1537c7fda6568b`의 README는 HTTP API 306개를 PRD와 MOCK 각각에 제공해 총 612개 요청이 있고 미국 HTTP API가 121개라고 설명한다. 같은 revision의 공식 Postman collection에는 미국주식 MOCK 매수주문 request 정의가 존재한다. WebSocket API 31개는 Python 예제로 제공한다고 별도로 설명한다. | [고정 revision README](https://github.com/Kiwoom-Securities/Kiwoom-REST-API/blob/69642586f7d84ba9fd8a6faf1f1537c7fda6568b/README.md), [고정 revision Postman collection](https://github.com/Kiwoom-Securities/Kiwoom-REST-API/blob/69642586f7d84ba9fd8a6faf1f1537c7fda6568b/postman/kiwoom-openapi.postman_collection.json) |
| F-11 | 같은 고정 revision의 공식 주문 문서는 **국내주식 REST API**의 매수·매도·정정·취소 route를 설명하며 그 국내 모의 도메인에 KRX-only 주석을 둔다. 이 주석의 문서상 범위는 해당 국내 route다. | [고정 revision 국내주식 주문 문서](https://github.com/Kiwoom-Securities/Kiwoom-REST-API/blob/69642586f7d84ba9fd8a6faf1f1537c7fda6568b/kiwoom_docs/%EC%A3%BC%EB%AC%B8.md) |
| F-12 | 같은 고정 revision의 공식 실시간 문서는 **국내주식 WebSocket**의 주문체결·잔고·시세·ETF NAV·VI 이벤트를 설명하며 그 국내 모의 WebSocket 도메인에 KRX-only 주석을 둔다. 이 주석의 문서상 범위는 해당 국내 WebSocket route다. | [고정 revision 국내주식 실시간 문서](https://github.com/Kiwoom-Securities/Kiwoom-REST-API/blob/69642586f7d84ba9fd8a6faf1f1537c7fda6568b/kiwoom_docs/%EC%8B%A4%EC%8B%9C%EA%B0%84%EC%8B%9C%EC%84%B8.md) |
| F-13 | 현재 공식 모의투자 가이드는 국내 모의 매매·계좌조회는 KRX만 가능하다고 설명하는 한편, 미국 모의투자는 NYSE·NASDAQ·AMEX 상장 종목을 지원한다고 별도로 명시한다. | [REST API 모의투자 이용안내](https://openapi.kiwoom.com/intro/mockInvestInfo?dummyVal=0) |
| F-14 | 키움 공식 OpenAPI+ 페이지는 모듈 설치와 OCX control 제작 절차를 안내하고, 개발 환경을 Windows COM 버전으로 명시한다. | [키움 OpenAPI+ 공식 안내](https://www.kiwoom.com/m/customer/download/VOpenApiInfoView) |

> **[추론 I-01] 공식 페이지의 범위 차이 처리**
>
> 이벤트 FAQ의 국내주식 중심 설명과 현재 포털의 국내·미국 상품 표는 게시 문맥과 시점이 다르다. F-13의 미국 MOCK 시장 지원과 F-10의 PRD/MOCK HTTP catalog·미국 MOCK 매수 request는 미국 MOCK HTTP 표면과 주문 request 정의의 **존재**를 보이지만, 개별 요청의 성공, 주문·체결·대사 행동, WebSocket 제공 범위 또는 REAL parity를 증명하지 않는다. F-11·F-12의 국내 route KRX-only 주석을 미국 route 부재로 일반화하지 않는다. 미국 MOCK의 계좌·조회·주문·체결·대사·WebSocket 능력은 실제 계약 실행 전까지 `미확인`이고 `DENY`다.

> **[추론 I-02] 공식 노출 범위와 AUTO 능력 분리**
>
> F-05·F-08·F-09의 계좌·상품 또는 신청 가능 진술은 그 문언 범위의 사실이다. 각 계좌의 조회·주문·체결·대사와 상품 적격성은 연산별 증거가 없으면 `미확인`이며, 금지 사실로 단정하지 않고 제품의 fail-closed 정책에 따라 `DENY`한다.

## 4. 목표 계좌·시장·상품·연산 능력

### 4.1 fail-closed 판정식

AUTO 허용 여부는 다음 교집합이다.

```text
AUTO_ALLOWED =
    account_type_allowed
  ∧ market_allowed
  ∧ instrument_allowed
  ∧ operation_allowed
  ∧ environment_evidence_passed
  ∧ exact_account_binding_passed
  ∧ reconciliation_ready
  ∧ operational_gate_open
```

한 항이라도 `false` 또는 `unknown`이면 결과는 `DENY`다. 브로커 응답에 종목이 존재하거나 주문 요청이 접수될 수 있다는 사실은 `instrument_allowed`를 참으로 만들지 않는다. 능력 캐시는 긍정 증거에만 유효기간을 두고, 만료·스키마 변화·공식 근거 개정 시 다시 `unknown`으로 닫는다.

### 4.2 능력 행렬

표의 `목표 AUTO`는 최종 제품 범위이고, `현재 LIVE/REAL`은 이 설계 시점의 안전 상태다. `조회`에는 정확한 계좌 식별, 잔고·보유·가용 현금, 주문/체결 대사에 필요한 read-only 응답이 포함된다.

| 계좌 경계 | 시장 | 상품 | 등록/인증 | 조회 | 주문·취소·대사 | 목표 AUTO | 현재 LIVE/REAL과 안전 폴백 |
|---|---|---|---|---|---|---|---|
| 일반위탁 | 국내 KRX | 애플리케이션 승인 국내 ETF | 공식 계좌 등록 후 정확 결합 필요 | 계약 검증 필요 | 계약·소액 통제 검증 필요 | **허용 목표** | 게이트 전 `DENY`; DRY_RUN local simulator와 KRX PAPER/MOCK 뒤 명시적 LIVE/REAL 절차 |
| 일반위탁 | 미국 정규시장 (`NASD`·`NYSE`·`AMEX`) | 애플리케이션 승인 미국 ETF | 정확 결합 필요 | 시장·계좌별 계약 검증 필요 | 주문유형·체결조회·환율·대사 검증 필요 | **허용 목표** | 공식 catalog에 미국 MOCK HTTP 요청은 있으나 실제 조회·주문·체결·대사와 MOCK WebSocket/parity는 미확인; 계약 실행과 별도 LIVE/REAL 게이트 전 `DENY` |
| 일반위탁 | 국내 NXT/SOR | 모든 상품 | API 노출 여부와 무관 | 자동운용 입력으로 사용하지 않음 | **금지** | 금지 | 별도 근거·안전 카드가 승인될 때까지 `DENY` |
| 일반위탁 | 국내·미국 | 개별주, ETN, 기타 현 유니버스 제외 상품 | API 노출 여부와 무관 | 관측 가능해도 AUTO 입력 아님 | **금지** | 금지 | `DENY`; 유니버스 확대는 별도 제품 결정 |
| 중개형 ISA | 국내 KRX | 애플리케이션 승인·계좌 적격 국내 ETF | 공식 이용 가능 사실 + 정확 결합 필요 | 응답 계약 검증 필요 | 종목 적격성·주문·체결·대사 검증 필요 | **허용 목표** | 모든 검증 전 `DENY`; 적격성 `unknown`이면 주문 거부 |
| 중개형 ISA | 미국, NXT/SOR | 모든 상품 | 제품 범위 밖 | 사용하지 않음 | 금지 | 금지 | `DENY` |
| 중개형 ISA | 국내 KRX | 개별주, ETN, 기타 ETF 외 상품 | 공식 FAQ의 ETF/ETN 언급과 무관 | AUTO 입력 아님 | 금지 | 금지 | **제품 결정으로 `DENY`** |
| 신탁형·일임형 ISA | 모든 시장 | 모든 상품 | 제품 범위 밖 | 관리하지 않음 | 금지 | 금지 | 브로커 미지원이라는 법적·기술적 단정이 아니라 제품 배제 |
| 연금저축 | 국내 KRX | 애플리케이션 승인·계좌 적격 국내 ETF | 공식 신청 가능 사실 + 정확 결합 필요 | 정확한 등록·잔고·보유 응답 검증 필요 | 적격성 행동과 주문·취소·체결·대사 검증 필요 | **허용 목표** | **LIVE/REAL 강제 비활성**. §10.3의 연금 전용 게이트를 모두 통과하기 전 `DENY` |
| 연금저축 | 미국, NXT/SOR | 모든 상품 | 제품 범위 밖 | 관리 입력으로 사용하지 않음 | 금지 | 금지 | `DENY` |
| 연금저축 | 국내 KRX | 개별주, ETN, 기타 ETF 외 상품 | API 노출 여부와 무관 | AUTO 입력 아님 | 금지 | 금지 | `DENY`; 키움의 전체 상품 허용 목록을 이 문서가 주장하지 않음 |
| IRP | 모든 시장 | 모든 상품 | **등록 금지** | **잔고·보유 동기화 금지** | **주문 금지** | 금지 | 관리 `Account`가 아님. §5의 수동 누적 납입액만 허용 |
| 업비트 | 업비트 현물 | 기존 승인 BTC/ETH 위성 | 기존 경계 유지 | 기존 계약 유지 | 기존 주문·체결·대사 정책 유지 | 허용 목표 | 이 전환의 증권 게이트와 독립; 유니버스 자동 확대 없음 |

### 4.3 계좌별 추가 불변식

> **[결정 D-04] 일반위탁**
>
> 국내는 기존 KRX 정규시장 안전 정책을 그대로 유지한다. 미국은 기존 `NASD`·`NYSE`·`AMEX` 시장의 승인 ETF 유니버스만 대상이다. 개별주, ETN, NXT, SOR는 키움 API가 노출해도 활성화되지 않는다.

> **[결정 D-05] 중개형 ISA**
>
> 중개형 ISA만 관리 대상이며, 애플리케이션 승인 국내 KRX ETF 중 계좌 적격성이 확인된 상품만 AUTO 대상이다. 상품 적격성을 응답·공식 자료·통제 검증으로 확인할 수 없으면 주문을 거부한다.

> **[결정 D-06] 연금저축**
>
> 목표 상태는 승인·적격 국내 KRX ETF의 AUTO지만, 정확한 계좌 등록, read-only 응답, 상품 적격성 행동, 주문/체결/대사와 통제된 LIVE/REAL 검증이 모두 끝날 때까지 live 주문 기능은 코드와 설정 양쪽에서 꺼져 있어야 한다. 이 문서는 키움 연금저축의 완전한 상품 허용 목록을 선언하지 않는다.

> **[결정 D-07] IRP**
>
> IRP는 관리 계좌가 아니다. 자격증명을 받지 않고, 계좌 식별자를 저장하지 않고, 잔고·보유·체결을 동기화하지 않고, 자산배분·성과·주문에 넣지 않는다. 현재 과세연도의 누적 납입액만 수동 외부 입력으로 받는다. 향후 공식 지원이 생겨도 자동 활성화하지 않으며 공식 근거 개정, 별도 제품 카드, 계좌·상품·LIVE/REAL 검증을 모두 다시 거쳐야 한다.

## 5. IRP 외부 납입 경계

### 5.1 도메인 모델

관리 계좌 모델의 `AccountType.IRP`는 제거한다. 대신 관리 계좌와 의존 방향이 없는 외부 세금 입력을 둔다.

```python
class ExternalTaxContribution:
    tax_year: int
    cumulative_contributed_krw: Decimal
    as_of: date
    source: Literal["manual"]
    recorded_at: datetime
```

위 다섯 항목이 IRP 납입의 전체 의미 계약이다. `source = manual`과 `recorded_at`은 클라이언트가 제출하는 세금값이 아니라 시스템이 기록하며, `recorded_at`은 설정된 한국 업무 시간대에 맞춘 timezone-aware 서버 시각으로 부여해 이후 바꾸지 않는다. 영속 계층은 내부 기술 식별자, revision/head 연결값, correction workflow가 남기는 시스템 통제 분류·사유만 audit metadata로 추가할 수 있다. 이 메타데이터는 다섯 의미 필드나 세금 계산 입력이 아니다. 이 레코드에는 다음 항목이 존재해서는 안 된다.

- 계좌번호, 계좌 별칭, 브로커 계좌 식별자
- 잔고, 보유 종목, 수익률, 평가액
- 주문, 거래, 체결, 입출금 내역
- 세액 또는 세금 납부액

`cumulative_contributed_krw`는 **납입액**이지 세액이 아니다. 새 가이드 입력은 설정된 한국 업무 시간대에서 실행일이 속한 현재 과세연도만 받으며, 과거 연도 레코드는 감사·재현 이력일 뿐 현재 계산에 대입하지 않는다. 음수는 거부한다.

### 5.2 선형 개정 체인과 입력 검증

각 `tax_year`는 정확히 하나의 선형 IRP contribution revision chain과 최대 하나의 head를 가진다. 첫 revision의 `supersedes_id`는 `null`이고, 이후의 증가·동일 금액 신선도 확인·정정은 모두 쓰기 시작 시 읽은 현재 head를 `supersedes_id`와 expected head로 지정한다. revision append와 head 교체는 하나의 트랜잭션에서 compare-and-swap으로 처리한다. expected head가 이미 바뀌었거나, 두 번째 head 또는 fork를 만들려는 쓰기는 전체 롤백하고 거부한다.

입력 검증은 다음과 같다.

- `as_of`의 연도는 `tax_year`와 같아야 하고, 설정된 한국 업무 시간대의 현재 날짜보다 미래일 수 없다.
- 정상 snapshot은 현재 head보다 `as_of`와 `cumulative_contributed_krw`가 모두 감소하지 않아야 한다. 같은 금액의 더 늦은 `as_of`는 신선도 확인 revision으로 허용하고, 이전 날짜로 늦게 도착한 일반 snapshot은 거부한다.
- 날짜 또는 금액을 감소시키는 변경은 현재 head를 잇는 명시적 감사 정정만 허용한다. 정정은 audit-only `change_kind = correction`과 비어 있지 않은 사유를 남기며 원래 revision을 수정하거나 삭제하지 않는다.
- `recorded_at`은 설정된 한국 업무 시간대에 맞춘 timezone-aware 서버 시각으로 append 시 부여한다. 클라이언트가 제시한 시각이나 단순한 최대 `recorded_at`으로 현재값을 선택하지 않는다.

계산의 현재값은 `tax_year`의 unique head가 가리키는 revision 하나로 결정한다. revision이 있는데 head가 없거나, head가 복수이거나, `supersedes_id` 단절·fork·cycle이 감지되면 현재값을 임의 선택하지 않는다. 새 쓰기는 거부하고 읽기는 `UNKNOWN`과 무결성 경보를 반환한다.

IRP contribution revision 하나만 기록해서는 파생 세금 가이드의 당시 선택과 계산을 재현할 수 없다.

### 5.3 세금 계산 provenance와 재현 계약

파생 세금 가이드는 결과의 값·상태와 **versioned logical calculation provenance bundle**을 하나의 트랜잭션으로 저장한다. 물리 테이블·컬럼 이름은 후속 세금·영속 카드가 소유하며, 이 절은 논리적 최소 계약만 정한다.

| 논리 구성요소 | 반드시 보존할 내용 |
|---|---|
| IRP 납입 입력 | 소비한 정확한 contribution revision 식별자, 또는 레코드 없음·stale·chain 무결성 오류라는 명시적 `UNKNOWN` 상태와 사유. stale에 마지막 revision이 있으면 그 식별자와 `as_of`도 보존 |
| 평가 문맥 | 계산·평가 `as_of`, 입력·규칙 선택 시각, 그 시각을 해석한 설정된 한국 업무 시간대 |
| 세법 규칙·설정 | 선택한 effective-date 세법 규칙 revision 또는 불변 fingerprint, 적용일 판정과 해당 config/schema revision |
| 다른 연금 납입 | 계산에 소비한 모든 snapshot/revision 식별자 또는 불변 fingerprint, 없거나 미확인이면 대상별 명시적 `UNKNOWN` 사유 |
| 소득·프로필 | 소비한 input revision 또는 불변 snapshot fingerprint, 필요한 입력이 없으면 항목별 명시적 `UNKNOWN` 사유 |
| 구현·정책 | calculator/code version과 policy version 등 같은 입력을 같은 의미로 해석하는 구현 provenance |

입력값이 누락·stale이어도 그 상태와 사유를 명시하면 bundle은 완전할 수 있고, 재실행은 같은 `UNKNOWN` 상태를 산출해야 한다. 결정론적 재실행은 당시 bundle의 불변 참조와 선택 문맥을 사용하며 현재 IRP head, 현재 설정, 현재 다른 납입, 현재 프로필 또는 현재 시각으로 대체하지 않는다.

필수 구성요소가 빠졌거나 참조한 revision·snapshot·version을 해석할 수 없으면 그 결과를 **재현 가능**하다고 표시하지 않는다. 이미 저장된 값은 `non-reproducible` 감사 이력으로만 남길 수 있고 현재 가이드에 재사용하지 않는다. 필요한 의미 입력 또는 감사 가능한 계산 근거가 불완전한 새 가이드는 해당 결과를 `UNKNOWN`으로 닫는다.

### 5.4 신선도와 UNKNOWN

신선도는 임의의 고정 일수로 추측하지 않는다. 소비자가 요구하는 **납입 확인 기준일**을 명시하고 `as_of`가 그 기준일보다 이르면 stale이다. 예를 들어 연말 잔여 한도 점검의 확인 기준일은 그 점검 실행일이다.

| 상태 | 납입액 의미 | 잔여 납입 여력 | 예상 세액공제 |
|---|---|---|---|
| 해당 연도 레코드 없음 | `UNKNOWN` | `UNKNOWN` | `UNKNOWN` |
| `as_of`가 요구 기준일보다 이전임 | `UNKNOWN(stale)` | `UNKNOWN` | `UNKNOWN` |
| 연도·기준일·누적액 유효 | 알려진 누적 납입액 | effective-date 세법 규칙으로 계산 가능 | 필요한 소득·프로필 입력까지 알려진 경우만 계산 가능 |
| 소득·프로필 입력 미확인 | 납입액은 알려질 수 있음 | 계산 가능할 수 있음 | **`UNKNOWN`** |

누락 또는 stale을 `0`으로 대체하지 않는다. 오래된 실제 값도 현재 계산 입력으로 재사용하지 않고, 화면과 알림에는 마지막 `as_of`와 함께 `UNKNOWN` 사유를 표시한다.

### 5.5 예시 데이터 흐름

다음은 세법 한도나 세율을 뜻하지 않는 최초 revision의 수동 입력 예다. 시스템은 `source`와 `recorded_at`을 부여하고 최초 head precondition을 `null`로 검증한다.

```yaml
tax_year: 2026
cumulative_contributed_krw: 3000000
as_of: 2026-08-21
```

```text
본인 수동 입력
  → 현재 과세연도·한국 업무 날짜·누적액 검증
  → 트랜잭션에서 expected head 확인
  → revision append와 unique head compare-and-swap
  → unique head의 as_of와 요구 기준일 비교
  → 유효한 IRP revision과 연금저축 등 다른 납입 snapshot/revision 또는 UNKNOWN 사유 확정
  → 평가 as_of·선택 시각과 해당 날짜의 tax.yaml 규칙/config revision 확정
  → 소득·프로필 revision 또는 항목별 UNKNOWN 사유 확정
  → 잔여 납입 여력 산출 또는 UNKNOWN
  → 소득·프로필이 모두 알려진 경우에만 예상 공제 산출
  → calculator/code/policy version을 포함한 완전한 provenance bundle 조립
  → 결과와 versioned provenance bundle을 원자적으로 저장
  → 대시보드/알림의 세금 가이드
```

이 흐름에서 브로커 게이트웨이, 포트폴리오, 성과 계산, 리밸런서, 주문 라우터로 향하는 간선은 없다.

## 6. 도메인·식별자 전환

### 6.1 목표 공개 식별자

| 개념 | 역사적 마이그레이션 입력 | 목표 정본 |
|---|---|---|
| 증권 브로커 | 역사적 `Broker.KIS = "KIS"` | `Broker.KIWOOM = "KIWOOM"` |
| 국내 증권 슬리브 | 역사적 `kis_domestic` | `domestic_securities` |
| 미국 증권 슬리브 | 역사적 `kis_overseas` | `us_securities` |
| 암호화폐 슬리브 | 벤더 결합 `upbit` | `crypto` |
| 관리 IRP 계좌 | 역사적 `AccountType.IRP` | 관리 계좌 enum에서 제거; `ExternalTaxContribution`으로 분리 |

`SleeveId`는 실행·상태·한도·성과의 **자산 경계**이고, `Broker`는 통신 제공자다. 따라서 `domestic_securities`, `us_securities`, `crypto`는 브로커 교체 없이 유지될 수 있어야 한다. 브로커 라우팅은 `(account.broker, market)`에서 결정하고 슬리브 문자열에서 벤더를 역추론하지 않는다.

> **[결정 D-08] 런타임 별칭 금지**
>
> 역사적 값과 새 값을 동시에 받는 enum 별칭, 두 브로커 디렉터리의 동시 로딩, 설정 fallback은 만들지 않는다. 필요한 개발 DB 변환은 실행 전 일회성 오프라인 마이그레이션으로 수행하고, 완료 뒤 역사적 활성 값은 스키마 검증에서 거부한다.

### 6.2 관리 계좌와 외부 세금 입력의 의존 경계

```text
Managed Account ──> portfolio / allocation / performance / execution / reconciliation

ExternalTaxContribution(IRP) ──> tax guidance only
```

두 모델은 공통 기반 클래스를 공유하지 않는다. `account_id`, `broker`, `credentials_ref`, `positions`, `orders`를 외부 세금 입력에 추가하면 이 경계를 위반한다. 세금 엔진은 관리 계좌 납입 레코드와 IRP 외부 입력을 계산 시점에 값으로 결합할 수 있지만 IRP를 계좌 객체로 승격하지 않는다.

## 7. 인증, 계좌 등록, 정확 결합

### 7.1 실행 모드와 자격증명 단위

애플리케이션 정본 `ExecEnv = {dry_run, paper, live}`와 키움 전송 경계의 서버/자격증명 환경을 구분한다.

| 애플리케이션 `ExecEnv` | 키움 전송 환경 | 자격증명·제출 의미 |
|---|---|---|
| `dry_run` | 없음 | 로컬 simulator만 사용한다. 키움 제출 endpoint, App Key/Secret, token, account binding을 조회하거나 사용하지 않는다. |
| `paper` | 공식 `MOCK` | MOCK endpoint·자격증명·token·계좌 등록/binding만 사용한다. |
| `live` | 공식 `REAL` | REAL endpoint·자격증명·token·계좌 등록/binding만 사용한다. |

> **[결정 D-09] 계좌 × 실행 환경 단위 결합**
>
> 키움 자격증명은 `exec_env ∈ {paper, live}`에서 최소 `(managed_account_id, exec_env)` 단위로 등록하고 서버 환경은 위 표로만 파생한다. 하나의 공식 키가 여러 계좌를 노출하더라도 각 관리 계좌는 자신의 기대 식별자와 명시적으로 결합되어야 한다. 다만 공식 응답의 1:1 또는 1:N 계좌 노출 계약이 검증되기 전에는 반환 건수나 일치 건수와 무관하게 binding을 만들지 않는다.

실행 모드, 파생 서버 환경, endpoint 집합, App Key/Secret reference, token namespace, rate profile, 계좌 등록과 binding을 하나의 버전된 environment bundle로 검증하고 선택한다. endpoint만 바꾸거나 key·token·binding 일부만 반대 환경에서 재사용하는 half-switch는 네트워크 호출 전에 거부한다. `dry_run` bundle에는 브로커 제출 자격증명 reference가 존재해서는 안 된다.

구성의 공개 부분은 내부 `managed_account_id`, 브로커, `exec_env`, fingerprint 버전과 전체 expected digest 또는 비밀정보 공급자의 opaque reference, 허용 능력 프로파일만 가진다. 파생 `MOCK`/`REAL`을 별도 선택값으로 두지 않는다. App Key, App Secret, 접근 토큰, 원계좌번호와 fingerprint pepper는 비밀정보 공급자에만 둔다. 비밀정보를 YAML, Git, 감사로그, 예외 메시지, HTTP 카세트에 기록하지 않는다.

계좌 fingerprint는 기존 공개 config의 비키 방식 SHA-256을 재사용하지 않는다. 버전된 domain tag와 정규화된 `(broker, exec_env, derived_server_env, full_account_identity)`를 모호하지 않은 length-prefixed canonical encoding으로 만들고, 비밀정보 공급자에만 있는 버전별 pepper를 키로 **HMAC-SHA-256**을 계산한다. 평문·비키 해시와 계좌번호의 짧은 prefix는 금지하며, 전체 digest는 constant-time 비교한다.

### 7.2 계좌 선택 알고리즘

반환 배열의 첫 번째 계좌, 정렬상 첫 계좌, 단 하나처럼 보이는 계좌를 선택하는 로직은 금지한다. `matching_candidates`는 configured expected digest와 안전하게 일치한 반환 레코드의 집합이다.

```text
1. `paper`/`live` 실행 모드에서 각각 완전한 `MOCK`/`REAL` environment bundle을 검증한다.
2. 그 bundle의 자격증명으로 토큰을 발급한다.
3. 안전한 read-only 공식 경로로 노출 계좌/계좌 정체성을 조회한다.
4. 각 원식별자는 비밀정보 경계 안에서 정규화한다.
5. configured fingerprint 버전의 secret pepper로 각 레코드의 HMAC-SHA-256을 계산한다.
6. 전체 digest를 constant-time 비교해 `matching_candidates`를 만든다.
7. 1:1/1:N 응답 계약 증거가 미확인이면 후보 수와 무관하게 binding을 거부한다.
8. 계약이 검증됐고 `matching_candidates`가 정확히 1건이면 그 레코드에만 binding한다.
9. 일치 후보가 0건 또는 2건 이상이면 해당 관리 계좌의 조회·주문을 닫고 critical을 낸다.
```

응답에 일치하지 않는 레코드가 여러 건 있다는 사실만으로 모호한 것은 아니다. 검증된 1:N 계약에서 일치 후보가 정확히 1건이면 나머지는 선택하지 않는다. 계약 미확인, 0건 일치, 복수 일치는 서로 다른 거부 사유로 기록하되 원식별자·digest·pepper는 기록하지 않는다.

pepper 회전은 새 secret 버전을 만든 뒤 사람이 계좌 등록·환경·원식별자를 다시 확인하고 public fingerprint 버전·digest 또는 opaque reference를 원자적으로 재프로비저닝한다. 모든 binding이 전환된 뒤 구버전을 폐기하며 자동 rehash·digest 갱신은 금지한다.

### 7.3 토큰 생명주기

- `dry_run`은 키움 토큰을 발급·조회·재사용하지 않는다.
- 공식 유효기간 24시간을 기준으로 `(managed_account_id, exec_env, derived_server_env)`별 토큰 캐시를 분리한다.
- 만료 전에 갱신하되 정확한 선제 갱신 여유와 발급 동시성은 계약 측정으로 정한다. 확인 전에는 직렬화와 단일 비행(single-flight)을 기본으로 한다.
- 인증 거부 뒤 제출성 요청을 무조건 재시도하지 않는다. 토큰 상태와 브로커 주문 존재 여부를 먼저 확정한다.
- 재시작 시 token namespace, endpoint, rate profile, binding의 실행/서버 환경과 계좌 fingerprint가 모두 같은 environment bundle에 속할 때만 재사용한다.
- `PAPER`/`MOCK` 성공은 `LIVE`/`REAL` 자격증명·계좌 등록·상품 지원 또는 세제계좌 의미론을 증명하지 않는다.

## 8. 키움 REST 전송과 실시간 경계

### 8.1 전송 구성

증권 어댑터는 다음 네 구성요소로 나눈다.

1. `KiwoomAuth`: 실행 모드에서 원자적으로 파생한 서버 환경별 OAuth 토큰과 계좌 binding.
2. `KiwoomRestClient`: 조회·주문·취소·정정·체결조회 단일 HTTP 경로.
3. `KiwoomRateLimiter`: 계좌·토큰·API 군·시간대별 상한과 bounded queue.
4. `KiwoomWebSocket`: 주문체결·잔고·시세 알림의 별도 세션.

상위 레이어는 `BrokerGateway`와 표준 이벤트만 본다. 공식 API ID, 경로, 응답 필드, 오류코드는 어댑터의 버전된 계약 레지스트리와 카세트가 소유한다. 이 설계는 확인하지 않은 API ID나 필드를 발명하지 않는다.

### 8.2 유량과 async 동시성

> **[결정 D-10] 브로커 유량은 안전 천장**
>
> 공식 유량은 limiter가 절대 넘지 않을 천장이지 목표 처리량이 아니다. 더 낮은 운영 예산은 허용하며, 상한을 채우는 것을 성능 성공으로 측정하지 않는다.

- limiter 키는 최소 `(exec_env, derived_server_env, account_binding, token, api_family)`를 포함한다.
- 국내 주문/조회, 미국 주문/조회/환전, 미국 피크 구간, 모의 TR별 상한을 서로 다른 프로파일로 표현한다.
- 공식 페이지의 미국 전체·차트·특정 목록 추가 한도도 교집합으로 적용한다.
- 요청 동시성은 유량 토큰과 별도의 작은 semaphore로 제한한다. semaphore 크기는 부하 시험으로 정하며 공식 초당 수치를 동시 연결 수로 해석하지 않는다.
- 우선순위는 상태 확정·체결조회·취소/정정·신규 주문·대화형 조회·배치 조회 순으로 안전하게 구성한다. 낮은 우선순위가 주문 상태 확정을 굶기면 안 된다.
- 계약으로 검증된 유량 제한 응답/오류를 성능 조정 신호로 기록한다. 제출성 호출은 자동 재전송하지 않고 §8.4의 모호 상태 절차로 보낸다.
- 동적으로 한도를 올리지 않는다. 공식 문서가 넓어져도 버전된 근거와 별도 설정 변경이 있어야 한다.

### 8.3 REST와 WebSocket 분리

WebSocket은 빠른 알림 채널이지 장부 정본이 아니다.

| 기능 | REST | WebSocket |
|---|---|---|
| 토큰·계좌 binding | 정본 | 사용하지 않음 |
| 잔고·보유 기동 스냅샷 | 정본 | 후속 알림 가능 |
| 주문 제출·정정·취소 | 정본 | 사용하지 않음 |
| 주문 접수·체결 빠른 감지 | 조회로 확정 | 알림 가속 |
| EOD·재시작·응답 유실 대사 | 정본 | 증거 보조만 |
| 시세·호가 | 폴백·스냅샷 | 허용된 실행 창의 빠른 입력 |

WebSocket 단절은 그 자체로 장부를 변경하지 않는다. REST 폴링과 대사로 퇴화하고, 주문 안전에 필요한 최신성이 없으면 신규 주문을 거부한다. 재연결 뒤에는 구독 성공과 계좌 binding을 다시 확인한다.

### 8.4 주문·체결·대사 원칙

역사적 한국투자증권 KIS 기준선에서 이미 승인된 다음 안전 원칙은 브로커 종속이 아니므로 유지한다.

1. **persist-before-submit**: 내부 주문과 의도·계좌·수량·가격·상태를 커밋한 뒤 REST 주문을 보낸다.
2. **맹목 재시도 금지**: 타임아웃이나 응답 유실 뒤 같은 주문을 다시 제출하지 않는다.
3. **모호 상태 격리**: 해당 계좌·시장에 submit hold를 걸고 공식 주문/체결 조회로 존재 여부를 확정한다.
4. **체결 중복 방지**: 공식 체결 식별자 또는 검증된 복합 키로 WS와 REST 중복을 제거한다. 사용할 키는 실제 응답 계약으로만 확정한다.
5. **REST 대사 정본**: 재시작, 창 종료, EOD에 주문·체결·잔고를 다시 조회한다.
6. **부분 체결 보존**: 확인된 체결분을 되돌리지 않고 미체결 잔량만 취소·재계획한다.
7. **시장가 자동 폴백 없음**: 주문유형 확대는 계좌·시장별 별도 증거가 필요하다.

공식 문서에서 client-supplied idempotency key가 확인되기 전에는 그런 필드가 있다고 가정하지 않는다. 없거나 미확인이면 persist-before-submit과 조회 대사가 유일한 중복 방어다.

## 9. 종단간 데이터 흐름

### 9.1 기동과 read-only 동기화

```text
버전된 public config와 ExecEnv 로드
  → ExecEnv 분기
    ├─ dry_run: 자격증명 없이 로컬 simulator/fixture readiness만 만들고 브로커 network·제출 경로 종료
    └─ paper/live: 각각 MOCK/REAL environment bundle을 원자적으로 파생·검증
         → secret provider에서 (managed_account_id, exec_env) 자격증명 조회
         → 해당 bundle의 OAuth 토큰 발급/검증
         → 공식 read-only 계좌 정체성 조회
         → 응답 계약 증거 확인과 matching_candidates 계산
         → 정확히 1개의 matching candidate에만 binding
         → capability matrix에서 조회 연산 허용 확인
         → 잔고·보유·가용현금·미체결 조회
         → 도메인 정규화와 스키마 검증
         → 로컬 장부·미완료 주문과 REST 대사
         → 계좌별 readiness 공개
```

어느 단계든 실패하면 그 계좌 readiness는 `DENY`다. 다른 계좌는 오염되지 않은 경우 독립적으로 read-only 상태를 유지할 수 있지만, 포트폴리오 전체 계획이 누락 계좌의 자산에 의존하면 계획 생성도 거부한다.

### 9.2 계획 → pre-trade → 제출 → 체결 → 대사

```text
검증된 시장·잔고 스냅샷
  → vendor-neutral sleeve별 목표/드리프트 계획
  → account × market × instrument × operation 능력 조회
  → 상품 유니버스·계좌 적격성·KRX-only 국내 정책 확인
  → 세금·감시·상태·매수여력·수량/호가 단위 pre-trade
  → order intent를 SUBMITTING으로 먼저 영속
  → 계좌/토큰 limiter와 bounded concurrency 획득
  → Kiwoom REST 제출
  → 응답 수신 시 broker order identity 결합
  → WebSocket 체결 알림으로 빠르게 반영
  → REST 주문/체결 재조회로 확정
  → 창 종료·EOD 잔고 대사
```

중개형 ISA와 연금저축은 일반위탁의 성공 결과를 상속하지 않는다. 같은 ETF라도 계좌별 적격성·응답·주문 결과를 별도로 검증한다.

### 9.3 외부 IRP 납입 → 세금 가이드

```text
본인의 수동 누적 납입액·as_of 입력
  → 현재 과세연도·미래일·음수·정상 snapshot/명시적 정정 검증
  → 시스템이 source=manual과 timezone-aware recorded_at 부여
  → 기존 chain과 unique head 무결성 검증
    ├─ 무결성 오류: 쓰기 DENY, 세금 가이드는 UNKNOWN으로 종료
    └─ 정상: 트랜잭션에서 expected head 확인
         → revision append와 unique head compare-and-swap
         → 결과 head의 신선도 판정
         → 명시적 UNKNOWN 상태·사유 또는 유효 contribution revision 확정
  → 계산·평가 as_of, 입력·규칙 선택 시각과 한국 업무 시간대 확정
  → 과세연도·effective-date tax rule/config revision 확정
  → 다른 연금 납입 snapshot/revision 또는 대상별 UNKNOWN 사유 확정
  → 잔여 납입 여력 또는 UNKNOWN
  → 필요한 소득·프로필 revision 또는 항목별 UNKNOWN 사유 확정
  → 예상 공제 또는 UNKNOWN
  → calculator/code/policy version을 포함한 완전한 provenance bundle 조립
  → 계산 결과와 versioned provenance bundle 원자 저장
  → 가이드·알림만 생성
```

이 흐름은 자금이체, IRP 로그인, 주문, 보유 조회를 만들지 않는다.

## 10. 오류 처리와 운영 게이트

### 10.1 오류 분류와 안전 방향

| 오류 | 안전 방향 | 복구 증거 |
|---|---|---|
| 자격증명 없음·ExecEnv/서버 bundle 불일치·`dry_run`의 broker secret 존재 | 네트워크 호출 전 해당 경로 중단 | 올바른 원자적 environment bundle과 token 검증 |
| 계좌 응답 계약 미확인 또는 `matching_candidates` 0건·2건 이상 | 해당 계좌 전면 중단, 자동 재결합 없음 | 1:1/1:N 계약 증거 + 사람이 등록 상태를 확인하고 정확히 1개 일치 후보 재검증 |
| 미확인 계좌/상품/연산 능력 | 주문 거부 | 공식 근거 + 계약 테스트 + 필요한 live gate |
| 응답 스키마 변화 | 해당 연산 거부, 원문은 마스킹 후 격리 | 새 스키마 버전 승인과 카세트 회귀 |
| 유량 초과 | 낮은 우선순위 축소, 제출성 호출 재전송 금지 | limiter 보정과 상태 조회 |
| 제출 응답 유실 | submit hold, 신규 주문 금지 | REST 주문/체결 대사 |
| WebSocket 단절·순서 이상 | REST 폴백, 최신성 부족 시 주문 거부 | 재구독 확인 + REST 대사 |
| 주문/체결/잔고 불일치 | 해당 계좌 HALT 성격의 무결성 중단 | 원인 설명·장부 정정·재대사 |
| ISA/연금 상품 적격성 불명 | 해당 주문 거부 | 계좌별 공식/실호출 증거 |
| IRP 입력 누락·stale | `UNKNOWN`, 0 대체 금지 | 새 수동 입력 |
| IRP 연도/날짜/누적 규칙 위반, stale expected head, fork 시도 | 쓰기 전체 거부, 기존 head 불변 | 현재 head를 다시 읽은 유효 snapshot 또는 사유가 있는 명시적 정정 |
| IRP head 복수·유실, chain 단절·fork·cycle | 읽기 `UNKNOWN`, 새 쓰기 거부, 무결성 경보 | 선형 chain과 unique head를 보존하는 감사된 복구 |
| 세법 버전 또는 필수 소득·프로필 불명 | 예상 세액공제 `UNKNOWN`; 근거 없는 기본 세율 사용 금지 | 승인된 effective-date 규칙과 검증된 입력 |
| 계산 provenance 구성요소 누락 또는 불변 참조 해석 불가 | 재현 가능 표시 금지; 기존 값은 `non-reproducible` 감사 이력으로만 격리하고 감사 가능한 근거가 필요한 현재 결과는 `UNKNOWN` | 완전한 versioned bundle, 해석 가능한 불변 revision·fingerprint·구현 version으로 재실행 |

### 10.2 `PAPER`/`MOCK`가 증명하지 않는 것

F-10·F-13은 미국 MOCK 시장과 HTTP·매수주문 request 정의의 존재를 증명한다. F-11·F-12의 KRX-only 주석은 국내 route 범위이며 미국 능력 부재로 일반화할 수 없다. 그럼에도 다음 추론은 지원 증거가 아니다.

- MOCK 일반위탁 성공 ⇒ 중개형 ISA 주문 지원
- MOCK 일반위탁 성공 ⇒ 연금저축 주문 지원
- 국내 KRX MOCK 성공 ⇒ 미국 주문·체결·대사 지원
- 미국 MOCK request 정의 또는 일부 성공 ⇒ 전체 주문·체결·대사·WebSocket 행동이나 REAL parity
- MOCK 주문 성공 ⇒ LIVE/REAL 계좌 등록·허용 IP·자격증명 결합 성공
- MOCK ETF 성공 ⇒ 해당 세제계좌의 상품 적격성 성공

`ExecEnv.PAPER`는 검증된 MOCK 계약에서 코드 경로·스키마·실패 처리를 확인하는 증거다. MOCK 성공은 REAL 또는 세제계좌 지원 증명이 아니며, 세제계좌 지원 증거는 계좌별 read-only 응답과 통제된 LIVE/REAL 검증에서만 얻는다.

### 10.3 live 검증 게이트

모든 `ExecEnv.LIVE`/키움 `REAL` 증권 계좌는 다음 순서를 통과해야 한다.

1. **근거 게이트**: 관찰일·URL·지원 문언·미확인 범위를 담은 evidence revision 승인.
2. **binding 게이트**: LIVE/REAL 키, 허용 IP, 계좌 등록, 검증된 응답 계약 아래 `matching_candidates` 정확 1건.
3. **read-only 게이트**: 잔고·보유·가용현금·미체결·체결조회 스키마와 페이지네이션 카세트.
4. **실패 게이트**: 인증 만료, 유량, 네트워크 유실, 미확인 응답 계약, 일치 후보 0/복수, 스키마 변화가 모두 거부 방향임을 증명.
5. **DRY_RUN/PAPER 게이트**: 로컬 simulator에는 broker secret·제출이 없고, PAPER/MOCK에는 환경 혼합·중복 제출이 없으며 REST 대사를 회수함을 증명.
6. **사람 승인 LIVE/REAL 절차**: 대상 계좌·환경·시장·승인 ETF·방향·최대 수량/금액·허용 시간·사전 잔고·취소 조건·비상 중단·사후 체결/잔고 대사·증거 보관·롤백을 문서화하고, 실행 직전 사람이 다시 확인한다.
7. **무결성 게이트**: 주문·체결·잔고·감사로그가 일치하고 열린 주문과 submit hold가 0임을 독립 확인한다.

연금저축은 위 공통 게이트 외에 다음 네 증거가 모두 필요하다.

- 실제 대상 계좌가 API 관리 화면에 정확히 등록됨
- read-only 응답이 일반위탁과 섞이지 않고 정확히 binding됨
- 승인 국내 KRX ETF의 허용/거부 행동이 계좌별로 확인됨
- 통제된 LIVE/REAL 주문·취소·체결·대사 절차가 성공하고 사람의 명시적 활성 승인이 남음

이 중 하나라도 없으면 연금저축 `live_order_enabled`의 실효값은 항상 `false`다.

## 11. 보안, 개인정보, 운영 전제

### 11.1 보안·개인정보 불변식

- 개인 자가 호스팅, 본인 명의 계좌, 본인 자금만 범위다.
- 타인 계좌 자격증명 수탁, 타인 주문, 다사용자 계좌 운영을 가정하지 않는다.
- App Key, App Secret, 접근 토큰, 원계좌번호는 Git·YAML·DB 일반 컬럼·로그·알림·카세트에 남기지 않는다.
- 계좌 fingerprint는 §7.1의 versioned domain-separated HMAC-SHA-256만 사용한다. key/pepper는 secret provider에만 두고 원계좌번호·key·digest를 로그에 남기지 않으며, plain/unkeyed hash와 짧은 prefix를 금지하고 전체 digest를 constant-time 비교한다.
- key rotation은 사람의 계좌 재확인과 public version/digest 또는 opaque reference의 원자적 재프로비저닝을 요구한다.
- 키움 공식 허용 IP를 최소 집합으로 등록하고 사용하지 않는 IP는 제거한다.
- PAPER/MOCK와 LIVE/REAL secret namespace·token store를 물리·논리적으로 분리하고, DRY_RUN에는 브로커 secret을 공급하지 않는다.
- 계좌번호가 포함될 수 있는 공식 응답은 공용 masking 코드가 HTTP 기록·감사로그·테스트 카세트 모두에 적용된 뒤에만 보관한다.
- 화면과 알림은 내부 `managed_account_id`와 마스킹 식별자만 쓴다.
- IRP 외부 입력에는 계좌번호를 입력할 UI·CLI·API 필드 자체를 만들지 않는다.
- 운영 자격증명을 third-party telemetry, hosted error reporting, 모델 입력으로 전송하지 않는다.
- 실거래 활성화는 수동 배포와 명시적 설정 변경을 요구한다. 근거 변화가 자동 설정 변경으로 이어지지 않는다.

### 11.2 비목표

이 전환은 다음을 만들지 않는다.

- 고전 OpenAPI+ 또는 Windows 보조 런타임
- 두 증권사를 동시에 선택하는 멀티브로커 제품
- 타인 계좌 운용·상용 투자일임 기능
- IRP 계좌 조회·성과·자산배분·주문
- 신탁형·일임형 ISA 관리
- NXT/SOR 자동주문
- 개별주·ETN·API가 새로 노출한 상품의 자동 편입
- 키움 연금저축/ISA의 완전한 상품 허용 목록 주장
- 세법 한도·세율의 코드 하드코딩 또는 법률·세무 결과 보증
- WebSocket을 장부 정본으로 사용하는 구조
- 브로커 한도를 채우기 위한 불필요한 호출

## 12. 문서 기준선 마이그레이션 원장

이 절은 **후속 문서 카드의 작업 지도**다. 아래 파일이 이 카드에서 수정됐다는 뜻이 아니다. 변경되지 않은 이 기준선에 대응하는 issue #49의 전체 문서 감사를 역사적 감사 입력으로 사용했으며, 이 카드가 아래 모든 파일을 독립적으로 다시 읽었다고 주장하지 않는다.

### 12.1 `docs/plan` 소유 파일

후속 기준선 마이그레이션 카드가 아래 여덟 파일을 한 정합 단위로 소유한다.

| 파일 | 바꿀 정본 내용 |
|---|---|
| `docs/plan/00-overview.md` | 증권사·계좌 범위·ETF 전용 정책·IRP 외부 입력·비목표·자동화 등급의 브로커 전제 |
| `docs/plan/01-architecture.md` | 모듈 트리, Broker/Sleeve 식별자, 계좌 binding, OAuth/유량/세션, 기동·잡·API 예산, 역사적 TR 가정 제거 |
| `docs/plan/02-investment-engine.md` | 관리 계좌 집합, asset location에서 IRP 제거, vendor-neutral sleeve, 계좌별 주문 능력, IRP 납입 UNKNOWN 의미론, 실행·세금 흐름 |
| `docs/plan/03-safety-operations.md` | 계좌/시장별 fail-closed, submit hold, capability 만료, Kiwoom 오류·유량, 세제계좌 live gate, 활성 식별자 |
| `docs/plan/04-roadmap.md` | 역사적 한국투자증권 KIS 스파이크를 키움 evidence/read-only/order/live 게이트와 §15 카드 순서로 대체 |
| `docs/plan/05-research-appendix.md` | 브로커·세제계좌·유량·실시간 근거를 §3의 키움 공식 1차 자료로 교체하고 사실/결정/미확인을 분리 |
| `docs/plan/06-realtime-and-surveillance.md` | 키움 REST/WS 이벤트·세션·폴백·감시 소스, KRX-only 정책, 공식 범위보다 좁은 ETF 정책 |
| `docs/plan/07-self-improvement.md` | 브로커 공식 근거 수집원을 키움으로 바꾸되 공식 변화가 AUTO를 직접 켜지 못하는 승격 게이트 |

### 12.2 `docs/design` 소유 파일

후속 기준선 마이그레이션 카드는 파일별 기존 소유권을 유지하며 아래 열일곱 파일을 함께 정합시킨다.

| 파일 | 바꿀 설계 계약 |
|---|---|
| `00-design-overview.md` | 승인된 전환 지시의 감사 기록 링크, 문서 맵·공통 기호·조건부 게이트·역사적 브로커 표현 제거 |
| `01-system-architecture.md` | composition root, 키움 태스크·세션·계좌별 클라이언트, 의존 규율, startup/read 흐름 |
| `02-domain-model.md` | `Broker.KIWOOM`, 세 슬리브, 관리 IRP 제거, 외부 납입 타입, 오류·식별자 |
| `03-data-and-persistence.md` | enum/check 값, token/binding/capability/evidence, external contribution, 오프라인 값 변환, 인덱스·감사 |
| `04-configuration-and-secrets.md` | 기존 ExecEnv와 MOCK/REAL 파생, 키움 계좌×실행환경 secret, HMAC fingerprint, 능력 기본 거부, IRP 외부 입력, config 파일명·교차 제약 |
| `05-broker-gateway.md` | 키움 REST/OAuth/유량/WebSocket/오류/계좌 binding 전체. 역사적 브로커 전용 프로토콜을 공식 키움 계약으로 대체 |
| `06-market-data-and-calendar.md` | 키움 시세·휴장·환율·ETF 데이터 포트와 fallback; 공식 응답이 없는 소스는 미확인 유지 |
| `07-portfolio-engine.md` | vendor-neutral sleeve와 관리 계좌 집합, IRP 배분/성과 제거, 계좌 능력에 따른 계획 거부 |
| `08-execution.md` | 키움 주문·정정·취소·체결조회, 능력 게이트, vendor-neutral 라우팅, 모호 상태·대사 |
| `09-safety-protections.md` | 계좌 binding/capability/스키마/유량 보호, 새 슬리브 값, IRP 주문 경로 부재 |
| `10-tax-engine.md` | IRP 관리 계좌·70% 제약·브로커 집계 제거, external contribution·UNKNOWN·effective-date 계산 경계 |
| `11-realtime-and-surveillance.md` | 키움 WebSocket 이벤트·REST 폴백·세션 한도·KRX/NXT/SOR 판정 경계 |
| `12-scheduling-and-operations.md` | 계좌별 토큰·readiness·대사·evidence expiry·live gate·IRP 입력 알림 잡 |
| `13-web-and-telegram.md` | 키움 연결 상태, 마스킹 binding, capability 이유, IRP `UNKNOWN`/as-of 표시; 계좌번호 입력 금지 |
| `14-research-and-labs.md` | 공식 키움 근거 수집과 evidence revision; 연구 결과가 capability를 자동 승격하지 못하는 경계 |
| `15-backtest-and-validation.md` | vendor-neutral broker fixtures, 국내 PAPER/MOCK의 KRX-only 범위와 별도로 미확인인 미국 MOCK 계약, 계좌별 계약·대사 시나리오 |
| `16-testing-and-quality.md` | §14의 계약·property·failure·security·식별자 검증과 live 증거 DoD. `docs/design/16-testing-and-quality.md`의 KIS cassette 경로·group·catalog 이름은 역사적 마이그레이션 입력이며 후속 기준선 마이그레이션 카드가 키움 또는 vendor-neutral 이름과 새 계약으로 교체 |

### 12.3 `docs/engineering`, 기여 정책, 과거 구현 계획

| 파일/가족 | 후속 소유와 처리 |
|---|---|
| `docs/engineering/README.md` | 문서 기준선 마이그레이션 카드가 이 승인된 전환 기록과 새 기준선의 관계를 인덱싱한다. 제품 결정을 복제하지 않는다. |
| `docs/engineering/development-workflow.md` | 일반 workflow 소유를 유지한다. 외부 capability 증거와 계좌별 live gate가 기존 추적성·검증 규칙으로 충분한지 확인하고, 제품 세부값은 넣지 않는다. |
| `docs/engineering/document-baseline-migration.md` | 완료된 과거 감사 기록이므로 다시 쓰지 않는다. issue #49의 당시 결론을 보존한다. |
| `CONTRIBUTING.md` | 브로커 제품 정의를 넣지 않는다. 현재 branch/commit/검증 정책만 유지한다. |
| `docs/plans/2026-08-19-m0-container-runtime.md` | 완료된 M0 구현 계획의 역사적 스냅샷으로 유지한다. 후속 키움 구현은 새 날짜의 계획 파일을 만들고 이 파일을 현재 제품 정본으로 갱신하지 않는다. |

기준선 마이그레이션이 실제로 merge되고 계획·설계 전체의 활성 한국투자증권 KIS 전제가 제거된 뒤에만 issue #49를 superseded 또는 재범위화할 수 있다. 이 카드에서는 issue #49의 상태·범위·본문을 바꾸지 않는다.

## 13. 소스·설정·스키마·영속·테스트 마이그레이션 원장

### 13.1 소스와 패키지

| 영역 | 역사적 마이그레이션 입력 | 목표와 소유 |
|---|---|---|
| 핵심 계좌 | `src/omra/core/accounts.py`의 역사적 broker/sleeve/IRP enum | core 카드가 §6 식별자와 관리/외부 경계를 구현 |
| 증권 어댑터 | 역사적 `src/omra/brokers/kis/` 좌표 | broker 카드가 `src/omra/brokers/kiwoom/`으로 완전 교체; 런타임 호환 어댑터 없음 |
| 게이트웨이 공통 | `src/omra/brokers/base.py`, masking | vendor-neutral ABC와 공용 masking 유지, 계좌 binding·능력 계약 추가 |
| 아키텍처 의존 계약 | `pyproject.toml` import-linter의 C05a·C06a·C09가 금지 모듈로 가리키는 역사적 `omra.brokers.kis.client` | source migration 카드가 세 계약의 금지 좌표를 `omra.brokers.kiwoom.client`로 원자적으로 교체하고 기존 직접 의존 금지를 그대로 유지한다. 역사적 경로만 삭제해 경계를 약화하는 변경은 금지한다. |
| 설정 모델 | `src/omra/config/files/trids.py`, `schema/*`, `secrets.py`, `constraints.py` | 키움 공식 계약, 기존 `ExecEnv={dry_run,paper,live}`와 MOCK/REAL 파생, 계좌×실행환경 secret, HMAC fingerprint, 새 sleeve, 관리 IRP 거부, capability 기본 거부 |
| 포트폴리오·집행·세금 | M0의 다수 스텁과 일부 순수 도메인 | 기준선 마이그레이션 뒤 소유 plan/design에 반영된 §9 흐름과 §4 행렬을 구현; IRP import가 execution/portfolio에 들어가지 않도록 아키텍처 테스트 |
| 데이터·감시·실시간·스케줄 | 역사적 벤더 이름 source 키와 스텁 | vendor-neutral 소비 포트 + `kiwoom_*` 전송 source, REST/WS 퇴화, 계좌별 readiness |

### 13.2 설정과 비밀정보

| 대상 | 후속 처리 |
|---|---|
| 역사적 `config/tr_ids.kis.yaml` | `config/tr_ids.kiwoom.yaml`로 교체하고 공식 API ID와 MOCK/REAL별 endpoint·rate profile은 검증된 값만 기록한다. endpoint·profile은 `ExecEnv`에서 파생하는 하나의 bundle로 선택하고 역사적 파일 fallback은 두지 않는다. |
| `config/config.yaml` | 기존 `ExecEnv={dry_run,paper,live}`를 유지하고 `dry_run→local/no broker credential`, `paper→MOCK`, `live→REAL`을 결정론적으로 적용한다. 관리 계좌에서 IRP 제거; broker·market·capability·새 sleeve 명시; 연금 live 기본 false |
| `config/universe.yaml` | ETF 전용 허용과 계좌별 적격성 증거 상태를 분리; NXT/SOR·개별주·ETN을 명시 거부 |
| `config/tax.yaml` | 실제 한도·세율과 적용일은 versioned effective-date 규칙으로 유지하고, 외부 IRP 납입을 소비하는 규칙 스키마만 후속 세금 카드가 정합시킨다. 이 설계에 수치를 복제하지 않는다. |
| `src/omra/config/schema/taxcfg.py`의 역사적 기본 세액공제율과 소유 public config | 고정 기본값을 알려진 소득·프로필로 취급하지 않도록 마이그레이션한다. 검증된 선택 입력이 없으면 예상 공제는 `UNKNOWN`이고, 실제 세율은 `config/tax.yaml`의 effective-date 규칙이 소유한다. |
| `config/external_income.yaml` | 기존 외부 금융소득 계산식으로 유지한다. 근로·종합소득 프로필이나 IRP 납입 입력으로 재사용하지 않는다. |
| `config/secrets_registry.yaml` | 키움 자격증명·토큰을 계좌×`exec_env`에 연결하고 vendor-neutral sleeve 영향 범위를 기록한다. public에는 fingerprint 버전+전체 digest 또는 opaque reference만 허용하고 원계좌번호·HMAC key/pepper는 secret provider에만 둔다. |
| `config/surveillance.yaml`, 관측/연구 기본값 | 역사적 source 이름을 키움 또는 vendor-neutral source로 교체; 공식 변화가 AUTO flag를 켜지 못함 |
| 프로세스 secret namespace | 역사적 secret 이름을 제거하고 `KIWOOM` namespace로 완전 교체한다. 직렬화 이름보다 `(managed_account_id, exec_env, secret_kind)` 의미 계약이 정본이고 서버 환경은 `paper→MOCK`, `live→REAL`로만 파생한다. `dry_run` namespace에는 broker secret이 없다. |
| IRP 수동 입력 | 비밀정보 파일이나 계좌 설정이 아니라 §13.4의 append-only 외부 납입 저장/API를 사용한다. |

### 13.3 스키마와 활성 영속 식별자

| 저장 대상 | 마이그레이션 규칙 |
|---|---|
| account/broker enum | 활성 `KIS` 값을 `KIWOOM`으로 일회 변환하고 이후 역사적 값을 CHECK/validator에서 거부 |
| sleeve enum | `kis_domestic → domestic_securities`, `kis_overseas → us_securities`, `upbit → crypto` 일회 변환 |
| 관리 accounts | IRP 행은 live 마이그레이션 대상이 아니다. M0 개발 데이터에 존재하면 자동 승격하지 않고 운영자 검토 없이 기동을 거부한다. 새 스키마는 관리 IRP를 허용하지 않는다. |
| broker token/cache | 역사적 증권 토큰·세션은 변환하지 않고 폐기한다. 현재 schema의 `live`/`paper` 실행 값을 `ExecEnv.LIVE`/`ExecEnv.PAPER` 의미로 일관되게 보존해 각각 REAL/MOCK token namespace를 새로 만들고, `dry_run`에는 token row를 만들지 않는다. secret 자체는 DB migration 대상이 아니다. |
| source 값·휴장 캐시·감시 기록 | 활성 벤더 source enum을 키움으로 바꾼다. immutable pre-live 감사 기록을 보존하면 schema/version과 `historical` 표기를 붙이고 활성 상태 질의에서 제외한다. |
| orders/fills/reconciliation | 비종결 주문이 있는 DB에서는 브로커 전환을 실행하지 않는다. M0 개발 DB라도 열린 주문 0건을 확인한 뒤 식별자를 변환한다. |
| evidence/capability | 공식 URL·revision, 관찰일, 계좌/시장/상품/연산, 애플리케이션 `ExecEnv`와 파생 서버 환경, 검증 결과, 만료/철회 상태를 저장하고 긍정 allow의 provenance로 사용한다. |
| 세금 가이드 결과/provenance | 결과 값·상태와 §5.3의 완전한 versioned logical bundle을 원자 저장한다. 모든 참조는 보존된 불변 revision·snapshot·fingerprint를 해석할 수 있어야 하며, 물리 스키마와 retention은 후속 세금·영속 카드가 소유한다. |

### 13.4 외부 납입 영속 계약

IRP 전용 append-only `external_tax_contributions` revision 테이블과 unique-head registry는 다음 의미를 가진다. 물리 DDL은 데이터·영속 카드가 소유한다.

| 필드 | 의미 |
|---|---|
| `id` | 내부 opaque revision 식별자 |
| `tax_year` | 납입이 귀속되는 과세연도 |
| `cumulative_contributed_krw` | 해당 연도 누적 납입액, 정확한 Decimal 값 |
| `as_of` | 누적액이 사실인 기준일 |
| `source` | 시스템 통제 상수 `manual` |
| `recorded_at` | 설정된 한국 업무 시간대에 맞춘 timezone-aware 서버 기록 시각 |
| `supersedes_id` | 최초 revision은 `null`; 이후 revision은 쓰기 시점 current head의 `id` |
| `change_kind` | 시스템 통제 audit metadata인 `snapshot` 또는 `correction`; 납입·세금 계산값이 아님 |
| `correction_reason` | `correction`에만 필요한 비어 있지 않은 감사 사유; 사용자 세금 입력이 아님 |

revision 행은 갱신·삭제하지 않는다. 별도 head registry는 `tax_year`를 unique key로 하고 정확히 하나의 `revision_id`만 가리킨다.

쓰기 트랜잭션은 기존 chain과 head 무결성을 먼저 확인한 뒤 호출자가 본 expected head를 비교하고, 그 head를 `supersedes_id`로 삼은 새 revision append와 head pointer 교체를 원자적으로 수행한다. 최초 쓰기는 expected head와 `supersedes_id`가 모두 `null`이어야 한다. non-null `supersedes_id`의 uniqueness와 head compare-and-swap으로 fork를 막고, 경쟁·stale head·중복 head는 revision insert까지 롤백한다.

모든 revision은 `tax_year == as_of.year`, 설정된 한국 업무 시간대에서 비미래 날짜, 비음수 금액을 만족한다. 정상 snapshot은 `as_of`와 금액이 current head보다 비감소해야 한다. 감소는 current head를 잇는 명시적 `correction`과 사유로만 append한다.

계산기는 timestamp 최대값이 아니라 unique head를 선택하고 요구 기준일로 신선도를 판정한다. 레코드 없음·stale 또는 head/chain 단절·복수·fork·cycle이면 `UNKNOWN`을 반환한다.

파생 세금 결과 저장은 이 외부 납입 입력 테이블과 분리하며 §5.3의 계약을 따른다. contribution revision 식별자 하나만으로는 평가 시각, 세법·설정, 다른 납입, 소득·프로필, 구현·정책을 재현할 수 없다.

결과와 완전한 versioned provenance bundle을 원자 저장하고, 역사 재실행은 current head나 current config가 아니라 bundle이 고정한 불변 참조만 해석한다. bundle이 불완전하면 재현 가능하다고 주장하지 않는다.

`external_tax_contributions`의 금지 컬럼은 `account_id`, `broker`, `account_number`, `positions`, `performance`, `trades`, `tax_amount`다.

### 13.5 테스트 소유 영역

| 테스트 가족 | 필수 전환 |
|---|---|
| core 단위/property | 새 Broker/Sleeve 값, 시장 라우팅, 관리 IRP 생성 거부, 정확히 다섯 의미 필드인 외부 납입 타입 |
| 기존 core/config fixture | `tests/unit/core/test_sleeves.py`, `test_accounts.py`와 `tests/unit/config/test_app_config_engine_defaults.py`, `test_app_config_safety_defaults.py`, `test_app_config_contract.py`, `test_secrets_registry_file.py`의 활성 역사적 broker/sleeve/secret 기대값을 함께 전환 |
| 감사 payload registry | `tests/unit/audit/test_payload_registry.py`의 현재 활성 역사적 `kind="kis_access"`와 `group="kis.balance"`를 versioned Kiwoom 또는 vendor-neutral 감사 vocabulary로 교체한다. `PAYLOAD_MODELS` 전수와 EventType별 정확한 payload model 검증, schema/version·미등록 vocabulary 거부 계약을 보존하며 필드 삭제나 validator 완화로 통과시키지 않는다. |
| 활성 fixture 전수 | `tests/unit/config/**`, `tests/unit/persistence/**`, `tests/unit/cli/**`, `tests/unit/audit/**`, `tests/arch/**`의 config·영속·CLI·감사 vocabulary와 직렬화 기대값을 전수 검색해 키움 또는 vendor-neutral 값으로 전환한다. 이름이 명시된 오프라인 migration fixture와 schema/version+`historical`로 격리한 immutable pre-live 감사 레코드만 예외이며, 활성 registry·sample·현재값 기대는 예외가 아니다. |
| 공개 package 좌표 | `tests/arch/test_package_coordinates.py`의 필수 `omra.brokers.kis.client`·`omra.brokers.kis.ws.events`를 각각 `omra.brokers.kiwoom.client`·`omra.brokers.kiwoom.ws.events`로 원자 교체하고, masking·Upbit·core/data 등 나머지 필수 좌표와 first-level package 집합 검사를 보존 |
| import-linter 아키텍처 | `pyproject.toml` C05a·C06a·C09가 `omra.brokers.kiwoom.client` 직접 의존을 계속 금지하는지 실행 검증; 역사적 경로 삭제만으로 계약을 느슨하게 하지 않음 |
| config 단위 | 기존 `ExecEnv` 세 값과 DRY_RUN→local/PAPER→MOCK/LIVE→REAL mapping, half-switch 거부, HMAC fingerprint·회전, history 값 거부, 연금 live false, ETF allowlist |
| persistence/migration | enum 일회 변환, 환경별 token 폐기/재발급, 열린 주문 차단, IRP 최초 null link·선형 chain·unique head/CAS 경쟁·동일액 신선도·감소 정정·미래/교차연도/late snapshot 거부, 세금 결과+완전한 provenance bundle 원자 저장과 불변 참조 보존 |
| broker 계약 | OAuth 24h, PAPER/MOCK와 LIVE/REAL 분리, 응답 계약+일치 후보 binding, 공식 rate/peak/additional limits, 계약으로 검증된 rate-limit 오류 fixture, 미국 MOCK HTTP/주문/WS와 REAL parity의 독립 검증, REST/WS |
| execution 통합·장애주입 | persist-before-submit, ack 유실, 부분체결, 중복 이벤트, reconnect, REST 대사, 계좌별 submit hold |
| capability property | 행렬에 없는 임의 조합과 `unknown`이 주문 0건을 만든다. API가 ETN/NXT/SOR를 반환해도 주문 0건이다. |
| tax 단위/property | IRP 누락/stale/chain 무결성 오류 `UNKNOWN`, 0 폴백 없음, unique head 선택, effective-date 규칙, 소득/profile 미상 시 예상 공제 `UNKNOWN`; IRP 상태·평가 문맥·세법/config·다른 납입·소득/profile·calculator/code/policy provenance 전량을 고정한 replay, current 값 대체 금지, 불완전/해석 불가 bundle의 `non-reproducible`·`UNKNOWN` 판정 |
| security/architecture | 원계좌번호·HMAC key/pepper·키·토큰이 config/log/cassette에 없음; plain/unkeyed hash·짧은 prefix 금지와 표준 constant-time 비교; IRP에서 portfolio/execution으로 import 경로 없음 |
| 문서 품질 | 활성 역사적 식별자 0건, 링크/anchor/표/fence, 사실·결정·미확인 source trace |

## 14. 증거·테스트 전략과 측정 가능한 수용 기준

### 14.1 증거 계층

1. **공식 문서 snapshot**: URL, 관찰일, 지원 문언, 적용 범위, 서로 다른 공식 페이지의 차이.
2. **계약 fixture**: 비밀정보를 제거한 실제 read-only/주문/체결/오류 응답 스키마.
3. **결정론적 테스트**: 파서, binding, limiter, capability, 상태 전이, IRP UNKNOWN.
4. **장애 주입**: token 만료, 계약으로 검증된 rate-limit 응답/오류 fixture, timeout, ack 유실, WS 단절, 중복·역순 체결, 대사 불일치.
5. **환경 검증**: DRY_RUN local/no-credential → PAPER/MOCK의 계약 확인 → 사람이 승인한 LIVE/REAL 절차.
6. **운영 관찰**: 계좌별 readiness, limiter 여유, submit hold, reconciliation 결과, evidence revision.

### 14.2 구현 완료 수용 기준

후속 구현은 아래 전부를 실제 출력으로 증명해야 한다.

- 활성 source/config/schema와 config·persistence·CLI·audit 테스트 fixture/직렬화 vocabulary에서 역사적 `Broker.KIS`, `kis_domestic`, `kis_overseas`, `KIS_*`, `kis_access`, `kis.balance` 값과 `SleeveId`로 쓰인 `upbit`가 0건이다. `Broker.UPBIT`는 유지한다. 허용 예외는 이름이 명시된 오프라인 migration fixture, schema/version+`historical`로 활성 질의에서 격리한 immutable pre-live 감사 레코드, 역사적 문서 문맥뿐이다.
- `tests/unit/audit/test_payload_registry.py`는 새 versioned Kiwoom/vendor-neutral kind·group으로 모든 EventType의 정확한 payload model을 계속 검증하며, 감사 payload registry의 필드·schema/version·미등록 vocabulary 거부 계약은 약해지지 않는다.
- `Broker` 활성 값은 `KIWOOM`, `UPBIT`; `SleeveId` 활성 값은 `domestic_securities`, `us_securities`, `crypto`다.
- `pyproject.toml` C05a·C06a·C09의 금지 모듈은 모두 `omra.brokers.kiwoom.client`로 교체돼 기존 의존 금지를 유지하고, `tests/arch/test_package_coordinates.py`는 키움 client/WS 좌표를 요구하며 역사적 KIS 좌표는 요구하지 않고 나머지 필수 좌표를 보존한다.
- `ExecEnv.DRY_RUN`은 broker secret·token·네트워크 제출 0건, `PAPER`는 MOCK bundle만, `LIVE`는 REAL bundle만 사용한다. endpoint/key/token/rate profile/binding의 모든 half-switch 조합은 네트워크 호출 0건이다.
- 관리 account config/model/schema가 IRP를 거부하고, IRP가 broker secret 요청·잔고 sync·allocation·performance·order를 발생시키는 테스트가 전부 0건이다.
- 응답 1:1/1:N 계약 증거가 없으면 반환/일치 건수와 무관하게 binding 0건이다. 계약 검증 뒤 `matching_candidates`가 0건 또는 2건 이상이면 binding 0건이고, 정확히 1건이면 여러 비일치 반환 레코드가 함께 있어도 그 후보 하나만 binding한다.
- 계좌 fingerprint는 versioned domain-separated HMAC-SHA-256과 표준 constant-time 비교를 사용한다. 환경이 다르면 digest가 다르고, plain/unkeyed hash·짧은 prefix는 거부되며, pepper 회전 뒤 사람의 재확인·원자적 재프로비저닝 전 binding은 0건이다.
- 모든 계좌·시장·상품·연산 조합의 기본값이 `DENY`이고 §4.2의 목표 allow도 증거·운영 게이트 전에는 주문 0건이다.
- 공식 미국 MOCK 시장·request 정의만으로 AUTO 주문은 0건이다. 미국 HTTP 조회·주문·체결·대사, MOCK WebSocket, REAL parity는 각각 실행된 계약 fixture와 해당 운영 게이트가 있어야만 별도로 허용된다.
- limiter가 공식 국내·미국·피크·모의·추가 한도를 넘지 않으며, 부하 테스트에서도 한도를 채우는 것을 성공 기준으로 삼지 않는다.
- 제출 직후 응답 유실을 주입해도 신규 중복 주문이 0건이고 REST 대사가 상태를 확정한다.
- WebSocket을 끈 경로와 켠 경로의 최종 주문·체결·잔고가 REST 대사 후 동일하다.
- 중개형 ISA와 연금저축의 적격성 `unknown`에서 주문 0건이다.
- 연금저축 live 주문은 §10.3의 추가 증거가 하나라도 없으면 0건이다.
- IRP 입력 없음과 stale 각각에서 납입액/잔여 여력 출력이 `UNKNOWN`이며 숫자 0이 아니다.
- IRP 최초 revision만 `supersedes_id=null`이고 이후 revision은 당시 head를 잇는다. 병렬 CAS는 1건만 성공하며 stale head/fork는 롤백된다. 같은 금액의 더 늦은 `as_of`는 freshness revision으로 append되고, 과거 과세연도 신규 입력·교차연도·미래일·이전 날짜 일반 snapshot은 거부되며 감소는 사유가 있는 정정만 허용된다. head 유실·복수·단절·fork·cycle은 `UNKNOWN`이고, `recorded_at`은 한국 업무 시간대 기준 서버 시각이다.
- 모든 세금 계산 결과는 IRP revision 또는 명시적 누락/stale 상태, 평가 `as_of`·선택 시각, effective tax-rule/config revision·fingerprint, 다른 납입 snapshot/revision, 소득·프로필 revision 또는 항목별 UNKNOWN 사유, calculator/code/policy version을 포함한 완전한 versioned provenance bundle과 원자 저장된다.
- replay 테스트가 current IRP head·세법/config·다른 납입·소득/profile을 바꾼 뒤에도 bundle의 불변 참조로 동일한 결과 값·상태를 산출한다. 필수 구성요소 누락 또는 참조 해석 실패는 재현 가능으로 표시되지 않고, 감사 가능한 근거가 필요한 결과는 `non-reproducible` 이력 또는 `UNKNOWN`으로 닫히며 current 값으로 대체되지 않는다.
- 필수 소득·프로필이 없으면 예상 세액공제가 `UNKNOWN`이다.
- 원계좌번호·HMAC key/pepper·App Key·App Secret·접근 토큰이 Git diff, public config, 감사로그, 예외, 카세트에 0건이고 fingerprint digest도 로그에 0건이다.
- 기존 계획·설계 기준선 마이그레이션 뒤 모든 소유 문서가 이 행렬·도메인·IRP 경계와 일치하고, issue #49 처리 여부는 그 merge 이후에만 결정된다.

### 14.3 이 설계 카드 자체의 수용 기준

- tracked diff는 이 파일 하나다.
- 기존 `docs/plan`, `docs/design`, `docs/engineering`, source/config/schema/test 파일은 변경하지 않는다.
- 공식 근거는 §3의 키움 1차 자료만 사용한다.
- 확인하지 않은 API ID·계좌 코드·응답 필드·세법 수치가 없다.
- 모든 미확인 능력에는 확인 방법과 거부 폴백이 있다.

## 15. 후속 카드의 순서

각 카드는 앞 카드의 merge된 증거를 입력으로 받는다. 하나의 카드가 여러 단계의 live 권한을 동시에 열지 않는다.

1. **공식 증거·계약 카탈로그 카드** — §16 질문을 공식 문서와 안전한 read-only 호출로 좁히고 evidence schema를 확정한다.
2. **기존 문서 기준선 마이그레이션 카드** — 승인된 전환 지시와 이 감사 기록을 입력으로 §12의 `docs/plan`·`docs/design`·필요한 engineering 인덱스를 정합시킨다. 이 merge 후에만 구현 계획을 승인하고 issue #49를 supersede/re-scope할 수 있다.
3. **도메인·식별자·오프라인 영속 마이그레이션 카드** — Broker/Sleeve/관리 IRP 경계를 바꾸고 활성 역사적 값·열린 주문을 검사한다.
4. **설정·비밀정보·계좌 binding·외부 IRP 스키마 카드** — ExecEnv→MOCK/REAL bundle, 계좌×실행환경 secret, HMAC fingerprint·회전, capability 기본 거부, unique-head append-only 납입 입력과 세금 결과/provenance 영속 계약을 구현한다.
5. **키움 OAuth·read-only REST·limiter 카드** — 일반위탁부터 계좌 조회·잔고·보유·미체결·체결 계약과 오류를 구현한다. 주문 코드는 열지 않는다.
6. **키움 주문·체결·WebSocket·대사 카드** — 일반위탁 KRX의 persist-before-submit과 모호 상태·REST 대사를 DRY_RUN local simulator와 PAPER/MOCK까지 구현한다.
7. **일반위탁 시장 게이트 카드** — KRX LIVE/REAL 검증과 미국 HTTP/order/fill/reconciliation·WebSocket·REAL parity 증거를 각각 독립 게이트로 연다.
8. **중개형 ISA 카드** — 계좌 binding·read-only·ETF 적격성·주문·대사를 별도 증거로 검증하고 승인 조합만 AUTO로 연다.
9. **연금저축 카드** — §10.3 네 추가 증거와 사람 LIVE/REAL 절차를 완료한 뒤에만 AUTO 활성을 검토한다.
10. **운영·보안·레거시 폐쇄 카드** — 모니터링·runbook·fingerprint key와 broker secret rotation·evidence expiry를 완성하고 역사적 런타임 경로가 없음을 최종 검사한다.

IRP 관리 지원은 위 목록에 없다. 향후 공식 지원 문서가 나와도 새 근거 revision과 별도 제품·안전 카드를 만들어야 하며 이 순서에 자동 삽입되지 않는다.

## 16. 미해결 공식 질문, 확인 방법, 안전 폴백

| ID | 미해결 질문 | 확인 방법 | 확인 전 안전 폴백 |
|---|---|---|---|
| U-01 | App Key 하나와 등록 계좌의 정확한 1:1 또는 1:N 결합 규칙은 무엇인가 | 공식 이용안내 개정 확인 + 본인 계좌별 PAPER/MOCK와 LIVE/REAL read-only token으로 노출 계좌 HMAC fingerprint 비교 | 계좌×`exec_env` 별도 credential로 취급; 계약 확인 전 binding 전면 거부, 확인 뒤 일치 후보가 정확히 1건일 때만 결합 |
| U-02 | 전체 계좌 정체성을 안정적으로 확인·정규화할 공식 read-only 응답과 페이지네이션 계약은 무엇인가 | 공식 API 가이드·고정 revision의 계좌 예제 검토 + 마스킹 카세트에서 모든 페이지의 HMAC 후보 비교 | 반환 순서·짧은 prefix 사용 금지; fingerprint를 만들 수 없으면 계좌 비활성 |
| U-03 | 일반위탁 미국 ETF의 MOCK HTTP 조회·주문/정정/취소·체결·환율·잔고 대사 행동, MOCK WebSocket 범위와 REAL parity는 무엇인가 | 공식 미국 API 문서별 fixture를 PAPER/MOCK에서 실행하고 WebSocket을 별도 검증한 뒤 사람이 승인한 최소 LIVE/REAL 절차 | 미국 AUTO `DENY`; catalog/request 존재·국내 KRX 성공·일부 MOCK 성공을 대리 증거로 사용하지 않음 |
| U-04 | 중개형 ISA에서 승인 국내 ETF의 잔고·주문·체결과 부적격 상품 거부 행동은 무엇인가 | 공식 계좌/주문 문서 + 실제 대상 계좌 read-only + 승인 ETF와 안전한 거부 케이스의 통제 검증 | ISA 주문 전부 `DENY`; 등록 가능 사실만 readiness에 표시 |
| U-05 | 연금저축의 정확한 계좌 등록, read-only 응답, ETF 적격성, 주문·체결 계약은 무엇인가 | 공식 답변 revision + 실제 대상 계좌 read-only + §10.3 사람 LIVE/REAL 절차 | 연금 live 강제 false; 완전 상품 allowlist를 추론하지 않음 |
| U-06 | 공식 주문 API가 client-supplied idempotency 식별자를 지원하는가 | 공식 주문 문서와 실제 요청/응답 계약에서 명시 필드 확인 | 존재를 가정하지 않음; persist-before-submit, no blind retry, REST 조회 |
| U-07 | 주문/체결 이력의 조회 기간·페이지네이션·정정 체인·부분체결 식별자는 무엇인가 | 공식 조회 문서 + 부분체결/정정/취소 카세트 | EOD 대사를 증명할 수 없는 시장·계좌는 live `DENY` |
| U-08 | 24시간 토큰의 동시 발급·폐기·재발급 제한과 기존 WebSocket 영향은 무엇인가 | 공식 OAuth 문서 revision + 단일 계좌 순차 실험 | 계좌별 single-flight 직렬 갱신; 불확실 시 REST/WS 중단 후 재binding |
| U-09 | 유량 오류의 정확한 HTTP/응답 코드, 정정·취소 계수, 미국 피크 전환 경계는 무엇인가 | 공식 오류·유량 문서와 rate-limited fixture | 공식 상한보다 낮은 보수 프로파일; 제출성 자동 재시도 없음 |
| U-10 | 시장별 WebSocket 제공 범위와 이벤트의 중복·순서·재연결 뒤 누락 범위, 계좌 binding은 무엇인가 | 국내/미국 공식 실시간 문서를 분리 확인 + 환경별 disconnect/reconnect/duplicate/ordering 장애주입 카세트 | WS는 알림 전용; 시장별 계약이 없으면 그 WS를 사용하지 않고 REST 대사, 최신성 부족 시 주문 거부 |
| U-11 | ETF와 ETN, KRX와 NXT/SOR를 계좌·응답에서 안정적으로 구분하는 공식 분류값은 무엇인가 | 공식 종목/마스터 문서와 애플리케이션 유니버스의 교차검증 | 분류 불명 종목 주문 거부; ETN/NXT/SOR는 확인돼도 제품 정책상 금지 |
| U-12 | PAPER/MOCK가 일반위탁 외 세제계좌 의미론을 어느 정도 재현하는가 | 공식 모의 가이드의 계좌별 명시 답변 확인 | 재현한다고 가정하지 않음; PAPER/MOCK는 세제계좌 지원 증거가 아님 |
| U-13 | IRP 지원 상태가 향후 바뀌었는가 | F-06/F-07의 공식 답변보다 최신 공식 계좌 등록·API 문서 revision 확인 | 현재 `DENY`; 변화가 있어도 별도 카드 전에는 관리 계좌로 승격하지 않음 |

## 17. 최종 불변식

1. 증권 런타임은 키움 REST/WebSocket 하나이고 암호화폐는 업비트다.
2. 역사적 한국투자증권 KIS 제공자와의 dual runtime은 없다.
3. 계좌·시장·상품·연산·환경 중 하나라도 미확인이면 주문은 없다.
4. 국내 증권 자동주문은 KRX 정규시장으로 한정되고 NXT/SOR는 별도 카드 전까지 없다.
5. API가 주식·ETN을 노출해도 승인 ETF 유니버스는 넓어지지 않는다.
6. 중개형 ISA만 관리하고, 상품 적격성 미확인은 거부한다.
7. 연금저축 live 주문은 전용 증거·사람 절차가 완료될 때까지 항상 꺼져 있다.
8. IRP는 외부 누적 납입액이며 계좌·보유·성과·주문이 아니다.
9. IRP 누락·stale·head/chain 무결성 오류는 `UNKNOWN`이지 0이 아니다.
10. 세법 한도·세율은 effective-date 설정이고 이 설계에 고정하지 않는다.
11. 계좌 응답 계약을 검증한 뒤 `matching_candidates`가 정확히 1건일 때만 결합한다. 비일치 반환 레코드의 개수는 선택 근거가 아니다.
12. 브로커 유량은 천장이며 목표 처리량이 아니다.
13. WebSocket은 알림이고 REST 대사가 장부 정본이다.
14. 응답 유실 뒤 주문을 맹목 재전송하지 않는다.
15. 활성 공개 식별자는 vendor-neutral sleeve를 사용하고 실거래 전 역사적 벤더 결합 값을 제거한다.
16. 공식 지원 변화는 스스로 AUTO를 켜지 못한다. 근거 revision, 별도 카드, 검증, 사람 승인이 필요하다.
17. `ExecEnv`는 DRY_RUN→local/no credential, PAPER→MOCK, LIVE→REAL로만 대응하며 environment bundle 일부를 섞지 않는다.
18. 계좌 fingerprint는 secret-provider-only key를 쓰는 versioned domain-separated HMAC-SHA-256이고 비키 해시나 짧은 prefix가 아니다.
19. IRP는 과세연도별 단일 append-only chain과 unique head를 가진다.
20. 세금 결과의 재현은 결과와 완전한 versioned provenance bundle을 원자 저장한 경우에만 주장한다. contribution revision 하나만으로는 충분하지 않다.
