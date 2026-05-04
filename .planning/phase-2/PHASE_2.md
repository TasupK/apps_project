# Phase 2: Web Research Agent & Source Collection

**기간:** 2~3주차  
**담당:** 팀원 B  
**목표:** 부족 자재의 스펙을 기반으로 웹 검색 후보를 수집하고, 가격/납기/출처 URL/스펙 증거를 정규화한다.

## 핵심 역할

Phase 2는 구매 담당자가 하던 웹 검색 업무를 자동화하는 구간이다. 실제 웹 검색이 불안정할 수 있으므로, 데모에서는 mock 후보 캐시를 항상 사용할 수 있게 유지하고 실제 검색 로직은 확장 가능한 형태로 만든다.

## 작업 범위

- `shortage_event`와 자재 스펙을 입력으로 받기
- 검색 쿼리 템플릿 생성
- 제조사, 공식 판매처, 산업재몰, 마켓플레이스 후보 수집
- 후보별 가격, 납기, 재고 표기 여부, 출처 URL 추출
- 스펙 증거 문장 또는 표 요약 저장
- 후보가 없을 경우 검색어 변형 후 재시도
- 결과를 `candidate_result` 형태로 정규화

## 검색 쿼리 예시

```text
Ball Bearing 6204-ZZ 20mm 47mm 14mm steel replacement
6204-ZZ bearing alternative 6204-2RS distributor lead time
6204-ZZ official datasheet price stock
```

## 출력 포맷

```json
{
  "material_id": "MAT-1002",
  "candidate_id": "WEB-001",
  "vendor_name": "Seoul Bearings Co.",
  "unit_price_krw": 15000,
  "lead_time_days": 1,
  "location": "Domestic",
  "source_type": "Official distributor",
  "source_url": "https://example.com/seoul-bearings/6204-2rs",
  "price_listed": true,
  "stock_listed": true,
  "leadtime_listed": true,
  "spec_evidence": "Manufacturer datasheet includes ID 20mm OD 47mm width 14mm steel 6204 series."
}
```

## 완료 기준

- 최소 2개 이상의 후보를 같은 포맷으로 반환한다.
- 각 후보에 `source_url`과 `source_type`이 포함된다.
- 가격, 납기, 재고 정보의 존재 여부가 boolean으로 표시된다.
- 실제 검색 실패 시에도 mock 데이터로 데모가 가능하다.
- Phase 3가 바로 평가할 수 있도록 필드명이 고정된다.

## 테스트 체크리스트

- 같은 입력 자재에 대해 후보가 정렬 가능한 형태로 반환되는가?
- URL이 없는 후보는 신뢰도 평가에서 감점될 수 있게 표시되는가?
- 가격/납기/재고 중 누락된 정보가 명확히 드러나는가?
- 검색 결과가 0개일 때 재시도 로직 또는 fallback이 동작하는가?

## 다음 Phase로 넘길 것

- `candidate_result`
- 후보별 스펙 증거
- 후보별 가격/납기/재고 정보
- 후보별 출처 URL과 출처 유형
