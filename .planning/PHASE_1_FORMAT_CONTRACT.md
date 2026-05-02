# Phase 1 Format Contract

**Owner:** Team Member A  
**Status:** Fixed for 2-week sprint  
**Purpose:** Phase 1이 제공하는 데이터와 이벤트 포맷을 고정하여 Phase 2~5가 mock 입력으로 병렬 개발할 수 있게 한다.

## Contract Rules

- 필드명은 `snake_case`를 사용한다.
- CSV 원본 컬럼은 기존 파일 호환을 위해 `UPPER_SNAKE_CASE`를 유지한다.
- Phase 간 전달 JSON은 `snake_case`로 변환한다.
- 금액은 `KRW` 기준 정수로 저장한다.
- 수량, 점수, 리드타임은 숫자 타입으로 저장한다.
- 알 수 없는 값은 빈 문자열보다 `null`을 사용한다.
- enum 값은 이 문서에 정의된 문자열만 사용한다.

## Input 1: Inventory Snapshot CSV

**File:** `inventory_data.csv`

| Column | Type | Required | Example | Description |
|---|---|---:|---|---|
| `MATERIAL_ID` | string | Yes | `MAT-1001` | 내부 자재 코드 |
| `MATERIAL_NAME` | string | Yes | `Ball Bearing 6204-ZZ` | 사용자 표시용 자재명 |
| `CURRENT_STOCK` | integer | Yes | `10` | 현재 재고 |
| `SAFETY_STOCK` | integer | Yes | `50` | 안전 재고 |
| `PLANT` | string | Yes | `P100` | 플랜트/창고 코드 |

## Input 2: Material Master CSV

**File:** `material_master.csv`

| Column | Type | Required | Example | Description |
|---|---|---:|---|---|
| `MATERIAL_ID` | string | Yes | `MAT-1001` | 내부 자재 코드 |
| `CATEGORY` | string | Yes | `Bearing` | 자재 카테고리 |
| `TECHNICAL_SPECIFICATION` | string | Yes | `Deep groove ball bearing...` | 검색/평가에 사용할 원본 스펙 텍스트 |

## Input 3: Web Candidate Cache CSV

**File:** `vendor_sourcing.csv`

| Column | Type | Required | Example | Description |
|---|---|---:|---|---|
| `MATERIAL_ID` | string | Yes | `MAT-1002` | 후보 자재 코드 |
| `CANDIDATE_ID` | string | Yes | `WEB-001` | 웹 검색 후보 고유 ID |
| `VENDOR_NAME` | string | Yes | `Seoul Bearings Co.` | 공급업체명 |
| `UNIT_PRICE_KRW` | integer | Yes | `15000` | 단가 |
| `LEAD_TIME_DAYS` | integer | Yes | `1` | 예상 납기일 |
| `LOCATION` | enum | Yes | `Domestic` | `Domestic`, `Overseas`, `Unknown` |
| `SOURCE_TYPE` | enum | Yes | `Official distributor` | 아래 Source Type enum 참조 |
| `SOURCE_URL` | string | Yes | `https://example.com/...` | 원문 출처 URL |
| `PRICE_LISTED` | boolean | Yes | `TRUE` | 가격 명시 여부 |
| `STOCK_LISTED` | boolean | Yes | `TRUE` | 재고 명시 여부 |
| `LEADTIME_LISTED` | boolean | Yes | `TRUE` | 납기 명시 여부 |
| `SPEC_EVIDENCE` | string | Yes | `Datasheet includes...` | 스펙 근거 문장 |
| `TECH_COMPATIBILITY_PERCENT` | integer | Yes | `94` | 기술 호환성 점수 |
| `SOURCE_RELIABILITY_SCORE` | integer | Yes | `91` | 출처 신뢰도 점수 |
| `FINAL_SCORE` | integer | Yes | `92` | 최종 추천 점수 |
| `VALIDATION_STATUS` | enum | Yes | `Conditional approval` | 아래 Validation Status enum 참조 |
| `RISK_NOTE` | string | Yes | `Needs field confirmation...` | 사용자 검토용 리스크 메모 |

## Event: Shortage Event

Phase 1의 핵심 출력이다. Phase 2~5는 실제 Monitor Agent 없이도 이 JSON을 mock 입력으로 사용한다.

