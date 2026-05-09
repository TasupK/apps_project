from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from graph.state import AgentState
from graph.nodes import (
    monitor_node,
    search_node,
    evaluate_node,
    human_approval_node,
    report_node,
)
from graph.edges import (
    route_after_search,
    route_after_evaluate,
    route_after_approval,
)


def build_graph():
    """
    Phase 4 전체 LangGraph 워크플로우를 조립하고 컴파일한다.

    흐름:
        monitor → search → evaluate → human_approval → report → END

    조건부 라우팅:
        search        : 후보 유무 및 retry_count 기반
        evaluate      : C팀 next_action 기반
        human_approval: 사용자 승인/반려 기반

    핵심 제약:
        interrupt_before=["human_approval"]
        → 승인 전 PO 생성 구조적 차단
    """
    workflow = StateGraph(AgentState)

    # 노드 등록
    workflow.add_node("monitor", monitor_node)
    workflow.add_node("search", search_node)
    workflow.add_node("evaluate", evaluate_node)
    workflow.add_node("human_approval", human_approval_node)
    workflow.add_node("report", report_node)

    # 시작점
    workflow.set_entry_point("monitor")

    # 고정 엣지
    workflow.add_edge("monitor", "search")

    # 조건부 엣지
    workflow.add_conditional_edges(
        "search",
        route_after_search,
        {
            "evaluate": "evaluate",
            "search": "search",
            END: END,
        }
    )

    workflow.add_conditional_edges(
        "evaluate",
        route_after_evaluate,
        {
            "human_approval": "human_approval",
            END: END,
        }
    )

    workflow.add_conditional_edges(
        "human_approval",
        route_after_approval,
        {
            "report": "report",
            "search": "search",
        }
    )

    # 고정 엣지
    workflow.add_edge("report", END)

    # 컴파일 — interrupt_before 필수
    memory = MemorySaver()
    compiled_graph = workflow.compile(
        checkpointer=memory,
        interrupt_before=["human_approval"]
    )

    return compiled_graph


if __name__ == "__main__":
    graph = build_graph()
    print("그래프 빌드 완료:", graph)
