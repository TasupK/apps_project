# Phase 1: Mock Data Layer & Monitor Agent

**기간:** 1~2주차  
**담당:** 팀원 A  
**목표:** 자재 마스터, 재고 스냅샷, 웹 후보 캐시의 기본 구조를 만들고 재고 부족 이벤트를 안정적으로 발생시킨다.

## 핵심 역할

Phase 1은 전체 시스템의 입력을 책임진다. 이후 Phase 2~5는 모두 Phase 1이 만든 자재/재고 데이터와 `shortage_event`를 기준으로 동작하므로, 필드명과 데이터 타입을 먼저 고정하는 것이 가장 중요하다.

포맷 기준 문서: [Phase 1 Format Contract](PHASE_1_FORMAT_CONTRACT.md)

## 작업 범위

- 자재 마스터 데이터 구조 정의
- 재고 스냅샷 데이터 구조 정의
- 웹 검색 후보 캐시의 최소 필드 정의
- `현재고 < 안전재고` 조건 감지 로직 구현
- 부족 수량 계산
- 다음 단계로 넘길 `shortage_event` 생성
- 검색 쿼리 생성을 위한 핵심 스펙 키워드 추출 준비

## 입력 데이터

| 파일 | 설명 | 주요 필드 |
|---|---|---|
| `inventory_data.csv` | 현재고/안전재고 스냅샷 | `MATERIAL_ID`, `MATERIAL_NAME`, `CURRENT_STOCK`, `SAFETY_STOCK`, `PLANT` |
| `material_master.csv` | 자재별 기술 스펙 | `MATERIAL_ID`, `CATEGORY`, `TECHNICAL_SPECIFICATION` |
| `vendor_sourcing.csv` | 웹 검색 후보 캐시 | `MATERIAL_ID`, `CANDIDATE_ID`, `VENDOR_NAME`, `SOURCE_URL`, `FINAL_SCORE` |

## 출력 포맷

Phase 1의 공식 출력은 `shortage_event`이며, 필드명과 타입은 `PHASE_1_FORMAT_CONTRACT.md`를 따른다.

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

## 완료 기준

- 재고 부족 자재가 1개 이상 정상 감지된다.
- 부족 수량이 정확히 계산된다.
- `shortage_event`가 Phase 2에서 바로 사용할 수 있는 형태로 생성된다.
- `PHASE_1_FORMAT_CONTRACT.md`의 필수 필드가 모두 채워진다.
- mock 데이터만으로 단독 실행이 가능하다.
- 필드명 변경 사항이 생기면 `REQUIREMENTS.md`와 팀원에게 공유된다.

## 테스트 체크리스트

- 현재고가 안전재고보다 작으면 이벤트가 발생하는가?
- 현재고가 안전재고 이상이면 이벤트가 발생하지 않는가?
- 부족 수량이 `SAFETY_STOCK - CURRENT_STOCK`으로 계산되는가?
- 존재하지 않는 자재코드가 들어왔을 때 오류 메시지가 명확한가?

## 다음 Phase로 넘길 것

- `shortage_event`
- 대상 자재의 기술 스펙 텍스트
- 검색 쿼리 생성을 위한 키워드 후보
- 데이터 필드 정의표
