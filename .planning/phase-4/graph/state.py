from typing import TypedDict, Literal, Optional

Status = Literal[
    "IDLE", 
    "SHORTAGE_DETECTED", 
    "CANDIDATES_FOUND", 
    "REVIEW_REQUIRED", 
    "APPROVAL_PENDING", 
    "REJECTED", 
    "APPROVED", 
    "PO_DRAFT_CREATED"
]

class AgentState(TypedDict):
    workflow_id: str
    status: Status
    shortage_event: dict
    candidate_results: list
    evaluation_report_batch: dict
    selected_candidate_id: Optional[str]
    retry_count: int
    approval: dict
    po_draft: Optional[dict]

def make_initial_state(workflow_id: str) -> AgentState:
    return {
        "workflow_id": workflow_id,
        "status": "IDLE",
        "shortage_event": {},
        "candidate_results": [],
        "evaluation_report_batch": {},
        "selected_candidate_id": None,
        "retry_count": 0,
        "approval": {},
        "po_draft": None
    }
