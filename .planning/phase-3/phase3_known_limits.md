# Phase 3 Known Limits

**Owner:** Team Member C  
**Purpose:** MVP에서 의도적으로 제외하거나 제한하는 범위를 명확히 하여 Phase 간 역할 충돌과 과도한 구현을 방지한다.

## Scope Boundary

Phase 3는 구매 후보를 평가하고 설명하는 엔진이다. 검색, 승인, 발주, UI 렌더링은 다른 Phase의 책임이다.

| Area | Phase 3 Decision |
|---|---|
| 웹 검색 | 직접 수행하지 않음. Phase 2 산출물 또는 mock 후보를 입력으로 사용 |
| 사용자 승인 | 직접 수행하지 않음. Phase 4가 담당 |
| PO 생성 | 직접 수행하지 않음. Phase 5 또는 ERP mock 단계가 담당 |
| UI 연결 | 직접 수행하지 않음. JSON 산출물만 생성 |
| 최종 구매 결정 | 자동 확정하지 않음. Human-in-the-loop 전제 |

## MVP Rule Limits

| Topic | MVP Rule | Reason |
|---|---|---|
| 길이 | `length_mm` 불일치 시 무조건 `reject` | 나사/볼트는 길이 오구매 리스크가 큼 |
| 직경 | `diameter` 불일치 시 무조건 `reject` | 체결 호환 불가 |
| 피치 | `pitch` 불일치 시 무조건 `reject` | 나사산 체결 불가 |
| 규격 체계 | Metric/UNC 불일치 시 무조건 `reject` | 규격 체계 불일치 |
| 재질 | material decision matrix 기준 | AI 주관 판단 방지 |
| 출처 신뢰도 | 출처 유형과 표시 정보 기반 rule score | 실시간 검증 전 MVP 기준 |

## Not Implemented Yet

- 실시간 판매 페이지 크롤링
- 실제 재고 수량 자동 확인
- 실제 납기 API 검증
- 실제 제조사 데이터시트 다운로드/파싱
- 회사 내부 승인 이력 기반 점수화
- ERP 또는 SAP BAPI 직접 연동
- LLM 기반 자유 판단을 최종 판정에 직접 반영

## Assumptions

- Phase 1이 부족 자재와 원본 스펙을 제공한다.
- Phase 2가 후보 자재와 출처 URL, 가격, 납기, 스펙 근거 텍스트를 제공한다.
- Phase 3는 입력값이 불완전하면 `review_required` 또는 `reject`를 낸다.
- Phase 4는 `next_action`을 기준으로 승인 흐름을 제어한다.

## Open Questions

- Phase 1에서 실제로 사용할 fastener 재질 범위는 무엇인가?
- 회사 기준에서 SUS304 -> SUS316 상향 대체를 항상 허용할 수 있는가?
- SUS316 -> SUS304 하향 대체를 어떤 조건에서 검토 가능으로 볼 것인가?
- 출처 신뢰도에서 공식 판매처와 산업재 전문몰의 점수 차이를 얼마나 둘 것인가?
- Phase 2가 후보 스펙을 어떤 컬럼명으로 넘길 것인가?

## Presentation Note

Phase 3의 MVP는 완전 자동 구매가 아니라, 구매 담당자가 빠르게 검토할 수 있는 평가 리포트 생성이다. 따라서 불확실한 정보는 무리하게 승인하지 않고 `review_required`로 넘기는 것이 정상 동작이다.
