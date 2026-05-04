# Phase 3 Task Board

**Owner:** Team Member C  
**Purpose:** Phase 3 구현 작업을 작은 단위로 쪼개어 진행 상황과 우선순위를 추적한다.

## Working Rule

- Phase 3는 후보 검색을 직접 수행하지 않는다.
- Phase 3는 Phase 2가 넘긴 후보 또는 mock 후보 데이터를 평가한다.
- Phase 3의 공식 handoff 산출물은 `output/evaluation_report_batch.json`이다.
- Phase 4와 공유하는 필드는 공용 계약 문서 `../shared/contracts/phase3_to_phase4_contract.md`를 따른다.

## MVP Task Board

| Status | Priority | Task | Output |
|---|---:|---|---|
| Done | P0 | Phase 3 기본 평가 엔진 구현 | `agents/evaluation_agent.py` |
| Done | P0 | 단일 후보 평가 리포트 생성 | `output/evaluation_report.json` |
| Done | P0 | Batch 평가 리포트 생성 | `output/evaluation_report_batch.json` |
| Done | P0 | Phase 3 -> Phase 4 공용 계약 정의 | `.planning/shared/contracts/phase3_to_phase4_contract.md` |
| Done | P0 | 공용 계약 검증 테스트 추가 | `tests/test_phase3_contract.py` |
| Todo | P0 | Fastener spec parser 고도화 | `tools/spec_normalizer.py` |
| Todo | P0 | 후보 mock 데이터 3~5개로 확장 | `vendor_sourcing.csv`, `material_master.csv` |
| Todo | P0 | Recommend / Conditional / Review / Reject 시나리오 테스트 확장 | `tests/test_phase3_evaluation.py` |
| Todo | P1 | 리포트 메시지 한국어화 | `agents/evaluation_agent.py` |
| Todo | P1 | 출처 신뢰도 계산 근거 설명 강화 | `decision_context`, `source_trust_breakdown` |
| Todo | P1 | 재질 matrix 보강 후보 정리 | `PHASE_3_MATERIAL_DECISION_MATRIX.md` |
| Todo | P2 | CLI 실행 결과를 발표용 로그 형태로 정리 | `output/` sample artifacts |

## Recommended Implementation Order

1. Parser coverage 확장
2. Mock 후보 데이터 확장
3. 판정 시나리오별 테스트 추가
4. 리포트 문구 한국어화
5. 계약 테스트 재실행
6. Phase 4 담당자에게 `next_action` 기준 설명

## Definition of Done

- `python3 -m unittest tests/test_phase3_evaluation.py tests/test_phase3_contract.py` 통과
- Batch 리포트에 최소 3개 후보가 포함됨
- 최소 3개 이상의 판정 상태가 demo에서 확인됨
- Phase 4가 `next_action`만 보고 다음 상태를 라우팅할 수 있음
- Phase 3는 PO 생성 또는 Phase 5 UI 직접 호출을 하지 않음
