# Phase 3: Trust & Evaluation Agent

**기간:** 3~4주차  
**담당:** 팀원 C  
**목표:** 웹 검색 후보의 기술 호환성과 출처 신뢰도를 평가하고, 사용자가 검토할 수 있는 추천 리포트를 생성한다.

## 핵심 역할

Phase 3는 AI 추천의 안전성을 책임진다. 웹 검색 결과를 그대로 믿지 않고, 필수 스펙 일치 여부와 출처 신뢰도를 함께 평가해 추천, 조건부 승인, 검토 필요, 제외 상태를 구분한다.

포맷 기준 문서: [Phase 3 Format Contract](PHASE_3_FORMAT_CONTRACT.md)
재질 판정 기준 문서: [Phase 3 Material Decision Matrix](PHASE_3_MATERIAL_DECISION_MATRIX.md)
Phase 4 전달 계약: [Phase 3 to Phase 4 Contract](../shared/contracts/phase3_to_phase4_contract.md)
작업 보드: [Phase 3 Task Board](phase3_task_board.md)
MVP 제한사항: [Phase 3 Known Limits](phase3_known_limits.md)
최종 점검: [Phase 3 Readiness Review](PHASE_3_READINESS_REVIEW.md)

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
- Phase 4 전달용 `evaluation_report_batch` 생성

## MVP 우선 구현 기능

- 규격 파싱
- 필수 스펙 검증
- 스펙 차이 하이라이트
- 위험등급 분류
- 추천/반려 사유 생성
- 출처 신뢰도 breakdown
- 긴급 모드 가중치 조절

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

## 실행 방법

Phase 3는 Phase 5 UI와 직접 연결하지 않고 JSON 산출물만 생성한다.

```bash
python3 agents/evaluation_agent.py --csv-demo --output output/evaluation_report.json
```

여러 후보를 한 번에 평가하고 랭킹/요약까지 생성하려면 batch 모드를 사용한다.

```bash
python3 agents/evaluation_agent.py --batch --output output/evaluation_report_batch.json
```

Phase 2의 live search 산출물을 직접 평가하려면 `--candidate-results`를 사용한다.

```bash
python3 agents/evaluation_agent.py --candidate-results output/candidate_results.json --output output/evaluation_report_batch.json
```

Phase 2 fastener 연동 샘플로 검증하려면 아래 명령을 사용한다.

```bash
python3 agents/evaluation_agent.py --candidate-results output/candidate_results.fastener.json --output output/evaluation_report_batch.json
```

Phase 4로 넘기는 공식 산출물은 단일 후보 리포트가 아니라 batch 리포트다. 상세 필드와 상태값은 공용 계약 문서인 [Phase 3 to Phase 4 Contract](../shared/contracts/phase3_to_phase4_contract.md)를 따른다.

샘플 리포트를 콘솔에도 같이 보고 싶으면 아래 명령을 사용한다.

```bash
python3 agents/evaluation_agent.py --csv-demo --output output/evaluation_report.json --print
```

## 입력/출력 파일

| 구분 | 파일 |
|---|---|
| 부족 이벤트 mock | `.planning/phase-3/fastener_shortage_event.sample.json` |
| 자재 마스터 | `material_master.csv` |
| 후보/공급처 mock | `vendor_sourcing.csv` |
| Phase 2 후보 결과 | `output/candidate_results.json` |
| Phase 2 fastener 후보 샘플 | `output/candidate_results.fastener.json` |
| 평가 리포트 산출물 | `output/evaluation_report.json` |
| Batch 평가 리포트 산출물 | `output/evaluation_report_batch.json` |

## 현재 CSV 데모 결과

현재 mock 데이터에서는 `MAT-3001` 원본 자재를 기준으로 4개 후보를 비교한다.

| Candidate | Expected Decision | Reason |
|---|---|---|
| `WEB-006` | `recommend` | 직경, 피치, 길이, 재질이 모두 동일 |
| `WEB-007` | `conditional_approve` | 길이는 동일하지만 `SUS304 -> SUS316` 재질 상향 |
| `WEB-008` | `review_required` | 규격은 동일하지만 marketplace 출처 근거가 약함 |
| `WEB-005` | `reject` | 길이 `50mm -> 55mm` 불일치 |

Batch 리포트의 `next_action`은 `approval_pending`이며, `top_candidate_id`는 `WEB-006`이다.

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

## 테스트 실행

```bash
python3 -m unittest tests/test_phase3_evaluation.py
python3 -m unittest tests/test_phase3_contract.py
```

## 샘플 리포트

- [Conditional Approve Sample](evaluation_report.conditional_approve.sample.json)
- [Reject Sample](evaluation_report.reject.sample.json)

## 다음 Phase로 넘길 것

- `output/evaluation_report_batch.json`
- `next_action`
- `top_candidate_id`
- 후보별 `decision_context`
- 후보별 `scores`, `highlighted_differences`
