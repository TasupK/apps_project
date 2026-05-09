# Phase 4 — Orchestration & Human-in-the-Loop

**Owner:** Team Member D  
**Status:** In Progress  
**Period:** Week 4–5  
**Purpose:** Monitor, Search, Evaluate, Report Agent를 단일 LangGraph 워크플로우로 연결하고 사람의 승인 게이트를 구현한다.

---

## Overview

Phase 4는 각 팀원이 만든 Agent 모듈을 하나의 실행 흐름으로 묶는다.  
핵심은 **통제된 자동화**다. 평가 리포트가 생성된 뒤에는 반드시 사람의 승인 또는 반려를 거쳐야 한다.  
승인 없이는 코드 구조상 PO 초안이 생성되지 않는다.

---

## Workflow

```
IDLE
 └─ monitor_node ──────────────────────► SHORTAGE_DETECTED
     └─ search_node ───── 후보 없음(재시도 max 3) ──► END
         └─ evaluate_node
             ├─ approval_pending ──► human_approval_node ──► APPROVED ──► report_node ──► PO_DRAFT_CREATED
             ├─ manual_review ────► REVIEW_REQUIRED (종료)
             └─ no_viable_candidate ──► REJECTED (종료)
```

---

## Deliverables

| 파일 | 설명 |
|------|------|
| `graph/state.py` | AgentState TypedDict 정의 |
| `graph/nodes.py` | 5개 Agent 노드 함수 |
| `graph/edges.py` | 조건부 라우팅 엣지 3종 |
| `graph/workflow.py` | 전체 그래프 조립 및 컴파일 |
| `tests/test_pipeline.py` | E2E 테스트 5종 |

---

## Key Design Decisions

- `interrupt_before=["human_approval"]` — 구조적으로 승인 전 PO 생성 차단
- Phase 3 계약(`evaluation_report_batch.json`)만 참조, 내부 로직 직접 import 금지
- `retry_count` 최대 3회 — 무한 루프 방지
- 각 노드는 state를 복사 후 수정하여 반환, 직접 mutate 금지
