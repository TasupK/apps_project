import pytest
from graph.state import make_initial_state
from graph.workflow import build_graph

def test_happy_path():
    graph = build_graph()
    config = {"configurable": {"thread_id": "happy"}}
    
    initial_state = make_initial_state("WF-100")
    initial_state["candidate_results"] = [
        {"id": "WEB-001", "vendor_name": "Happy Vendor", "unit_price": 5000}
    ]
    initial_state["evaluation_report_batch"] = {
        "next_action": "approval_pending",
        "top_candidate_id": "WEB-001"
    }
    initial_state["shortage_event"] = {"material_code": "MAT-01", "quantity": 100}
    
    for event in graph.stream(initial_state, config=config):
        pass
        
    state = graph.get_state(config).values
    assert state["status"] == "APPROVAL_PENDING"
    
    graph.update_state(config, {"approval": {"approved": True, "approver": "Manager"}})
    
    for event in graph.stream(None, config=config):
        pass
        
    final_state = graph.get_state(config).values
    assert final_state["status"] == "PO_DRAFT_CREATED"
    assert final_state["po_draft"] is not None
    assert final_state["po_draft"]["vendor_name"] == "Happy Vendor"
    assert final_state["po_draft"]["total_price"] == 500000

def test_no_candidates_retry_limit():
    graph = build_graph()
    config = {"configurable": {"thread_id": "retry"}}
    
    initial_state = make_initial_state("WF-200")
    
    for event in graph.stream(initial_state, config=config):
        pass
        
    final_state = graph.get_state(config).values
    assert final_state["retry_count"] >= 3
    assert final_state["status"] != "PO_DRAFT_CREATED"
    assert final_state["po_draft"] is None

def test_no_viable_candidate_skips_approval():
    graph = build_graph()
    config = {"configurable": {"thread_id": "no-viable"}}
    
    initial_state = make_initial_state("WF-300")
    initial_state["candidate_results"] = [{"id": "WEB-002"}]
    initial_state["evaluation_report_batch"] = {
        "next_action": "no_viable_candidate"
    }
    
    for event in graph.stream(initial_state, config=config):
        pass
        
    final_state = graph.get_state(config).values
    assert final_state["status"] == "REJECTED"
    assert final_state.get("po_draft") is None

def test_rejection_no_po():
    graph = build_graph()
    config = {"configurable": {"thread_id": "reject"}}
    
    initial_state = make_initial_state("WF-400")
    initial_state["candidate_results"] = [{"id": "WEB-003"}]
    initial_state["evaluation_report_batch"] = {
        "next_action": "approval_pending",
        "top_candidate_id": "WEB-003"
    }
    
    for event in graph.stream(initial_state, config=config):
        pass
        
    graph.update_state(config, {"approval": {"approved": False}})
    
    for event in graph.stream(None, config=config):
        pass
        
    final_state = graph.get_state(config).values
    assert final_state["po_draft"] is None

def test_approval_correct_candidate():
    graph = build_graph()
    config = {"configurable": {"thread_id": "correct-candidate"}}
    
    initial_state = make_initial_state("WF-500")
    initial_state["candidate_results"] = [
        {"id": "WEB-001", "vendor_name": "Vendor A", "unit_price": 1000},
        {"id": "WEB-002", "vendor_name": "Vendor B", "unit_price": 2000}
    ]
    initial_state["evaluation_report_batch"] = {
        "next_action": "approval_pending",
        "top_candidate_id": "WEB-002"
    }
    initial_state["shortage_event"] = {"material_code": "MAT-222", "quantity": 50}
    
    for event in graph.stream(initial_state, config=config):
        pass
        
    graph.update_state(config, {"approval": {"approved": True}})
    
    for event in graph.stream(None, config=config):
        pass
        
    final_state = graph.get_state(config).values
    assert final_state["status"] == "PO_DRAFT_CREATED"
    assert final_state["po_draft"]["vendor_name"] == "Vendor B"
    assert final_state["po_draft"]["total_price"] == 100000
