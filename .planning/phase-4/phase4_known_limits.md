# Phase 4 Known Limits

**Owner:** Team Member D  
**Status:** MVP 기준 작성  
**Purpose:** 현재 구현의 한계와 미구현 항목을 팀원들에게 투명하게 공유한다.

---

## 현재 MVP에서 의도적으로 단순화한 항목

**Human-in-the-Loop 입력 방식**  
실제 시스템에서는 LangGraph `interrupt()`로 외부 입력을 기다린다.  
현재는 `approval` dict를 코드에서 직접 주입하는 방식으로 구현되어 있다.  
실제 승인 UI 또는 Slack 연동은 MVP 범위 밖이다.

**반려 후 재검색 조건 변경**  
반려 시 `search_node`를 재실행하지만 검색 조건은 변경되지 않는다.  
조건 변경 로직은 현재 수동으로 처리해야 한다.

**monitor_node / search_node 시뮬레이션**  
Phase 1, 2 Agent가 완성되기 전까지 노드 내부는 mock 데이터로 동작한다.  
실제 Agent 연결은 Phase 1, 2 완료 후 `nodes.py`에서 교체한다.

---

## Phase 3 팀에 의존하는 항목

`evaluation_report_batch.json`의 `next_action` 값이 아래 세 가지 중 하나여야 한다.

- `approval_pending`
- `manual_review`
- `no_viable_candidate`

이 외의 값이 오면 현재 워크플로우는 예외 처리 없이 `end`로 종료된다.  
예외값 처리 로직은 Phase 3 계약 확정 후 추가할 예정이다.

---

## Phase 5 팀에 전달되지 않는 케이스

아래 상태에서는 `po_draft`가 생성되지 않으며 Phase 5로 데이터가 전달되지 않는다.

| 상태 | 원인 |
|------|------|
| `REJECTED` | 사용자 반려 |
| `REVIEW_REQUIRED` | 자동 처리 불가 판정 |
| `retry_count >= 3` | 후보 없음 한도 초과 |

이 케이스에 대한 Phase 5 측 예외 처리가 필요하다.

---

## 향후 개선 예정

- 실제 LangGraph `interrupt()` 기반 HITL 구현
- 반려 사유 기록 및 재검색 조건 자동 조정
- 승인 알림 발송 (Slack / Email)
- `REVIEW_REQUIRED` 상태 전용 처리 흐름 추가
