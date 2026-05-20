import pytest
from unittest.mock import patch
from graph.workflow import build_graph
from graph.state import make_initial_state


# ─── C팀 계약 기준 mock evaluation_report_batch ───────────────────────────────

MOCK_REPORT_APPROVAL_PENDING = {
    "batch_report_id": "BER-20260504-001",
    "generated_at": "2026-05-04T14:30:00+09:00",
    "mode": "urgent",
    "candidate_count": 1,
    "decision_counts": {
        "recommend": 1,
        "conditional_approve": 0,
        "review_required": 0,
        "reject": 0
    },
    "top_candidate_id": "WEB-001",
    "next_action": "approval_pending",
    "items": [
        {
            "report_id": "ER-20260504-001",
            "generated_at": "2026-05-04T14:30:00+09:00",
            "mode": "urgent",
            "candidate_material": {
                "candidate_id": "WEB-001",
                "vendor_name": "MISUMI Korea",
                "source_url": "https://example.com/item/123",
                "price_krw": 450,
                "lead_time_days": 1,
                "moq": 10
            },
            "scores": {
                "final_score": 87
            },
            "decision_context": {
                "decision": "recommend",
                "risk_level": "low",
                "recommendation_reason": "스펙 일치, 리드타임 1일로 긴급 조달 적합",
                "approval_conditions": [],
                "rejection_reason": None
            }
        }
    ]
}

MOCK_REPORT_NO_VIABLE = {
    "batch_report_id": "BER-20260504-002",
    "generated_at": "2026-05-04T14:30:00+09:00",
    "mode": "urgent",
    "candidate_count": 0,
    "decision_counts": {
        "recommend": 0,
        "conditional_approve": 0,
        "review_required": 0,
        "reject": 1
    },
    "top_candidate_id": None,
    "next_action": "no_viable_candidate",
    "items": []
}


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def graph():
    return build_graph()


# ─── Tests ────────────────────────────────────────────────────────────────────

def test_happy_path(graph):
    """
    Happy Path 시나리오.
    후보 수집 → 평가 통과(approval_pending) → 사용자 승인 → PO 생성.
    - status == PO_DRAFT_CREATED
    - po_draft is not None
    - vendor 정보는 C팀 items[].candidate_material에서 꺼낸다.
    """
    initial_state = make_initial_state("wf-happy-001")
    initial_state["evaluation_report_batch"] = MOCK_REPORT_APPROVAL_PENDING

    config = {"configurable": {"thread_id": "1"}}

    for _ in graph.stream(initial_state, config=config):
        pass

    state = graph.get_state(config).values
    assert state["status"] == "APPROVAL_PENDING"
    assert state["selected_candidate_id"] == "WEB-001"  # top_candidate_id 기준

    state["approval"]["approved"] = True
    state["approval"]["approver"] = "홍길동"
    state["approval"]["approved_at"] = "2026-05-06T10:30:00Z"
    graph.update_state(config, state)

    for _ in graph.stream(None, config=config):
        pass

    final_state = graph.get_state(config).values
    assert final_state["status"] == "PO_DRAFT_CREATED"
    assert final_state["po_draft"] is not None
    assert final_state["po_draft"]["vendor_name"] == "MISUMI Korea"
    assert final_state["po_draft"]["total_price"] > 0


def test_no_candidates_retry_limit():
    """
    후보 없음 재시도 한도 초과 시나리오.
    retry_count >= 3 이후 종료.
    PO_DRAFT_CREATED에 도달하지 않아야 한다.
    """
    initial_state = make_initial_state("wf-retry-001")
    config = {"configurable": {"thread_id": "2"}}

    with patch("graph.workflow.search_node") as mock_search:
        def side_effect(state):
            import copy
            new_state = copy.deepcopy(state)
            new_state["retry_count"] += 1
            new_state["candidate_results"] = []
            return new_state

        mock_search.side_effect = side_effect
        
        # 컴파일 전에 Mock을 적용한 뒤 그래프를 빌드해야 반영됩니다.
        test_graph = build_graph()

        for _ in test_graph.stream(initial_state, config=config):
            pass

    final_state = test_graph.get_state(config).values
    assert final_state["retry_count"] >= 3
    assert final_state["status"] != "PO_DRAFT_CREATED"


