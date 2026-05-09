# Phase 4 Format Contract

**Owner:** Team Member D  
**Status:** MVP — C팀 계약서 기준 반영  
**Purpose:** Phase 3 → Phase 4 → Phase 5 간 입출력 데이터 계약을 정의한다.

---

## Important Note

Phase 4는 Phase 3 내부 로직을 직접 참조하지 않는다.  
`output/evaluation_report_batch.json`의 `next_action` 필드만 읽어서 분기한다.  
점수 재계산, 스펙 비교, 신뢰도 분류는 Phase 3 소유다. Phase 4는 절대 재계산하지 않는다.

---

## Input Contract — Phase 3 → Phase 4

C팀 계약서 원문: `.planning/shared/contracts/evaluation_report_batch.schema.json`  
C팀 실행 커맨드: `python3 agents/evaluation_agent.py --batch --output output/evaluation_report_batch.json`

### next_action 허용값

| 값 | Phase 4 동작 |
|----|-------------|
| `approval_pending` | 승인 요청, top_candidate_id 기준으로 워크플로우 일시 정지 |
| `manual_review` | 자동 발주 금지, 사람 검토 요청 |
| `no_viable_candidate` | PO 생성 금지, 재검색 또는 종료 |

이 세 가지 외의 값이 오면 워크플로우는 예외 처리 없이 종료된다.

### Phase 4가 읽는 필드 목록

| 필드 | 용도 |
|------|------|
| `next_action` | 워크플로우 분기 기준 |
| `top_candidate_id` | selected_candidate_id 설정 기준 |
| `items[].candidate_material.candidate_id` | 승인 대상 후보 식별 |
| `items[].candidate_material.vendor_name` | PO 초안 업체명 |
| `items[].candidate_material.price_krw` | PO 초안 단가 |
| `items[].candidate_material.lead_time_days` | 승인 메시지 납기 표시 |
| `items[].candidate_material.moq` | 최소 주문 수량 확인 |
| `items[].scores.final_score` | 승인 메시지 점수 표시 |
| `items[].decision_context.decision` | 후보별 추천/검토/반려 상태 |
| `items[].decision_context.risk_level` | 승인 메시지 위험등급 |
| `items[].decision_context.recommendation_reason` | 승인 메시지 추천 근거 |
| `items[].decision_context.approval_conditions` | 조건부 승인 시 확인 조건 |

### Batch 최상위 구조

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

---

## Output Contract — Phase 4 → Phase 5

### 필수 필드

```json
{
  "workflow_id": "WF-20260506-001",
  "status": "PO_DRAFT_CREATED",
  "selected_candidate_id": "WEB-001",
  "approval": {
    "required": true,
    "approved": true,
    "approver": "홍길동",
    "approved_at": "2026-05-06T10:30:00Z"
  },
  "po_draft": {
    "vendor_name": "MISUMI Korea",
    "material_code": "BT-H-M10-50",
    "quantity": 88,
    "unit_price": 450,
    "total_price": 39600
  }
}
```

### 전달 불가 조건

| 상태 | 이유 |
|------|------|
| `REJECTED` | 사용자 반려 또는 no_viable_candidate |
| `REVIEW_REQUIRED` | 자동 처리 불가 |
| `retry_count >= 3` | 후보 없음 한도 초과 |

---

## Boundary

| 소유권 | Phase 3 | Phase 4 |
|--------|---------|---------|
| 점수 계산 | ✅ | ❌ |
| 스펙 비교 | ✅ | ❌ |
| 신뢰도 분류 | ✅ | ❌ |
| 워크플로우 상태 | ❌ | ✅ |
| 사용자 승인 | ❌ | ✅ |
| PO 초안 생성 | ❌ | ✅ |
