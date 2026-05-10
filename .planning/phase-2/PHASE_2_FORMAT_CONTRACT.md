# Phase 2 Format Contract

**Owner:** Team Member B  
**Status:** MVP live-search contract  
**Purpose:** Phase 2가 Phase 1 부족 이벤트를 받아 웹 리서치 후보를 수집/정규화하고, Phase 3가 바로 평가할 수 있는 고정 JSON 포맷을 제공한다.

## Boundary

- Phase 2는 검색 쿼리 생성, live search provider 호출, 검색 결과 정규화, 출처 URL 보존, 가격/납기/MOQ/스펙 근거 추출 준비를 담당한다.
- `--extraction-mode llm`을 사용할 경우 Phase 2는 verified URL의 페이지 텍스트를 가져와 가격/납기/MOQ/재고 표시 여부/스펙 근거를 추출한다.
- 외화 가격이 명시된 경우 Phase 2 내부에서 최신 환율 API로 KRW 환산을 시도하고, 성공하면 `price_krw`에 KRW 정수값을 저장한다.
- Phase 2는 최종 추천 점수, 승인 조건, 거절 사유를 계산하지 않는다.
- Phase 2는 Phase 3의 `evaluation_report` 객체를 만들지 않는다.
- Phase 2는 Phase 4 workflow state나 PO draft를 만들지 않는다.
- LLM은 검색 쿼리 생성과 추출 보조에 사용할 수 있지만, 확인되지 않은 URL/가격/납기/재고를 추측해서 확정값으로 넣으면 안 된다.

## Input

**File:** `output/shortage_event.json`  
**Sample file:** `.planning/phase-2/shortage_event.sample.json`

입력은 `.planning/phase-1/PHASE_1_FORMAT_CONTRACT.md`를 따른다.

Phase 2가 사용하는 필수 필드:

| Field | Type | Required | Usage |
| --- | --- | ---: | --- |
| `event_id` | string | Yes | 부족 이벤트와 검색 결과 연결 |
| `material_id` | string | Yes | 원본 부족 자재 ID |
| `material_name` | string | Yes | 검색어 생성 및 표시 |
| `category` | string | Yes | 검색 쿼리/후보 해석 보조 |
| `technical_specification` | string | Yes | 원본 스펙 텍스트 |
| `search_keywords` | array[string] | Yes | 검색 쿼리 생성 |
| `detected_at` | string | Yes | 감사 추적용 timestamp |

## Output

**File:** `output/candidate_results.json`  
**Legacy samples:** `.planning/phase-2/candidate_results.sample.json`, `.planning/phase-2/candidate_results.fastener.sample.json`

샘플 JSON은 Phase 3 연동과 회귀 테스트를 위해 유지한다. 실제 실행 경로는 `live` 또는 `mixed` search mode를 사용한다.

```json
{
  "search_id": "SR-20260502-001",
  "event_id": "SE-20260502-0001",
  "material_id": "MAT-1001",
  "material_name": "Ball Bearing 6204-ZZ",
  "category": "Bearing",
  "target_spec_text": "Deep groove ball bearing 6204-ZZ...",
  "searched_at": "2026-05-02T15:30:00+09:00",
  "query_used": "Ball Bearing 6204-ZZ 20mm 47mm 14mm steel replacement",
  "search_mode": "live",
  "candidates": []
}
```

## Root Fields

| Field | Type | Required | Description |
| --- | --- | ---: | --- |
| `search_id` | string | Yes | Phase 2 검색 결과 ID |
| `event_id` | string | Yes | Phase 1 부족 이벤트 ID |
| `material_id` | string | Yes | Phase 1의 원본 부족 자재 ID |
| `material_name` | string | Yes | 원본 부족 자재명 |
| `category` | string | Yes | 자재 카테고리 |
| `target_spec_text` | string | Yes | 원본 자재 스펙 텍스트 |
| `searched_at` | string | Yes | ISO 8601 timestamp |
| `query_used` | string | Yes | 대표 검색 쿼리 |
| `search_mode` | enum | Yes | `live`, `mixed`, 또는 legacy sample용 `mock` |
| `candidates` | array | Yes | 정규화된 후보 목록 |

## Candidate Fields

| Field | Type | Required | Description |
| --- | --- | ---: | --- |
| `candidate_id` | string | Yes | 후보 고유 ID |
| `candidate_material_id` | string or null | Yes | 내부 후보 자재 ID가 있을 경우 사용 |
| `vendor_name` | string | Yes | 공급사/판매처 이름 |
| `price_krw` | integer or null | Yes | 명시된 KRW 단가 |
| `min_price_krw` | integer or null | Yes | 비교 가능한 후보 중 최저가 |
| `lead_time_days` | integer or null | Yes | 예상 납기 일수 |
| `moq` | integer or null | Yes | 최소 주문 수량 |
| `location` | enum | Yes | `Domestic`, `Overseas`, `Unknown` |
| `source_type` | enum | Yes | Phase 3 snake_case source type |
| `source_url` | string or null | Yes | 실제 확인된 출처 URL |
| `price_listed` | boolean | Yes | 가격 표시 여부 |
| `stock_listed` | boolean | Yes | 재고 표시 여부 |
| `leadtime_listed` | boolean | Yes | 납기 표시 여부 |
| `spec_text` | string | Yes | 후보 스펙 텍스트 |
| `spec_evidence` | string | Yes | 스펙 근거 문장 또는 표 요약 |

## Enums

### Search Mode

| Value | Meaning |
| --- | --- |
| `live` | live search provider 결과 사용 |
| `mixed` | live search와 보조 검색 전략 병행 |
| `mock` | legacy sample JSON 검증용 값 |

### Source Type

| Value | Meaning |
| --- | --- |
| `manufacturer_page` | 제조사 공식 제품/카탈로그 페이지 |
| `official_distributor` | 공식 대리점 또는 인증 판매처 |
| `industrial_marketplace` | 산업재 전문 마켓플레이스 |
| `marketplace` | 일반 마켓플레이스 |
| `unknown` | 출처 유형 불명 |

## Validation Rules

- root `material_id`는 Phase 1 shortage event의 `material_id`와 같아야 한다.
- 후보 자재 ID가 있으면 root `material_id`가 아니라 `candidate_material_id`에 넣는다.
- `source_type`은 Phase 3가 사용하는 snake_case enum이어야 한다.
- 알 수 없는 숫자 값은 빈 문자열이나 0 placeholder가 아니라 `null`이어야 한다.
- URL을 확인하지 못한 값은 `source_url: null`로 둔다.
- `price_listed`, `stock_listed`, `leadtime_listed`는 항상 JSON boolean이어야 한다.
- 가격이 확인된 후보가 있으면 `min_price_krw`는 non-null `price_krw` 중 최저가여야 한다.
- 각 후보는 `spec_text`와 `spec_evidence`를 포함해야 한다.
- 실제 URL이 검증되지 않은 LLM search plan은 Phase 3 후보로 승격하지 않는다.
- LLM extraction이 실패하거나 페이지에 값이 명시되지 않은 경우 해당 값은 추측하지 않고 `null` 또는 `false`로 둔다.
- 외화 가격을 KRW로 환산한 경우 `spec_evidence`에 원문 가격과 환율 변환 사실을 남긴다.
