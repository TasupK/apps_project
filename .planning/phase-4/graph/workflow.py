from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from .state import AgentState
from .nodes import monitor_node, search_node, evaluate_node, human_approval_node, report_node
from .edges import route_after_search, route_after_evaluate, route_after_approval

def build_graph():
    builder = StateGraph(AgentState)
    
    # Register nodes
    builder.add_node("monitor", monitor_node)
    builder.add_node("search", search_node)
    builder.add_node("evaluate", evaluate_node)
    builder.add_node("human_approval", human_approval_node)
    builder.add_node("report", report_node)
    
    # Set entry point
    builder.set_entry_point("monitor")
    
    # Add edges
    builder.add_edge("monitor", "search")
    
    builder.add_conditional_edges("search", route_after_search, {
        "evaluate": "evaluate",
        "search": "search",
        END: END
    })
    
    builder.add_conditional_edges("evaluate", route_after_evaluate, {
        "human_approval": "human_approval",
        END: END
    })
    
    builder.add_conditional_edges("human_approval", route_after_approval, {
        "report": "report",
        "search": "search"
    })
    
    builder.add_edge("report", END)
    
    # Compile graph with checkpointer and interrupt
    memory = MemorySaver()
    graph = builder.compile(
        checkpointer=memory,
        interrupt_before=["human_approval"]
    )
    
    return graph
