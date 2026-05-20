import copy
from graph.state import AgentState


def monitor_node(state: AgentState) -> AgentState:
    """
    Phase 1 연결 포인트.
    재고 모니터링을 수행하고 부족 자재를 감지한다.
    Phase 1 Agent 완성 후 이 함수 내부를 실제 Agent 호출로 교체한다.
    """
    new_state = copy.deepcopy(state)
    new_state["status"] = "SHORTAGE_DETECTED"
    if not new_state.get("shortage_event"):
        new_state["shortage_event"] = {
            "material_id": "BT-H-M10-50",
            "description": "Hex bolt M10x50",
            "current_stock": 12,
            "minimum_stock": 100,
            "shortage_qty": 88,
            "detected_at": "2026-05-06T09:00:00Z"
        }
    return new_state


def search_node(state: AgentState) -> AgentState:
    """
    Phase 2 연결 포인트.
    웹 리서치를 수행하고 공급 업체 후보를 수집한다.
    Phase 2 Agent 완성 후 이 함수 내부를 실제 Agent 호출로 교체한다.
    """
    new_state = copy.deepcopy(state)
    new_state["retry_count"] += 1

    new_state["candidate_results"] = [
        {
            "candidate_id": "WEB-001",
            "vendor_name": "MISUMI Korea",
            "source_url": "https://example.com/item/123",
            "price_krw": 450,
            "lead_time_days": 1,
            "moq": 10
        }
    ]

    if new_state["candidate_results"]:
        new_state["status"] = "CANDIDATES_FOUND"

    return new_state


def evaluate_node(state: AgentState) -> AgentState:
    """
    Phase 3 계약 기반 라우팅.
    evaluation_report_batch의 next_action 값만 읽어 status를 변경한다.
    점수를 직접 재계산하지 않는다.

    C팀 계약 기준 next_action 허용값:
        approval_pending    → APPROVAL_PENDING
        manual_review       → REVIEW_REQUIRED
        no_viable_candidate → REJECTED

    selected_candidate_id는 evaluation_report_batch["top_candidate_id"]에서 꺼낸다.
    candidate_results에서 꺼내지 않는다. (C팀 계약 기준)
    """
    new_state = copy.deepcopy(state)
    report = new_state.get("evaluation_report_batch", {})
    next_action = report.get("next_action")

    if next_action == "approval_pending":
        new_state["status"] = "APPROVAL_PENDING"
        # C팀 계약: top_candidate_id는 evaluation_report_batch에서 꺼냄
        new_state["selected_candidate_id"] = report.get("top_candidate_id")

    elif next_action == "manual_review":
        new_state["status"] = "REVIEW_REQUIRED"

    elif next_action == "no_viable_candidate":
        new_state["status"] = "REJECTED"

    return new_state


def human_approval_node(state: AgentState) -> AgentState:
    """
    Human-in-the-Loop 승인 처리.
    workflow.py의 interrupt_before=["human_approval"] 설정으로
    이 노드 진입 전 워크플로우가 일시 정지된다.
    외부에서 approval dict를 주입한 뒤 재개하면 이 함수가 실행된다.
    """
    new_state = copy.deepcopy(state)
    approved = new_state.get("approval", {}).get("approved", False)

    if approved:
        new_state["status"] = "APPROVED"
    else:
        new_state["status"] = "REJECTED"

    return new_state


def report_node(state: AgentState) -> AgentState:
    """
    PO 초안 생성.
    status가 APPROVED일 때만 실행된다.

    C팀 계약 기준:
        vendor 정보는 evaluation_report_batch["items"]에서
        top_candidate_id와 일치하는 항목의 candidate_material에서 꺼낸다.
        candidate_results에서 꺼내지 않는다.

    Phase 5 전달 필드: vendor_name / material_code / quantity / unit_price / total_price
    """
    new_state = copy.deepcopy(state)

    if new_state.get("status") != "APPROVED":
        return new_state

    report = new_state.get("evaluation_report_batch", {})
    selected_id = new_state.get("selected_candidate_id")
    items = report.get("items", [])

    # C팀 계약: items에서 top_candidate_id와 일치하는 항목 찾기
    selected_item = next(
        (
            item for item in items
            if item.get("candidate_material", {}).get("candidate_id") == selected_id
        ),
        None
    )

    if selected_item:
        candidate = selected_item.get("candidate_material", {})
        shortage = new_state.get("shortage_event", {})
        qty = shortage.get("shortage_qty", 0) or 0
        price = candidate.get("price_krw")
        if price in {None, ""}:
            new_state["status"] = "REJECTED"
            return new_state
        qty = int(qty)
        price = int(price)

        new_state["po_draft"] = {
            "vendor_name": candidate.get("vendor_name"),
            "material_code": shortage.get("material_id"),
            "quantity": qty,
            "unit_price": price,
            "total_price": qty * price
        }
        new_state["status"] = "PO_DRAFT_CREATED"

    return new_state