```json
{
  "event_id": "SE-20260502-0001",
  "status": "SHORTAGE_DETECTED",
  "material_id": "MAT-1001",
  "material_name": "Ball Bearing 6204-ZZ",
  "category": "Bearing",
  "plant": "P100",
  "current_stock": 10,
  "safety_stock": 50,
  "shortage_qty": 40,
  "technical_specification": "Deep groove ball bearing 6204-ZZ. Shielded metal on both sides. Inner diameter 20mm outer diameter 47mm width 14mm. Steel material. Max RPM 10000. Operating temp -20C to 120C.",
  "search_keywords": [
    "Ball Bearing 6204-ZZ",
    "20mm 47mm 14mm",
    "steel",
    "replacement"
  ],
  "detected_at": "2026-05-02T15:00:00+09:00"
}
```

## Shortage Event Fields

| Field | Type | Required | Example | Description |
|---|---|---:|---|---|
| `event_id` | string | Yes | `SE-20260502-0001` | 이벤트 고유 ID |
| `status` | enum | Yes | `SHORTAGE_DETECTED` | Phase 1 이벤트 상태 |
| `material_id` | string | Yes | `MAT-1001` | 부족 자재 코드 |
| `material_name` | string | Yes | `Ball Bearing 6204-ZZ` | 부족 자재명 |
| `category` | string | Yes | `Bearing` | 자재 카테고리 |
| `plant` | string | Yes | `P100` | 플랜트/창고 코드 |
| `current_stock` | integer | Yes | `10` | 현재 재고 |
| `safety_stock` | integer | Yes | `50` | 안전 재고 |
| `shortage_qty` | integer | Yes | `40` | 부족 수량 |
| `technical_specification` | string | Yes | `Deep groove...` | 원본 스펙 전문 |
| `search_keywords` | array[string] | Yes | `["6204-ZZ"]` | Phase 2 검색 쿼리 생성용 키워드 |
| `detected_at` | string | Yes | `2026-05-02T15:00:00+09:00` | ISO 8601 감지 시각 |

## Enums

### Shortage Status

| Value | Meaning |
|---|---|
| `SHORTAGE_DETECTED` | 현재고가 안전재고보다 낮아 조달 프로세스를 시작해야 함 |
| `NO_SHORTAGE` | 부족 자재 없음 |

### Source Type

| Value | Meaning |
|---|---|
| `Manufacturer page` | 제조사 공식 페이지 |
| `Official distributor` | 공식 대리점/공식 판매처 |
| `Industrial marketplace` | 산업재 전문몰 |
| `Marketplace` | 일반 마켓플레이스 |
| `Unknown` | 출처 유형 불명확 |

### Validation Status

| Value | Meaning |
|---|---|
| `Recommended` | 자동 추천 가능 |
| `Conditional approval` | 조건부 추천, 사용자 확인 필요 |
| `Review required` | 검토 필요 |
| `Not recommended` | 추천 제외 |

## Validation Rules

- `shortage_qty = safety_stock - current_stock`
- `current_stock < safety_stock`일 때만 `SHORTAGE_DETECTED`를 생성한다.
- `material_id`는 `inventory_data.csv`와 `material_master.csv`에 모두 존재해야 한다.
- `search_keywords`는 최소 3개 이상 포함한다.
- `detected_at`은 ISO 8601 형식으로 기록한다.
- `TECH_COMPATIBILITY_PERCENT`, `SOURCE_RELIABILITY_SCORE`, `FINAL_SCORE`는 0~100 정수만 허용한다.
- `UNIT_PRICE_KRW`, `LEAD_TIME_DAYS`는 0 이상의 정수만 허용한다.

## Phase 2 Mock Input

Phase 2 담당자는 실제 Monitor Agent가 없어도 `.planning/shortage_event.sample.json` 하나로 검색 로직을 시작할 수 있어야 한다.

```json
{
  "event_id": "SE-20260502-0001",
  "status": "SHORTAGE_DETECTED",
  "material_id": "MAT-1001",
  "material_name": "Ball Bearing 6204-ZZ",
  "category": "Bearing",
  "plant": "P100",
  "current_stock": 10,
  "safety_stock": 50,
  "shortage_qty": 40,
  "technical_specification": "Deep groove ball bearing 6204-ZZ. Shielded metal on both sides. Inner diameter 20mm outer diameter 47mm width 14mm. Steel material. Max RPM 10000. Operating temp -20C to 120C.",
  "search_keywords": ["Ball Bearing 6204-ZZ", "20mm 47mm 14mm", "steel", "replacement"],
  "detected_at": "2026-05-02T15:00:00+09:00"
}
```
