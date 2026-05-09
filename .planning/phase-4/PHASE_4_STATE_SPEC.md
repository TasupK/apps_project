# Phase 4 AgentState Specification

**Owner:** Team Member D  
**Status:** MVP  
**Purpose:** 워크플로우 전체에서 사용되는 공통 상태 객체의 필드를 정의한다.

---

## Important Note

`AgentState`는 Phase 4의 내부 상태 객체다.  
각 노드는 이 state를 복사 후 수정하여 반환한다. 직접 mutate 금지.  
Phase 간 데이터 전달은 이 state 하나를 통해서만 이루어진다.

---

## 필드 정의

| 필드 | 타입 | 설명 | 담당 Phase |
|------|------|------|-----------|
| `workflow_id` | str | 워크플로우 고유 ID | Phase 4 |
| `status` | Literal | 현재 상태 (아래 상태표 참고) | Phase 4 |
| `shortage_event` | dict | 부족 자재 감지 이벤트 | Phase 1 |
| `candidate_results` | list | 웹 리서치 후보 목록 | Phase 2 |
| `evaluation_report_batch` | dict | 평가 리포트 (읽기 전용) | Phase 3 |
| `selected_candidate_id` | Optional[str] | 승인 대상 후보 ID | Phase 3→4 |
| `retry_count` | int | Search 재시도 횟수, 최대 3 | Phase 4 |
| `approval` | dict | 승인 정보 (아래 구조 참고) | Phase 4 |
| `po_draft` | Optional[dict] | 발주 초안, 승인 후에만 생성 | Phase 4→5 |

---

## 상태 전이표

| 상태 | 의미 | 다음 동작 |
|------|------|----------|
| `IDLE` | 대기 | 재고 모니터링 |
| `SHORTAGE_DETECTED` | 부족 감지 | 웹 리서치 실행 |
| `CANDIDATES_FOUND` | 후보 수집 완료 | 평가 실행 |
| `REVIEW_REQUIRED` | 검토 필요 | 사람 수동 검토 |
| `APPROVAL_PENDING` | 승인 대기 | 워크플로우 일시 정지 |
| `REJECTED` | 반려 | 재검색 또는 종료 |
| `APPROVED` | 승인 완료 | PO 초안 생성 |
| `PO_DRAFT_CREATED` | 초안 생성 완료 | Phase 5 전달 |

---

## approval 필드 구조

초기값
```json
{
  "required": true,
  "approved": null,
  "approver": null,
  "approved_at": null
}
```

승인 완료 시
```json
{
  "required": true,
  "approved": true,
  "approver": "홍길동",
  "approved_at": "2026-05-06T10:30:00Z"
}
```

---

## po_draft 필드 구조

승인 전에는 반드시 `null`이다.

```json
{
  "vendor_name": "MISUMI Korea",
  "material_code": "BT-H-M10-50",
  "quantity": 100,
  "unit_price": 450,
  "total_price": 45000
}
```
