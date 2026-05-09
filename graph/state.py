from typing import TypedDict, Literal, Optional


class AgentState(TypedDict):
    workflow_id: str
    status: Literal[
        "IDLE",
        "SHORTAGE_DETECTED",
        "CANDIDATES_FOUND",
        "REVIEW_REQUIRED",
        "APPROVAL_PENDING",
        "REJECTED",
        "APPROVED",
        "PO_DRAFT_CREATED"
    ]
    shortage_event: dict
    candidate_results: list
    evaluation_report_batch: dict  # C팀 output/evaluation_report_batch.json 그대로 주입
    selected_candidate_id: Optional[str]
    retry_count: int
    approval: dict  # required / approved / approver / approved_at
    po_draft: Optional[dict]  # vendor_name / material_code / quantity / unit_price / total_price


def make_initial_state(workflow_id: str) -> AgentState:
    return {
        "workflow_id": workflow_id,
        "status": "IDLE",
        "shortage_event": {},
        "candidate_results": [],
        "evaluation_report_batch": {},
        "selected_candidate_id": None,
        "retry_count": 0,
        "approval": {
            "required": False,
            "approved": None,
            "approver": None,
            "approved_at": None
        },
        "po_draft": None
    }
