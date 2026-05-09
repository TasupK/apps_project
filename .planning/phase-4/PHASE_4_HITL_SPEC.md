# Phase 4 Human-in-the-Loop Specification

**Owner:** Team Member D  
**Status:** MVP  
**Purpose:** 사람의 승인 개입 시점과 처리 방식을 정의한다.

---

## 핵심 원칙

평가 완료 후 워크플로우는 `human_approval` 노드 진입 전 강제로 일시 정지된다.  
외부에서 승인 또는 반려 입력이 올 때까지 상태를 유지한다.  
이 동작은 `interrupt_before=["human_approval"]` 설정으로 구조적으로 보장된다.

---

## 승인 흐름

```
evaluate_node 완료
    │
    ▼ (next_action == approval_pending)
[워크플로우 일시 정지] ◄── interrupt_before 작동
    │
    ▼
담당자에게 승인 요청 메시지 전송
    │
    ├─ approved: true  ──► status = APPROVED ──► report_node ──► PO_DRAFT_CREATED
    │
    └─ approved: false ──► status = REJECTED ──► search_node 재실행 (재검색 피드백)
```

---

## 승인 입력 구조

```json
{
  "approved": true,
  "approver": "홍길동",
  "approved_at": "2026-05-06T10:30:00Z"
}
```

---

## 승인 메시지에 포함되는 정보

Phase 3 산출물에서 아래 필드를 그대로 가져다 사용한다.  
Phase 4가 직접 계산하거나 가공하지 않는다.

- `items` — 후보 업체 목록
- `scores` — 평가 점수
- `decision_context` — 판단 근거
- `spec_analysis.highlighted_differences` — 스펙 차이 요약

---

## 반려 시 동작

반려(`approved: false`) 입력이 오면 `search_node`를 재실행한다.  
단, `retry_count >= 3`이면 재검색 없이 프로세스를 종료한다.  
재검색 시 검색 조건 변경 여부는 현재 MVP에서 수동으로 처리한다.

---

## MVP 한계

실제 시스템에서는 LangGraph의 `interrupt()`를 사용해 외부 입력을 기다린다.  
현재 MVP는 `approval` dict를 직접 주입하는 방식으로 구현되어 있다.  
실제 알림 발송(Slack, Email 등) 연동은 Phase 5 이후로 미룬다.
