# Phase 2: Web Research Agent & Source Collection

**기간:** 2~3주차  
**담당:** 팀원 B  
**목표:** 부족 자재의 스펙을 기반으로 웹 검색 후보를 수집하고, 가격/납기/출처 URL/스펙 증거를 정규화한다.

## 핵심 역할

Phase 2는 구매 담당자가 하던 웹 검색 업무를 자동화하는 구간이다. 실제 웹 검색이 불안정할 수 있으므로, 데모에서는 mock 후보 캐시를 항상 사용할 수 있게 유지하고 실제 검색 로직은 확장 가능한 형태로 만든다.

- 포맷 기준 문서: [Phase 2 Format Contract](PHASE_2_FORMAT_CONTRACT.md)
- Phase 1 입력 계약: `.planning/phase-1/PHASE_1_FORMAT_CONTRACT.md`
- Phase 3 출력 계약: [Phase 2 to Phase 3 Contract](PHASE_2_TO_PHASE_3_CONTRACT.md)
- MVP 제한사항: [Phase 2 Known Limits](PHASE_2_KNOWN_LIMITS.md)

## 작업 범위

- Phase 1의 shortage_event.json 입력 받기
- 자재 스펙과 검색 키워드 파싱
- 검색 쿼리 템플릿 생성
- 제조사, 공식 판매처, 산업재몰, 마켓플레이스 후보 수집
- 후보별 가격, 납기, 재고 표기 여부, 출처 URL 추출
- 스펙 증거 문장 또는 표 요약 저장
- 후보가 없을 경우 검색어 변형 후 재시도
- 결과를 candidate_results.json 형태로 정규화
- Phase 3 전달용 표준 포맷 준수 (`price_krw`, `spec_text`, snake_case `source_type` 포함)

## MVP 우선 구현 기능

- Mock 후보 캐시 사용
- Phase 1 샘플 입력 파싱
- 후보 정규화 (필수 필드 검증)
- Phase 3 계약 준수 검증

## 입력/출력 파일

| 구분 | 파일 |
| --- | --- |
| Phase 1 입력 (실제) | output/shortage_event.json |
| Phase 1 입력 (Mock) | .planning/phase-2/shortage_event.sample.json |
| Mock 후보 캐시 | .planning/phase-2/mock_candidates.csv |
| Phase 2 출력 | output/candidate_results.json |
| Phase 2 출력 (샘플) | .planning/phase-2/candidate_results.sample.json |

## 검색 쿼리 예시

```text
Ball Bearing 6204-ZZ 20mm 47mm 14mm steel replacement
6204-ZZ bearing alternative 6204-2RS distributor lead time
6204-ZZ official datasheet price stock
```

## 출력 포맷

```json
{
  "search_id": "SR-20260502-001",
  "material_id": "MAT-1001",
  "material_name": "Ball Bearing 6204-ZZ",
  "target_spec_text": "Deep groove ball bearing 6204-ZZ. Shielded metal on both sides. Inner diameter 20mm outer diameter 47mm width 14mm. Steel material.",
  "searched_at": "2026-05-02T15:30:00+09:00",
  "query_used": "Ball Bearing 6204-ZZ 20mm 47mm 14mm steel replacement",
  "candidates": [
    {
      "candidate_id": "WEB-001",
      "candidate_material_id": "MAT-1002",
      "vendor_name": "Seoul Bearings Co.",
      "price_krw": 15000,
      "min_price_krw": 15000,
      "lead_time_days": 1,
      "moq": null,
      "location": "Domestic",
      "source_type": "official_distributor",
      "source_url": "https://example.com/seoul-bearings/6204-2rs",
      "price_listed": true,
      "stock_listed": true,
      "leadtime_listed": true,
      "spec_text": "6204-2RS bearing. Inner diameter 20mm outer diameter 47mm width 14mm. Steel material.",
      "spec_evidence": "Manufacturer datasheet includes ID 20mm OD 47mm width 14mm steel 6204 series."
    }
  ]
}
```

상세 필드 정의는 [Phase 2 Format Contract](PHASE_2_FORMAT_CONTRACT.md)를 따른다.

## Phase 3 연동 기준

Phase 3는 후보 검색을 직접 수행하지 않고 Phase 2가 넘긴 후보를 평가한다. 따라서 Phase 2 출력은 아래 필드를 반드시 포함한다.

Phase 2 출력의 root `material_id`는 Phase 1에서 감지된 부족 원본 자재 ID를 유지한다. 후보 대체품의 내부 자재 ID가 있는 경우에는 후보 객체 안의 `candidate_material_id`에 저장한다. 이 규칙을 지켜야 Phase 3가 원본 자재와 후보 자재를 혼동하지 않는다.