def test_no_viable_candidate_skips_approval(graph):
    """
    no_viable_candidate 시나리오.
    C팀 next_action == no_viable_candidate 일 때
    APPROVAL_PENDING을 거치지 않고 REJECTED 되어야 한다.
    po_draft는 None이어야 한다.
    """
    initial_state = make_initial_state("wf-skip-001")
    initial_state["evaluation_report_batch"] = MOCK_REPORT_NO_VIABLE
    config = {"configurable": {"thread_id": "3"}}

    for _ in graph.stream(initial_state, config=config):
        pass

    final_state = graph.get_state(config).values
    assert final_state["status"] == "REJECTED"
    assert final_state["status"] != "APPROVAL_PENDING"
    assert final_state["po_draft"] is None


def test_rejection_no_po(graph):
    """
    사용자 반려 시나리오.
    approved: False 입력 후 po_draft가 None이어야 한다.
    """
    initial_state = make_initial_state("wf-reject-001")
    initial_state["evaluation_report_batch"] = MOCK_REPORT_APPROVAL_PENDING
    config = {"configurable": {"thread_id": "4"}}

    for _ in graph.stream(initial_state, config=config):
        pass

    state = graph.get_state(config).values
    state["approval"]["approved"] = False
    graph.update_state(config, state)

    for _ in graph.stream(None, config=config):
        pass

    final_state = graph.get_state(config).values
    assert final_state["po_draft"] is None


def test_approval_correct_candidate(graph):
    """
    승인 후 올바른 후보로 PO 생성 시나리오.
    C팀 계약 기준: vendor 정보는 items[].candidate_material에서 꺼낸다.
    po_draft["vendor_name"] is not None
    po_draft["total_price"] > 0
    """
    initial_state = make_initial_state("wf-correct-001")
    initial_state["evaluation_report_batch"] = MOCK_REPORT_APPROVAL_PENDING
    config = {"configurable": {"thread_id": "5"}}

    for _ in graph.stream(initial_state, config=config):
        pass

    state = graph.get_state(config).values
    state["approval"]["approved"] = True
    state["approval"]["approver"] = "홍길동"
    state["approval"]["approved_at"] = "2026-05-06T10:30:00Z"
    graph.update_state(config, state)

    for _ in graph.stream(None, config=config):
        pass

    final_state = graph.get_state(config).values
    assert final_state["po_draft"]["vendor_name"] is not None
    assert final_state["po_draft"]["total_price"] > 0


def test_approval_rejects_candidate_without_price(graph):
    """
    가격이 추출되지 않은 후보는 PO 금액을 계산할 수 없으므로
    TypeError 없이 PO 생성을 중단해야 한다.
    """
    report = {
        **MOCK_REPORT_APPROVAL_PENDING,
        "items": [
            {
                **MOCK_REPORT_APPROVAL_PENDING["items"][0],
                "candidate_material": {
                    **MOCK_REPORT_APPROVAL_PENDING["items"][0]["candidate_material"],
                    "price_krw": None,
                },
            }
        ],
    }
    initial_state = make_initial_state("wf-no-price-001")
    initial_state["evaluation_report_batch"] = report
    config = {"configurable": {"thread_id": "6"}}

    for _ in graph.stream(initial_state, config=config):
        pass

    state = graph.get_state(config).values
    state["approval"]["approved"] = True
    graph.update_state(config, state)

    for _ in graph.stream(None, config=config):
        pass

    final_state = graph.get_state(config).values
    assert final_state["status"] != "PO_DRAFT_CREATED"
    assert final_state["po_draft"] is None
