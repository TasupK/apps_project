from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from agents.evaluation_agent import evaluate_candidates_from_phase2_results
from agents.monitor_agent import scan_inventory
from agents.reporting_agent import write_evaluation_report
from agents.web_research.agent import run_web_research
from db.database import get_connection
from graph.state import make_initial_state
from graph.workflow import build_graph


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
PO_FILE = BASE_DIR / "PO_Result.csv"
ENV_FILE = BASE_DIR / ".env"
BUDGET_LIMIT_KRW = 5_000_000


st.set_page_config(page_title="BuyBee", layout="wide", page_icon="B")


def load_env_file(path: Path = ENV_FILE) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and value and key not in os.environ:
            os.environ[key] = value


load_env_file()


@st.cache_data(ttl=30)
def load_inventory_from_db() -> pd.DataFrame:
    query = """
        SELECT
            m.material_id,
            m.material_name,
            m.category,
            m.brand,
            m.mpn,
            m.technical_specification,
            i.current_stock,
            i.safety_stock,
            i.plant,
            i.last_updated
        FROM inventory i
        JOIN material_master m ON i.material_id = m.material_id
        ORDER BY m.material_id
    """
    with get_connection() as conn:
        return pd.read_sql_query(query, conn)


def initialize_session() -> None:
    defaults = {
        "step": "idle",
        "approval_ready": False,
        "candidate_results": None,
        "evaluation_report": None,
        "selected_material_id": None,
        "po_created": PO_FILE.exists(),
        "po_row": None,
        "last_error": None,
        "messages": [
            {
                "role": "assistant",
                "content": "안녕하세요. 실제 재고 DB 기준으로 부족 자재를 확인하고 웹 리서치를 실행할 수 있습니다.",
            }
        ],
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def reset_demo_state() -> None:
    for key in [
        "step",
        "approval_ready",
        "candidate_results",
        "evaluation_report",
        "po_created",
        "po_row",
        "last_error",
    ]:
        st.session_state.pop(key, None)
    st.session_state.messages = [
        {"role": "assistant", "content": "상태를 초기화했습니다. 실제 재고 DB를 다시 읽습니다."}
    ]
    initialize_session()


def shortage_rows(inventory: pd.DataFrame) -> pd.DataFrame:
    shortage = inventory[inventory["current_stock"] < inventory["safety_stock"]].copy()
    shortage["shortage_qty"] = shortage["safety_stock"] - shortage["current_stock"]
    shortage["risk_ratio"] = shortage["current_stock"] / shortage["safety_stock"]
    return shortage.sort_values(["risk_ratio", "shortage_qty"], ascending=[True, False])


def shortage_events_by_material() -> dict[str, dict]:
    events = {}
    for event in scan_inventory():
        events[event.material_id] = json.loads(event.model_dump_json())
    return events


def default_selected_material(shortages: pd.DataFrame) -> str | None:
    if shortages.empty:
        return None
    current = st.session_state.get("selected_material_id")
    if current in set(shortages["material_id"]):
        return current
    return str(shortages.iloc[0]["material_id"])


def write_shortage_event(event: dict) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / f"shortage_event_{event['material_id']}.json"
    path.write_text(json.dumps(event, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def candidate_output_path(material_id: str) -> Path:
    return OUTPUT_DIR / f"candidate_results_{material_id}.json"


def evaluation_output_path(material_id: str) -> Path:
    return OUTPUT_DIR / f"evaluation_report_batch_{material_id}.json"


def run_actual_pipeline(event: dict) -> tuple[dict, dict]:
    event_path = write_shortage_event(event)
    candidate_path = candidate_output_path(event["material_id"])

    has_serpapi = bool(os.environ.get("SERPAPI_API_KEY"))
    has_openai = bool(os.environ.get("OPENAI_API_KEY"))
    provider = "serpapi" if has_serpapi else "llm_plan"

    candidate_results = run_web_research(
        input_path=event_path,
        output_path=candidate_path,
        search_mode="live",
        query_mode="llm" if has_openai else "deterministic",
        extraction_mode="llm" if has_openai and has_serpapi else "none",
        search_provider=provider,
        max_results_per_query=3,
        max_candidates=6,
    )

    evaluation_report = evaluate_candidates_from_phase2_results(candidate_path, mode="urgent")
    write_evaluation_report(evaluation_report, evaluation_output_path(event["material_id"]))
    return candidate_results, evaluation_report


def build_candidate_table(candidate_results: dict | None, evaluation_report: dict | None) -> pd.DataFrame:
    if evaluation_report:
        rows = []
        for item in evaluation_report.get("items", []):
            candidate = item.get("candidate_material", {})
            scores = item.get("scores", {})
            decision = item.get("decision_context", {})
            trust_notes = item.get("source_trust_notes", {})
            rows.append(
                {
                    "candidate_id": candidate.get("candidate_id"),
                    "vendor_name": candidate.get("vendor_name"),
                    "decision": decision.get("decision"),
                    "risk_level": decision.get("risk_level"),
                    "price_krw": candidate.get("price_krw"),
                    "lead_time_days": candidate.get("lead_time_days"),
                    "source_type": candidate.get("source_type"),
                    "compatibility_score": scores.get("compatibility_score"),
                    "source_trust_score": scores.get("source_trust_score"),
                    "final_score": scores.get("final_score"),
                    "risk_note": " / ".join(trust_notes.get("risk_factors", []))
                    or decision.get("recommendation_reason"),
                    "source_url": candidate.get("source_url"),
                }
            )
        return pd.DataFrame(rows)

    rows = []
    for candidate in (candidate_results or {}).get("candidates", []):
        rows.append(
            {
                "candidate_id": candidate.get("candidate_id"),
                "vendor_name": candidate.get("vendor_name"),
                "decision": "not_evaluated",
                "risk_level": "Review",
                "price_krw": candidate.get("price_krw"),
                "lead_time_days": candidate.get("lead_time_days"),
                "source_type": candidate.get("source_type"),
                "compatibility_score": None,
                "source_trust_score": None,
                "final_score": None,
                "risk_note": candidate.get("spec_evidence"),
                "source_url": candidate.get("source_url"),
            }
        )
    return pd.DataFrame(rows)


def get_top_evaluation_item(evaluation_report: dict | None) -> dict | None:
    if not evaluation_report:
        return None
    items = evaluation_report.get("items", [])
    top_id = evaluation_report.get("top_candidate_id")
    return next(
        (item for item in items if item.get("candidate_material", {}).get("candidate_id") == top_id),
        items[0] if items else None,
    )


def run_phase4_approval(event: dict, evaluation_report: dict) -> dict:
    graph = build_graph()
    state = make_initial_state(f"streamlit-{event['material_id']}-{datetime.now().strftime('%H%M%S')}")
    state["shortage_event"] = {
        "material_id": event.get("material_id"),
        "description": event.get("material_name"),
        "shortage_qty": event.get("shortage_qty", 0),
    }
    state["evaluation_report_batch"] = evaluation_report

    config = {"configurable": {"thread_id": state["workflow_id"]}}
    for _ in graph.stream(state, config=config):
        pass

    current_state = graph.get_state(config).values
    if current_state.get("status") != "APPROVAL_PENDING":
        raise RuntimeError(f"Phase 4 approval is not available: {current_state.get('status')}")

    current_state["approval"] = {
        "required": True,
        "approved": True,
        "approver": "streamlit_user",
        "approved_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    graph.update_state(config, current_state)
    for _ in graph.stream(None, config=config):
        pass
    return graph.get_state(config).values


def write_po_from_phase4_state(final_state: dict, evaluation_report: dict) -> dict:
    po_draft = final_state.get("po_draft")
    if not po_draft:
        raise RuntimeError("Phase 4 did not produce po_draft.")

    item = get_top_evaluation_item(evaluation_report) or {}
    candidate = item.get("candidate_material", {})
    scores = item.get("scores", {})
    decision = item.get("decision_context", {})
    po_row = {
        "PO_DRAFT_NO": f"PO-DRAFT-{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "CREATED_AT": datetime.now().isoformat(timespec="seconds"),
        "WORKFLOW_STATUS": final_state.get("status"),
        "SOURCE": "phase4_po_draft",
        "VENDOR_NAME": po_draft.get("vendor_name"),
        "MATERIAL_ID": po_draft.get("material_code"),
        "CANDIDATE_ID": candidate.get("candidate_id"),
        "UNIT_PRICE_KRW": po_draft.get("unit_price"),
        "ORDER_QTY": po_draft.get("quantity"),
        "TOTAL_AMOUNT_KRW": po_draft.get("total_price"),
        "LEAD_TIME_DAYS": candidate.get("lead_time_days"),
        "SOURCE_URL": candidate.get("source_url"),
        "FINAL_SCORE": scores.get("final_score"),
        "RISK_NOTE": decision.get("recommendation_reason"),
    }
    pd.DataFrame([po_row]).to_csv(PO_FILE, index=False)
    st.session_state.po_created = True
    st.session_state.po_row = po_row
    return po_row


def assistant_reply(prompt: str, event: dict) -> str:
    text = prompt.strip().lower()

    if any(word in text for word in ["재고", "위험", "부족", "확인"]):
        st.session_state.step = "inventory_checked"
        st.session_state.approval_ready = False
        return (
            f"실제 DB 기준 **{event['material_id']} ({event['material_name']})** 재고는 "
            f"{event['current_stock']}개이고 안전재고는 {event['safety_stock']}개입니다. "
            f"부족 수량은 **{event['shortage_qty']}개**입니다."
        )

    if any(word in text for word in ["대체", "찾아", "검색", "후보", "업체"]):
        try:
            with st.spinner("웹 리서치와 평가를 실행하는 중입니다..."):
                candidate_results, evaluation_report = run_actual_pipeline(event)
        except Exception as exc:
            st.session_state.last_error = str(exc)
            st.session_state.approval_ready = False
            return f"파이프라인 실행이 실패했습니다.\n\n`{exc}`"

        st.session_state.candidate_results = candidate_results
        st.session_state.evaluation_report = evaluation_report
        st.session_state.step = "candidates_loaded"

        table = build_candidate_table(candidate_results, evaluation_report)
        action = evaluation_report.get("next_action")
        st.session_state.approval_ready = action == "approval_pending"
        top_item = get_top_evaluation_item(evaluation_report)
        top_candidate = top_item.get("candidate_material", {}) if top_item else {}

        if action == "approval_pending":
            return (
                f"후보 {len(table)}개를 수집하고 Phase 3/4 승인 대기 조건을 확인했습니다. "
                f"승인 대상은 **{top_candidate.get('vendor_name')} / {top_candidate.get('candidate_id')}**입니다."
            )
        if action == "manual_review":
            return "후보는 찾았지만 자동 승인 대상이 아닙니다. 구매 담당자 수동 검토가 필요해 PO 초안 생성을 잠급니다."
        return "승인 가능한 후보를 찾지 못했습니다. PO 초안 생성은 잠겨 있습니다."

    if any(word in text for word in ["반려", "거절", "보류", "중단"]):
        st.session_state.step = "rejected"
        st.session_state.approval_ready = False
        return "반려로 기록했습니다. PO 초안은 생성하지 않았습니다."

    if any(word in text for word in ["승인", "발주", "진행", "ok", "yes", "응"]):
        if not st.session_state.approval_ready or not st.session_state.evaluation_report:
            return "아직 Phase 4 승인 대기 상태가 아닙니다. 먼저 `대체품 찾아줘`로 후보 평가를 완료해주세요."
        try:
            final_state = run_phase4_approval(event, st.session_state.evaluation_report)
            po_row = write_po_from_phase4_state(final_state, st.session_state.evaluation_report)
        except Exception as exc:
            return f"PO 초안 생성에 실패했습니다.\n\n`{exc}`"
        st.session_state.step = "po_created"
        st.session_state.approval_ready = False
        return (
            f"승인 완료했습니다. Phase 4 `po_draft` 기준으로 `{PO_FILE.name}`를 생성했습니다.\n\n"
            f"{po_row['PO_DRAFT_NO']} / {po_row['VENDOR_NAME']} / "
            f"{po_row['ORDER_QTY']}개 / {po_row['TOTAL_AMOUNT_KRW']:,}원"
        )

    return "재고 확인, 대체품 검색, 승인, 반려 중 하나로 진행할 수 있습니다."


def render_inventory(inventory: pd.DataFrame, shortages: pd.DataFrame) -> None:
    st.subheader("실제 재고 DB")
    chart = inventory[["material_name", "current_stock", "safety_stock"]].set_index("material_name")
    st.bar_chart(chart, color=["#d64545", "#2563eb"])
    st.dataframe(
        shortages[
            [
                "material_id",
                "material_name",
                "category",
                "brand",
                "mpn",
                "current_stock",
                "safety_stock",
                "shortage_qty",
                "plant",
            ]
        ],
        width="stretch",
        hide_index=True,
    )


def render_pipeline_results(event: dict) -> None:
    st.subheader("웹 리서치 및 평가 결과")
    candidate_results = st.session_state.candidate_results
    evaluation_report = st.session_state.evaluation_report

    if st.session_state.last_error:
        st.error(st.session_state.last_error)

    if not candidate_results:
        st.info("아직 웹 검색을 실행하지 않았습니다. 우측 승인 창에서 `대체품 찾아줘`를 입력하세요.")
        return

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("검색 ID", candidate_results.get("search_id", "-"))
    c2.metric("검색 후보", len(candidate_results.get("candidates", [])))
    c3.metric("다음 액션", evaluation_report.get("next_action", "-") if evaluation_report else "-")
    c4.metric("예산 한도", f"{BUDGET_LIMIT_KRW:,}원")

    st.markdown("**부족 자재 스펙**")
    st.info(f"{event.get('material_id')} / {event.get('material_name')}\n\n{event.get('technical_specification')}")

    table = build_candidate_table(candidate_results, evaluation_report)
    if table.empty:
        st.warning("검증된 검색 후보가 없습니다. 검색 키워드 또는 API 설정을 확인해야 합니다.")
        return

    st.dataframe(
        table[
            [
                "candidate_id",
                "vendor_name",
                "decision",
                "risk_level",
                "price_krw",
                "lead_time_days",
                "source_type",
                "compatibility_score",
                "source_trust_score",
                "final_score",
                "risk_note",
                "source_url",
            ]
        ],
        width="stretch",
        hide_index=True,
    )

    top_item = get_top_evaluation_item(evaluation_report)
    if top_item:
        candidate = top_item.get("candidate_material", {})
        decision = top_item.get("decision_context", {})
        st.success(
            f"현재 후보: {candidate.get('vendor_name')} / {candidate.get('candidate_id')} "
            f"({decision.get('decision')})"
        )
        st.caption(f"출처 URL: {candidate.get('source_url')}")


def render_po() -> None:
    if PO_FILE.exists():
        st.subheader("PO 초안")
        st.dataframe(pd.read_csv(PO_FILE), width="stretch", hide_index=True)


def render_assistant(event: dict) -> None:
    st.subheader("AI Personal Assistant")
    st.caption("Phase 4 승인 게이트를 거쳐 PO 초안을 생성합니다.")

    with st.container(height=500):
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

    prompt = st.chat_input("재고 확인해줘 / 대체품 찾아줘 / 승인 / 반려")
    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        response = assistant_reply(prompt, event)
        st.session_state.messages.append({"role": "assistant", "content": response})
        st.rerun()

    cols = st.columns(2)
    if cols[0].button("상태 초기화", width="stretch"):
        reset_demo_state()
        st.rerun()
    if cols[1].button("검색 실행", width="stretch"):
        response = assistant_reply("대체품 찾아줘", event)
        st.session_state.messages.append({"role": "assistant", "content": response})
        st.rerun()


def main() -> None:
    initialize_session()
    inventory = load_inventory_from_db()
    shortages = shortage_rows(inventory)

    st.title("BuyBee 실제 데이터 대체 자재 승인 대시보드")
    st.caption("SQLite 재고 DB에서 부족 자재를 읽고, Phase 4 승인 게이트 이후에만 PO 초안을 생성합니다.")

    if shortages.empty:
        st.success("현재 부족 자재가 없습니다.")
        return

    selected_default = default_selected_material(shortages)
    selected_material = st.sidebar.selectbox(
        "부족 자재 선택",
        list(shortages["material_id"]),
        index=list(shortages["material_id"]).index(selected_default),
    )
    st.session_state.selected_material_id = selected_material

    events = shortage_events_by_material()
    event = events[selected_material]

    st.sidebar.markdown("**검색 설정**")
    st.sidebar.write("검색 제공자:", "SerpAPI" if os.environ.get("SERPAPI_API_KEY") else "llm_plan")
    st.sidebar.write("상세 추출:", "OpenAI LLM" if os.environ.get("OPENAI_API_KEY") else "검색 결과 스니펫")
    if not os.environ.get("SERPAPI_API_KEY"):
        st.sidebar.info("SERPAPI_API_KEY가 없어 오프라인 검색 계획 모드로 실행됩니다.")

    top_metrics = st.columns(4)
    top_metrics[0].metric("선택 자재", event["material_id"])
    top_metrics[1].metric("카테고리", event["category"])
    top_metrics[2].metric("부족 수량", f"{event['shortage_qty']:,}")
    top_metrics[3].metric("승인 상태", "대기" if st.session_state.approval_ready else "잠김")

    left, right = st.columns([7, 3.2], gap="large")
    with left:
        render_inventory(inventory, shortages)
        st.divider()
        render_pipeline_results(event)
        st.divider()
        render_po()
    with right:
        render_assistant(event)


if __name__ == "__main__":
    main()