| Field | Type | Required | Phase 3 사용 목적 |
| --- | --- | ---: | --- |
| candidate_id | string | Yes | 후보 식별 |
| candidate_material_id | string or null | Yes | 후보 자재 코드가 있을 때 식별 |
| vendor_name | string | Yes | 평가 리포트 표시 |
| source_url | string or null | Yes | 출처 신뢰도 평가 |
| source_type | enum | Yes | 출처 신뢰도 평가 |
| price_krw | integer or null | Yes | 가격 점수 계산 |
| min_price_krw | integer or null | Yes | 후보 간 가격 점수 계산 |
| lead_time_days | integer or null | Yes | 납기 점수 계산 |
| moq | integer or null | Yes | MOQ 점수 계산 |
| spec_text | string | Yes | 후보 규격 파싱 |
| spec_evidence | string | Yes | 데이터시트/상세 규격 근거 |
| price_listed | boolean | Yes | 출처 신뢰도 평가 |
| stock_listed | boolean | Yes | 출처 신뢰도 평가 |
| leadtime_listed | boolean | Yes | 출처 신뢰도 평가 |

`source_type`은 Phase 3 계약에 맞춰 아래 snake_case enum 중 하나로 저장한다.

- manufacturer_page
- official_distributor
- industrial_marketplace
- marketplace
- unknown

기존 CSV 호환이 필요한 경우에는 아래처럼 매핑한다.

| Phase 2 JSON | 기존 CSV 컬럼 |
| --- | --- |
| price_krw | UNIT_PRICE_KRW |
| spec_evidence | SPEC_EVIDENCE |
| price_listed | PRICE_LISTED |
| stock_listed | STOCK_LISTED |
| leadtime_listed | LEADTIME_LISTED |
| source_type | SOURCE_TYPE |

## 실행 방법

Phase 2는 Phase 1 없이도 독립 실행이 가능하다.

Mock 입력 사용 (Phase 1 없이 독립 실행):

```bash
python3 agents/web_research_agent.py --mock-input --output output/candidate_results.json
```

Phase 1 출력 연동:

```bash
python3 agents/web_research_agent.py --input output/shortage_event.json --output output/candidate_results.json
```

결과 확인:

```bash
cat output/candidate_results.json | jq .
```

콘솔 출력과 함께 보기:

```bash
python3 agents/web_research_agent.py --mock-input --output output/candidate_results.json --print
```

## 현재 Mock 데모 결과

현재 mock 데이터에서는 원본 부족 자재 `MAT-1001`에 대해 후보 자재 `MAT-1002` 계열의 4개 후보를 반환한다.

| Candidate ID | Vendor | Source Type | Price Listed | Lead Time |
| --- | --- | --- | --- | --- |
| WEB-001 | Seoul Bearings Co. | official_distributor | Yes | 1일 |
| WEB-002 | Global Parts Inc. | marketplace | Yes | 14일 |
| WEB-003 | Korea Industrial | official_distributor | Yes | 3일 |
| WEB-004 | Quick Supply | marketplace | No | 5일 |

## 완료 기준

- 최소 2개 이상의 후보를 같은 포맷으로 반환한다.
- 각 후보에 source_url과 source_type이 포함된다. URL이 없으면 `source_url: null`로 저장하되, Phase 3에는 낮은 출처 신뢰도 후보로 전달한다.
- 가격, 납기, 재고 정보의 존재 여부가 boolean으로 표시된다.
- 실제 검색 실패 시에도 mock 데이터로 데모가 가능하다.
- Phase 3가 바로 평가할 수 있도록 `price_krw`, `lead_time_days`, `source_type`, `source_url`, `spec_text` 필드가 고정된다.
- root `material_id`는 Phase 1 부족 자재 ID이며, 후보 자재 ID는 `candidate_material_id`로 분리된다.
- `source_type` 값은 Phase 3가 사용하는 snake_case enum을 따른다.
- Phase 1 입력 샘플만으로 독립 실행이 가능하다.

## 테스트 체크리스트

### 단위 테스트

- Phase 1 샘플 입력을 읽고 파싱할 수 있는가?
- 검색어 생성 로직이 search_keywords를 활용하는가?
- Mock 후보가 최소 2개 이상 반환되는가?
- 각 후보에 필수 필드(candidate_id, vendor_name, source_url)가 모두 채워지는가?
- URL이 없는 후보는 source_url: null로 표시되는가?
- 가격/납기/재고 중 누락된 정보가 boolean으로 명확히 드러나는가?
- 후보별 spec_text와 spec_evidence가 모두 포함되는가?
- 후보 간 min_price_krw가 계산되는가?

### 계약 준수 테스트

- Phase 2 출력이 Phase 2 Format Contract를 준수하는가?
- Phase 3가 요구하는 필드명(price_krw, spec_text, moq, source_type)을 포함하는가?
- source_type이 snake_case enum으로 정규화되는가?

### 통합 테스트 (Phase 3와 연동)

- Phase 2 출력을 Phase 3가 오류 없이 읽을 수 있는가?
- Phase 3가 candidate_id 기준으로 후보를 식별할 수 있는가?

## 테스트 실행

```bash
python3 -m unittest tests/test_phase2_research.py
python3 -m unittest tests/test_phase2_contract.py
```

## 샘플 파일

- Mock 입력 샘플
- Mock 출력 샘플

## 다음 Phase로 넘길 것

- output/candidate_results.json
- 후보별 candidate_id
- 후보별 스펙 증거
- 후보별 가격/납기/재고 정보
- 후보별 출처 URL과 출처 유형
- Phase 3 평가용 spec_text, price_krw, min_price_krw, moq
