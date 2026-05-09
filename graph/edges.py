from langgraph.graph import END
from graph.state import AgentState


def route_after_search(state: AgentState) -> str:
    """
    Search 결과에 따른 라우팅.
    - 후보 있음          → evaluate
    - 후보 없음 + 3회 초과 → END (무한 루프 방지)
    - 후보 없음 + 3회 미만 → search 재시도
    """
    if state.get("candidate_results"):
        return "evaluate"
    if state.get("retry_count", 0) >= 3:
        return END
    return "search"


def route_after_evaluate(state: AgentState) -> str:
    """
    C팀 next_action 기반 라우팅.
    - APPROVAL_PENDING → human_approval (워크플로우 일시 정지)
    - REVIEW_REQUIRED  → END (자동 발주 불가)
    - REJECTED         → END (재검색 또는 종료)
    """
    status = state.get("status")
    if status == "APPROVAL_PENDING":
        return "human_approval"
    return END


def route_after_approval(state: AgentState) -> str:
    """
    사용자 승인/반려에 따른 라우팅.
    - 승인 → report (PO 초안 생성)
    - 반려 → search (재검색 피드백 루프)
    """
    approved = state.get("approval", {}).get("approved", False)
    if approved:
        return "report"
    return "search"
