# Phase 3 Format Contract

**Owner:** Team Member C  
**Status:** Fixed for MVP scope  
**Purpose:** 범용 나사/볼트 대체 평가 결과를 구조화하여 Phase 4 워크플로우와 Phase 5 UI가 같은 계약을 기준으로 병렬 개발할 수 있게 한다.

## Scope

- 대상 품목: 범용 나사, 볼트, 체결부품
- 핵심 목적: 잘못된 규격 구매를 방지하면서 대체 가능 여부를 설명 가능한 형태로 리포트화
- 평가 초점: 규격 정확도, 리드타임, 가격, MOQ, 출처 신뢰도, 리스크

재질 판정 기준 문서: [Phase 3 Material Decision Matrix](PHASE_3_MATERIAL_DECISION_MATRIX.md)

## Decision Enums

| Value | Meaning |
|---|---|
| `recommend` | 필수 스펙이 일치하고 출처 신뢰도도 충분하여 바로 추천 가능 |
| `conditional_approve` | 핵심 규격은 맞지만 길이/재질 등 일부 차이로 조건부 확인 필요 |
| `review_required` | 규격은 유사하나 근거 부족 또는 불확실성이 있어 사람 검토 필요 |
| `reject` | 필수 스펙 불일치로 대체 불가 |

## Risk Enums

| Value | Meaning |
|---|---|
| `Low` | 동일 규격 또는 실질적으로 동일 |
| `Medium` | 일부 차이가 있으나 허용 가능성 있음 |
| `High` | 성능/현장 영향 또는 불확실성이 큼 |

## Source Type Enums

| Value | Meaning |
|---|---|
| `manufacturer_page` | 제조사 공식 제품/카탈로그 페이지 |
| `official_distributor` | 공식 대리점/공식 판매처 |
| `industrial_marketplace` | 산업재 전문몰 |
| `marketplace` | 일반 마켓플레이스 |
| `unknown` | 출처 성격 불명 |

## Required Critical Specs

필수 스펙은 제품 후보를 자동 탈락시킬 수 있는 항목이다.

| Spec | Rule | Mismatch Result |
|---|---|---|
| `diameter` | 반드시 동일 | `reject` |
| `pitch` | 반드시 동일 | `reject` |
| `thread_system` | 반드시 동일 | `reject` |
| `length_mm` | 반드시 동일 | `reject` |
| `material` | `PHASE_3_MATERIAL_DECISION_MATRIX.md` 기준으로 판정 | `conditional_approve`, `review_required`, `reject` |

## Tolerance Rules

| Condition | Decision | Risk |
|---|---|---|
| 길이 동일 | `recommend` 가능 | `Low` |
| 길이 불일치 | `reject` | `High` |
| 재질 동일 | `recommend` 가능 | `Low` |
| 재질 상향 대체 | `conditional_approve` | `Medium` |
| 재질 불명확 | `review_required` | `High` |
| 재질 하향 대체 | material matrix 기준 | `Medium` or `High` |

## Weight Profiles

### Normal Mode

| Dimension | Weight |
|---|---:|
| `compatibility_score` | 50 |
| `lead_time_score` | 20 |
| `price_score` | 15 |
| `source_trust_score` | 10 |
| `moq_score` | 5 |

### Urgent Mode

| Dimension | Weight |
|---|---:|
| `compatibility_score` | 50 |
| `lead_time_score` | 30 |
| `price_score` | 5 |
| `source_trust_score` | 10 |
| `moq_score` | 5 |

## Output Schema

**File:** `evaluation_report.json`

```json
{
  "report_id": "ER-20260504-001",
  "generated_at": "2026-05-04T14:30:00+09:00",
  "mode": "urgent",
  "target_material": {},
  "candidate_material": {},
  "spec_analysis": {},
  "scores": {},
  "source_trust_breakdown": {},
  "decision_context": {}
}
```

## Output Fields

### Root Fields

| Field | Type | Required | Description |
|---|---|---:|---|
| `report_id` | string | Yes | 평가 리포트 고유 ID |
| `generated_at` | string | Yes | ISO 8601 생성 시각 |
| `mode` | enum | Yes | `normal`, `urgent` |
| `target_material` | object | Yes | 원본 자재 정보 |
| `candidate_material` | object | Yes | 후보 자재 정보 |
| `spec_analysis` | object | Yes | 규격 비교 결과 |
| `scores` | object | Yes | 정량 점수 결과 |
| `source_trust_breakdown` | object | Yes | 출처 신뢰도 세부 항목 |
| `decision_context` | object | Yes | 추천/반려/조건부 승인 설명 |

### `target_material`

| Field | Type | Required | Description |
|---|---|---:|---|
| `material_id` | string | Yes | 원본 자재 코드 |
| `description` | string | Yes | 자재명 |
| `spec` | object | Yes | 파싱된 원본 규격 |

### `candidate_material`

| Field | Type | Required | Description |
|---|---|---:|---|
| `candidate_id` | string | Yes | 후보 ID |
| `vendor_name` | string | Yes | 판매업체명 |
| `source_url` | string | Yes | 출처 페이지 URL |
| `source_type` | enum | Yes | 출처 유형 |
| `price_krw` | integer | Yes | 단가 |
| `lead_time_days` | integer | Yes | 납기일 |
| `moq` | integer or null | Yes | 최소 주문 수량 |
| `spec` | object | Yes | 파싱된 후보 규격 |

### `spec_analysis`

| Field | Type | Required | Description |
|---|---|---:|---|
| `critical_spec_check` | object | Yes | 필수 스펙 판정 결과 |
| `highlighted_differences` | array | Yes | 차이점 목록 |

### `scores`

| Field | Type | Required | Description |
|---|---|---:|---|
| `compatibility_score` | integer | Yes | 규격 호환성 점수 |
| `source_trust_score` | integer | Yes | 출처 신뢰도 점수 |
| `lead_time_score` | integer | Yes | 납기 점수 |
| `price_score` | integer | Yes | 가격 점수 |
| `moq_score` | integer | Yes | MOQ 점수 |
| `final_score` | integer | Yes | 최종 종합 점수 |

### `source_trust_breakdown`

| Field | Type | Required | Description |
|---|---|---:|---|
| `official_distributor` | boolean | Yes | 공식 판매처 여부 |
| `datasheet_available` | boolean | Yes | 데이터시트 확인 여부 |
| `stock_visible` | boolean | Yes | 재고 표시 여부 |
| `price_visible` | boolean | Yes | 가격 표시 여부 |
| `leadtime_visible` | boolean | Yes | 납기 표시 여부 |

### `decision_context`

| Field | Type | Required | Description |
|---|---|---:|---|
| `decision` | enum | Yes | 최종 판정 |
| `risk_level` | enum | Yes | 위험등급 |
| `recommendation_reason` | string | Yes | 추천 또는 검토 사유 |
| `approval_conditions` | array[string] | Yes | 조건부 승인 조건 |
| `rejection_reason` | string or null | Yes | 반려 사유 |
| `review_required` | boolean | Yes | 사용자 검토 필요 여부 |

## Handoff Rules

- Phase 4는 `decision_context.decision`을 기준으로 워크플로우 상태를 결정한다.
- Phase 4는 `decision_context.review_required`가 `true`이면 자동 승인 경로로 보내지 않는다.
- Phase 5는 `spec_analysis.highlighted_differences`, `scores`, `decision_context`를 그대로 UI에 렌더링한다.
