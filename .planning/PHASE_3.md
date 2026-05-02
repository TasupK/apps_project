# Phase 3: Trust & Evaluation Agent

**기간:** 3~4주차  
**담당:** 팀원 C  
**목표:** 웹 검색 후보의 기술 호환성과 출처 신뢰도를 평가하고, 사용자가 검토할 수 있는 추천 리포트를 생성한다.

## 핵심 역할

Phase 3는 AI 추천의 안전성을 책임진다. 웹 검색 결과를 그대로 믿지 않고, 필수 스펙 일치 여부와 출처 신뢰도를 함께 평가해 추천, 조건부 승인, 검토 필요, 제외 상태를 구분한다.

## 작업 범위

- 원본 자재 스펙 파싱
- 후보 자재 스펙 파싱
- 필수 스펙 Rule 비교
- 단위 변환이 필요한 항목 처리
- 기술 호환성 점수 계산
- 출처 신뢰도 점수 계산
- 가격/납기/신뢰도 기반 최종 점수 계산
- 리스크 메모 생성
- `evaluation_report` 생성

## 점수 기준 초안

| 항목 | 가중치 | 설명 |
|---|---:|---|
| 기술 호환성 | 45% | 치수, 재질, 성능, 표준규격 등 필수 조건 |
| 출처 신뢰도 | 20% | 공식 제조사/공식 판매처/스펙 증거 여부 |
| 납기 적합성 | 20% | 긴급도 대비 리드타임 |
| 가격 경쟁력 | 10% | 후보 간 가격 비교 |
| 과거 승인 이력 | 5% | PoC에서는 mock 점수로 처리 가능 |

## 출력 포맷

```json
{
  "candidate_id": "WEB-001",
  "material_id": "MAT-1002",
  "vendor_name": "Seoul Bearings Co.",
  "tech_compatibility_percent": 94,
  "source_reliability_score": 91,
  "final_score": 92,
  "validation_status": "Conditional approval",
  "risk_note": "ZZ shield to 2RS rubber seal change needs field confirmation for heat/friction conditions.",
  "recommendation_rank": 1
}
```

## 완료 기준

- 후보별 기술 호환성 점수가 계산된다.
- 후보별 출처 신뢰도 점수가 계산된다.
- 최종 추천 순위가 생성된다.
- 기준 미달 후보는 자동 추천에서 제외되거나 `Review required`로 표시된다.
- 사용자가 판단할 수 있는 리스크 메모가 포함된다.

## 테스트 체크리스트

- 필수 스펙이 불일치하면 높은 점수가 나오지 않는가?
- 공식 출처 후보가 마켓플레이스 후보보다 높은 신뢰도를 받는가?
- 가격이 낮아도 납기가 너무 길면 최종 점수가 낮아지는가?
- 리스크 메모가 원본/후보 스펙 차이를 근거로 작성되는가?

## 다음 Phase로 넘길 것

- `evaluation_report`
- 추천 후보 Top 3
- 조건부 승인 사유
- 자동 제외 후보와 제외 근거
