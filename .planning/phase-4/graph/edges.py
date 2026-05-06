from langgraph.graph import END
from .state import AgentState

def route_after_search(state: AgentState) -> str:
    if state.get("candidate_results"):
        return "evaluate"
    if state.get("retry_count", 0) >= 3:
        return END
    return "search"

def route_after_evaluate(state: AgentState) -> str:
    status = state.get("status")
    if status == "APPROVAL_PENDING":
        return "human_approval"
    elif status == "REVIEW_REQUIRED":
        return END
    elif status == "REJECTED":
        return END
    return END

def route_after_approval(state: AgentState) -> str:
    approval = state.get("approval", {})
    if approval.get("approved") is True:
        return "report"
    return "search"
