import copy
from .state import AgentState

def monitor_node(state: AgentState) -> AgentState:
    new_state = copy.deepcopy(state)
    new_state["status"] = "SHORTAGE_DETECTED"
    # Populate shortage_event if not already present (for testing convenience)
    if not new_state.get("shortage_event"):
        new_state["shortage_event"] = {"material_code": "M001", "quantity": 100}
    return new_state

def search_node(state: AgentState) -> AgentState:
    new_state = copy.deepcopy(state)
    new_state["retry_count"] = new_state.get("retry_count", 0) + 1
    if new_state.get("candidate_results"):
        new_state["status"] = "CANDIDATES_FOUND"
    return new_state

def evaluate_node(state: AgentState) -> AgentState:
    new_state = copy.deepcopy(state)
    next_action = new_state.get("evaluation_report_batch", {}).get("next_action")
    
    if next_action == "approval_pending":
        new_state["status"] = "APPROVAL_PENDING"
        new_state["selected_candidate_id"] = new_state.get("evaluation_report_batch", {}).get("top_candidate_id")
    elif next_action == "manual_review":
        new_state["status"] = "REVIEW_REQUIRED"
    elif next_action == "no_viable_candidate":
        new_state["status"] = "REJECTED"
        
    return new_state

def human_approval_node(state: AgentState) -> AgentState:
    new_state = copy.deepcopy(state)
    approval = new_state.get("approval", {})
    if approval.get("approved") is True:
        new_state["status"] = "APPROVED"
    else:
        new_state["status"] = "REJECTED"
    return new_state

def report_node(state: AgentState) -> AgentState:
    new_state = copy.deepcopy(state)
    if new_state.get("status") == "APPROVED":
        selected_id = new_state.get("selected_candidate_id")
        candidate = None
        for cand in new_state.get("candidate_results", []):
            if cand.get("id") == selected_id:
                candidate = cand
                break
        
        vendor_name = candidate.get("vendor_name", "Unknown") if candidate else "Unknown"
        unit_price = candidate.get("unit_price", 0) if candidate else 0
        quantity = new_state.get("shortage_event", {}).get("quantity", 100)
        material_code = new_state.get("shortage_event", {}).get("material_code", "UNKNOWN")
        
        new_state["po_draft"] = {
            "vendor_name": vendor_name,
            "material_code": material_code,
            "quantity": quantity,
            "unit_price": unit_price,
            "total_price": quantity * unit_price
        }
        new_state["status"] = "PO_DRAFT_CREATED"
        
    return new_state
