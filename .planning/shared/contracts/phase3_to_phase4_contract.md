# Phase 3 to Phase 4 Contract

**Status:** MVP contract  
**Producer:** Phase 3 - Trust & Evaluation Agent  
**Consumer:** Phase 4 - Orchestration & Human-in-the-Loop  
**Purpose:** Phase 3가 평가한 후보 결과를 Phase 4 승인 워크플로우가 같은 기준으로 해석하도록 고정한다.

## Contract Summary

Phase 3는 웹에서 수집된 후보 자재를 평가한 뒤 `evaluation_report_batch.json`을 생성한다.

Phase 4는 후보를 다시 평가하지 않는다. Phase 4는 이 JSON의 `next_action`을 기준으로 승인 요청, 수동 검토, 재검색/종료 상태를 라우팅한다.

## File

| Item | Value |
|---|---|
| Artifact | `output/evaluation_report_batch.json` |
| Format | JSON |
| Encoding | UTF-8 |
| Producer command | `python3 agents/evaluation_agent.py --batch --output output/evaluation_report_batch.json` |

## Next Action Rules

| `next_action` | Phase 4 meaning | Required Phase 4 behavior |
|---|---|---|
| `approval_pending` | 추천 또는 조건부 승인 후보가 있음 | 사용자 승인 요청 생성 |
| `manual_review` | 자동 승인 후보는 없지만 검토 가능한 후보가 있음 | 자동 발주 금지, 사람 검토 요청 생성 |
| `no_viable_candidate` | 사용할 수 있는 후보가 없음 | 후보 없음 상태로 처리하고 재검색 또는 종료 |

## Batch Schema

```json
{
  "batch_report_id": "BER-20260504-001",
  "generated_at": "2026-05-04T14:30:00+09:00",
  "mode": "urgent",
  "candidate_count": 3,
  "decision_counts": {
    "recommend": 1,
    "conditional_approve": 1,
    "review_required": 1,
    "reject": 0
  },
  "top_candidate_id": "WEB-001",
  "next_action": "approval_pending",
  "items": []
}
```

## Batch Fields

| Field | Type | Required | Description |
|---|---|---:|---|
| `batch_report_id` | string | Yes | Batch 평가 리포트 ID |
| `generated_at` | string | Yes | ISO 8601 생성 시각 |
| `mode` | enum | Yes | `normal`, `urgent` |
| `candidate_count` | integer | Yes | 평가한 후보 수 |
| `decision_counts` | object | Yes | 후보 판정값별 개수 |
| `top_candidate_id` | string or null | Yes | 최종 점수 기준 1순위 후보 ID |
| `next_action` | enum | Yes | Phase 4가 처리할 다음 상태 |
| `items` | array | Yes | 후보별 단일 평가 리포트 목록 |

## Item Schema

`items`의 각 원소는 후보 1개에 대한 평가 결과다.

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

## Key Item Fields for Phase 4

Phase 4는 모든 평가 로직을 다시 계산하지 않고 아래 필드만 읽으면 된다.

| Field | Purpose |
|---|---|
| `candidate_material.candidate_id` | 승인/반려 대상 후보 식별 |
| `candidate_material.vendor_name` | 사용자 승인 메시지의 판매업체명 |
| `candidate_material.price_krw` | 예상 구매 단가 |
| `candidate_material.lead_time_days` | 납기 표시 |
| `candidate_material.moq` | 최소 주문 수량 확인 |
| `scores.final_score` | 후보 정렬/요약 표시 |
| `decision_context.decision` | 후보별 추천/검토/반려 상태 |
| `decision_context.risk_level` | 승인 메시지의 위험등급 |
| `decision_context.recommendation_reason` | 사용자에게 보여줄 추천 근거 |
| `decision_context.approval_conditions` | 조건부 승인 시 확인 조건 |
| `decision_context.rejection_reason` | 반려 사유 |

## Decision Values

| Decision | Meaning |
|---|---|
| `recommend` | 사용자 승인 요청 가능 |
| `conditional_approve` | 조건 확인 문구와 함께 사용자 승인 요청 가능 |
| `review_required` | 자동 승인 금지, 사람 검토 필요 |
| `reject` | 승인 후보에서 제외 |

## Handoff Behavior

1. Phase 4 reads `output/evaluation_report_batch.json`.
2. Phase 4 checks `next_action`.
3. If `approval_pending`, Phase 4 selects `top_candidate_id` and shows an approval request.
4. If `manual_review`, Phase 4 shows review-required details from `items`.
5. If `no_viable_candidate`, Phase 4 does not create a PO draft.

## Boundary

- Phase 3 owns scoring, spec comparison, source trust, risk classification, and recommendation reasoning.
- Phase 4 owns workflow state, user approval, rejection handling, and handoff to PO draft creation.
- Phase 4 must not recalculate Phase 3 scores.
- Phase 3 must not call Phase 5 or create PO drafts directly.
