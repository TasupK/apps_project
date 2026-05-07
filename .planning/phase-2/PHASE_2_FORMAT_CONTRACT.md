# Phase 2 Format Contract

**Owner:** Team Member B  
**Status:** MVP contract  
**Purpose:** Phase 2가 Phase 1 부족 이벤트를 받아 웹 후보를 수집/정규화하고, Phase 3가 평가할 수 있는 고정 JSON 포맷을 제공한다.

## Boundary

- Phase 2 owns search query generation, candidate source collection, source normalization, price/lead-time/MOQ extraction, and evidence text preservation.
- Phase 2 does not calculate final recommendation scores.
- Phase 2 does not create Phase 3 `evaluation_report` objects.
- Phase 2 does not create Phase 4 workflow state or PO drafts.

## Input

**File:** `output/shortage_event.json`  
**Mock file:** `.planning/phase-2/shortage_event.sample.json`

The input follows `.planning/phase-1/PHASE_1_FORMAT_CONTRACT.md`.

Required fields used by Phase 2:

| Field | Type | Required | Usage |
| --- | --- | ---: | --- |
| `event_id` | string | Yes | link search result to shortage event |
| `material_id` | string | Yes | target/original material ID |
| `material_name` | string | Yes | query text and display |
| `category` | string | Yes | query template selection |
| `technical_specification` | string | Yes | target spec text |
| `search_keywords` | array[string] | Yes | query generation |
| `detected_at` | string | Yes | audit trail |

## Output

**File:** `output/candidate_results.json`  
**Sample:** `.planning/phase-2/candidate_results.sample.json`

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
  "search_mode": "mock",
  "candidates": []
}
```

## Root Fields

| Field | Type | Required | Description |
| --- | --- | ---: | --- |
| `search_id` | string | Yes | Phase 2 search result ID |
| `event_id` | string | Yes | Phase 1 shortage event ID |
| `material_id` | string | Yes | original shortage material ID from Phase 1 |
| `material_name` | string | Yes | original shortage material name |
| `category` | string | Yes | material category |
| `target_spec_text` | string | Yes | original target specification text |
| `searched_at` | string | Yes | ISO 8601 timestamp |
| `query_used` | string | Yes | final query that produced candidates |
| `search_mode` | enum | Yes | `mock`, `live`, or `mixed` |
| `candidates` | array | Yes | normalized candidate list |

## Candidate Fields

| Field | Type | Required | Description |
| --- | --- | ---: | --- |
| `candidate_id` | string | Yes | unique candidate ID |
| `candidate_material_id` | string or null | Yes | internal candidate material ID if known |
| `vendor_name` | string | Yes | supplier or seller name |
| `price_krw` | integer or null | Yes | listed unit price in KRW |
| `min_price_krw` | integer or null | Yes | lowest comparable price among returned candidates |
| `lead_time_days` | integer or null | Yes | expected lead time in days |
| `moq` | integer or null | Yes | minimum order quantity |
| `location` | enum | Yes | `Domestic`, `Overseas`, or `Unknown` |
| `source_type` | enum | Yes | Phase 3 snake_case source type |
| `source_url` | string or null | Yes | source URL; null when unavailable |
| `price_listed` | boolean | Yes | whether price was visible |
| `stock_listed` | boolean | Yes | whether stock was visible |
| `leadtime_listed` | boolean | Yes | whether lead time was visible |
| `spec_text` | string | Yes | candidate specification text for Phase 3 parsing |
| `spec_evidence` | string | Yes | evidence sentence or table summary |

## Enums

### Search Mode

| Value | Meaning |
| --- | --- |
| `mock` | local mock candidate cache only |
| `live` | live web search only |
| `mixed` | live search with mock fallback or merge |

### Source Type

| Value | Meaning |
| --- | --- |
| `manufacturer_page` | official manufacturer product or catalog page |
| `official_distributor` | official distributor or authorized seller |
| `industrial_marketplace` | industrial marketplace |
| `marketplace` | general marketplace |
| `unknown` | source type is unclear |

## Validation Rules

- Root `material_id` must equal the Phase 1 shortage event `material_id`.
- Candidate replacement IDs must use `candidate_material_id`, not root `material_id`.
- `source_type` must use the Phase 3 snake_case enum.
- Unknown numeric values must be `null`, not empty strings or zero placeholders.
- Unknown URLs must be `null`.
- `price_listed`, `stock_listed`, and `leadtime_listed` must always be booleans.
- `min_price_krw` should be the minimum non-null `price_krw` among returned candidates.
- Each candidate must include both `spec_text` and `spec_evidence`.
