# Phase 3 Readiness Review

**Status:** MVP ready  
**Owner:** Team Member C  
**Purpose:** Phase 3가 구현/시연/Phase 4 handoff에 필요한 최소 요건을 충족했는지 최종 점검한다.

## Summary

Phase 3는 범용 나사/볼트 후보 자재를 평가하는 AI 평가 리포트 엔진이다. 현재 MVP는 후보 검색을 직접 수행하지 않고, Phase 2 또는 mock CSV에서 받은 후보를 대상으로 규격 호환성, 재질 룰, 출처 신뢰도, 가격, 납기, MOQ를 평가한다.

공식 산출물은 `output/evaluation_report_batch.json`이며, Phase 4는 이 파일의 `next_action`과 `top_candidate_id`를 기준으로 승인 흐름을 제어한다.

## Completed Scope

| Area | Status | Evidence |
|---|---|---|
| Fastener spec parser | Done | `tools/spec_normalizer.py` |
| Critical spec validation | Done | 직경, 피치, 규격 체계, 길이 |
| Material decision rules | Done | `PHASE_3_MATERIAL_DECISION_MATRIX.md` |
| Source trust scoring | Done | `source_trust_breakdown`, `source_trust_notes` |
| Batch report generation | Done | `output/evaluation_report_batch.json` |
| Shared contract | Done | `.planning/shared/contracts/phase3_to_phase4_contract.md` |
| Contract validation | Done | `tests/test_phase3_contract.py` |
| Demo log | Done | `output/phase3_demo_log.md` |

## Runbook

### Generate Batch Report

```bash
python3 agents/evaluation_agent.py --batch --output output/evaluation_report_batch.json
```

### Run Tests

```bash
python3 -m unittest tests/test_phase3_evaluation.py tests/test_phase3_contract.py
```

Expected result:

```text
Ran 23 tests
OK
```

## Current Demo Result

| Candidate | Decision | Risk | Reason |
|---|---|---|---|
| `WEB-006` | `recommend` | `Low` | 동일 규격, 동일 재질, 공식 대리점 |
| `WEB-007` | `conditional_approve` | `Medium` | 동일 규격, `SUS304 -> SUS316` 재질 상향 |
| `WEB-008` | `review_required` | `High` | 규격은 동일하지만 출처 신뢰도 낮음 |
| `WEB-005` | `reject` | `High` | 길이 `50mm -> 55mm` 불일치 |

## Phase 4 Handoff

Phase 4가 읽어야 하는 파일:

```text
output/evaluation_report_batch.json
```

Phase 4가 먼저 확인해야 하는 필드:

| Field | Current Value | Meaning |
|---|---|---|
| `next_action` | `approval_pending` | 사용자 승인 요청 가능 |
| `top_candidate_id` | `WEB-006` | 승인 요청 1순위 후보 |
| `candidate_count` | `4` | 평가 후보 수 |

Phase 4는 Phase 3의 점수를 다시 계산하지 않는다. 승인 메시지에는 각 item의 `decision_context`, `scores`, `source_trust_notes`, `spec_analysis.highlighted_differences`를 그대로 사용한다.

## Known Limits

- 실제 웹 크롤링은 Phase 2 책임이다.
- 실제 PO 생성은 Phase 5 또는 ERP mock 책임이다.
- 실제 회사 재고 DB의 재질 종류가 확정되면 material matrix를 갱신해야 한다.
- 길이 불일치는 MVP에서 무조건 `reject`로 처리한다.
- 재질 하향 대체는 명시 룰이 없으면 보수적으로 `review_required` 또는 `reject`로 처리한다.

## Open Coordination Items

| Owner | Question |
|---|---|
| Phase 1 | 실제 fastener 재질 목록과 표면처리/도금 정보를 제공할 수 있는가? |
| Phase 2 | 후보 데이터 컬럼명이 현재 `vendor_sourcing.csv` 구조와 맞는가? |
| Phase 4 | `approval_pending`, `manual_review`, `no_viable_candidate` 라우팅을 공용 계약 기준으로 구현할 수 있는가? |
| Phase 5 | 승인 후 PO draft에 필요한 필드가 batch report에 충분한가? |

## Final Check

- Phase 3 MVP tasks: Complete
- Tests: Passing
- Shared contract: Defined and validated
- Demo artifact: Ready
- Phase 4 handoff: Ready
