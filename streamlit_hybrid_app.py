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


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
PO_FILE = BASE_DIR / "PO_Result.csv"
ENV_FILE = BASE_DIR / ".env"
BUDGET_LIMIT_KRW = 5_000_000


st.set_page_config(page_title="BuyBee", layout="wide", page_icon="B")


def load_env_file(path: Path = ENV_FILE) -> None:
    """Load KEY=VALUE pairs from .env without overwriting shell env vars."""
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
        {
            "role": "assistant",
            "content": "상태를 초기화했습니다. 실제 재고 DB를 다시 읽습니다.",
        }
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


def run_actual_pipeline(event: dict) -> tuple[dict, dict | None]:
    """Run Phase 2 with real web search and Phase 3 when the evaluator supports it."""
    if not os.environ.get("SERPAPI_API_KEY"):
        raise RuntimeError(
            "SERPAPI_API_KEY가 없어 실제 웹 검색을 실행할 수 없습니다. "
            ".env 또는 터미널 환경변수에 SERPAPI_API_KEY를 설정한 뒤 다시 실행해주세요."
        )

    event_path = write_shortage_event(event)
    candidate_path = candidate_output_path(event["material_id"])
    extraction_mode = "llm" if os.environ.get("OPENAI_API_KEY") else "none"

    candidate_results = run_web_research(
        input_path=event_path,
        output_path=candidate_path,
        search_mode="live",
        query_mode="llm" if os.environ.get("OPENAI_API_KEY") else "deterministic",
        extraction_mode=extraction_mode,
        search_provider="serpapi",
        max_results_per_query=3,
        max_candidates=6,
    )

    evaluation_report = None
    if event.get("category", "").lower() == "fastener":
        evaluation_report = evaluate_candidates_from_phase2_results(candidate_path, mode="urgent")
        write_evaluation_report(evaluation_report, evaluation_output_path(event["material_id"]))

    return candidate_results, evaluation_report


def score_source_readiness(candidate: dict) -> int:
    score = 0
    source_type = str(candidate.get("source_type") or "").lower()
    if source_type in {"official_distributor", "manufacturer_page"}:
        score += 30
    elif source_type == "industrial_marketplace":
        score += 22
    elif source_type == "marketplace":
        score += 12
    score += 20 if candidate.get("price_listed") else 0
    score += 20 if candidate.get("stock_listed") else 0
    score += 20 if candidate.get("leadtime_listed") else 0
    score += 10 if candidate.get("source_url") else 0
    return min(score, 100)


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
        readiness_score = score_source_readiness(candidate)
        rows.append(
            {
                "candidate_id": candidate.get("candidate_id"),
                "vendor_name": candidate.get("vendor_name"),
                "decision": "human_review",
                "risk_level": "Review",
                "price_krw": candidate.get("price_krw"),
                "lead_time_days": candidate.get("lead_time_days"),
                "source_type": candidate.get("source_type"),
                "compatibility_score": None,
                "source_trust_score": readiness_score,
                "final_score": readiness_score,
                "risk_note": candidate.get("spec_evidence"),
                "source_url": candidate.get("source_url"),
            }
        )
    return pd.DataFrame(rows)


def get_top_candidate(candidate_results: dict | None, evaluation_report: dict | None) -> dict | None:
    if evaluation_report:
        top_id = evaluation_report.get("top_candidate_id")
        items = evaluation_report.get("items", [])
        top_item = next(
            (
                item
                for item in items
                if item.get("candidate_material", {}).get("candidate_id") == top_id
            ),
            items[0] if items else None,
        )
        return top_item.get("candidate_material") if top_item else None

    candidates = (candidate_results or {}).get("candidates", [])
    if not candidates:
        return None
    return max(candidates, key=score_source_readiness)


def create_po_result(event: dict, candidate_results: dict | None, evaluation_report: dict | None) -> dict:
    candidate = get_top_candidate(candidate_results, evaluation_report)
    if not candidate:
        raise RuntimeError("승인할 후보가 없습니다.")

    unit_price = int(candidate.get("price_krw") or 0)
    quantity = int(event.get("shortage_qty") or 0)
    total_amount = unit_price * quantity
    po_row = {
        "PO_DRAFT_NO": f"PO-DRAFT-{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "CREATED_AT": datetime.now().isoformat(timespec="seconds"),
        "WORKFLOW_STATUS": "PO_DRAFT_CREATED",
        "SOURCE": "live_phase2_web_research",
        "TARGET_MATERIAL_ID": event.get("material_id"),
        "TARGET_DESCRIPTION": event.get("material_name"),
        "CANDIDATE_ID": candidate.get("candidate_id"),
        "VENDOR_NAME": candidate.get("vendor_name"),
        "ORDER_QTY": quantity,
        "UNIT_PRICE_KRW": unit_price,
        "TOTAL_AMOUNT_KRW": total_amount,
        "LEAD_TIME_DAYS": candidate.get("lead_time_days"),
        "SOURCE_URL": candidate.get("source_url"),
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
            with st.spinner("실제 웹 검색과 후보 수집을 실행하는 중입니다..."):
                candidate_results, evaluation_report = run_actual_pipeline(event)
        except Exception as exc:
            st.session_state.last_error = str(exc)
            st.session_state.approval_ready = False
            return f"실제 파이프라인 실행이 실패했습니다.\n\n`{exc}`"

        st.session_state.candidate_results = candidate_results
        st.session_state.evaluation_report = evaluation_report
        table = build_candidate_table(candidate_results, evaluation_report)
        st.session_state.step = "candidates_loaded"
        st.session_state.approval_ready = not table.empty
        top = get_top_candidate(candidate_results, evaluation_report)
        if evaluation_report:
            action = evaluation_report.get("next_action")
            st.session_state.approval_ready = action == "approval_pending"
            return (
                f"실제 웹 검색 후보 {len(table)}개를 수집하고 Phase 3 평가까지 완료했습니다. "
                f"다음 액션은 **{action}**입니다. 1순위 후보는 "
                f"**{top.get('vendor_name')} / {top.get('candidate_id')}**입니다."
            )
        return (
            f"실제 웹 검색 후보 {len(table)}개를 수집했습니다. "
            "현재 자재 카테고리는 fastener 평가 엔진 대상이 아니어서 구매 담당자 검토 기준으로 표시합니다. "
            f"우선 검토 후보는 **{top.get('vendor_name')} / {top.get('candidate_id')}**입니다."
            if top
            else "실제 검색은 실행됐지만 승인 가능한 후보를 찾지 못했습니다."
        )

    if any(word in text for word in ["반려", "거절", "보류", "중단"]):
        st.session_state.step = "rejected"
        st.session_state.approval_ready = False
        return "반려로 기록했습니다. PO 초안은 생성하지 않았습니다."

    if any(word in text for word in ["승인", "발주", "진행", "ok", "yes", "응"]):
        if not st.session_state.approval_ready:
            return "아직 승인 가능한 실제 검색 후보가 없습니다. 먼저 `대체품 찾아줘`로 실제 파이프라인을 실행해주세요."
        try:
            po_row = create_po_result(
                event,
                st.session_state.candidate_results,
                st.session_state.evaluation_report,
            )
        except Exception as exc:
            return f"PO 초안 생성에 실패했습니다.\n\n`{exc}`"
        st.session_state.step = "po_created"
        st.session_state.approval_ready = False
        return (
            f"승인 완료했습니다. 실제 검색 후보 기준으로 `{PO_FILE.name}`를 생성했습니다.\n\n"
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
        use_container_width=True,
        hide_index=True,
    )


def render_pipeline_results(event: dict) -> None:
    st.subheader("실제 웹 리서치 결과")
    candidate_results = st.session_state.candidate_results
    evaluation_report = st.session_state.evaluation_report

    if st.session_state.last_error:
        st.error(st.session_state.last_error)

    if not candidate_results:
        st.info("아직 실제 웹 검색을 실행하지 않았습니다. 우측 승인 창에서 `대체품 찾아줘`를 입력하세요.")
        return

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("검색 ID", candidate_results.get("search_id", "-"))
    c2.metric("검색 후보", len(candidate_results.get("candidates", [])))
    c3.metric("평가 모드", "Phase 3" if evaluation_report else "Human review")
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
        use_container_width=True,
        hide_index=True,
    )

    top = get_top_candidate(candidate_results, evaluation_report)
    if top:
        st.success(f"현재 승인 대상 후보: {top.get('vendor_name')} / {top.get('candidate_id')}")
        st.caption(f"출처 URL: {top.get('source_url')}")


def render_po() -> None:
    if PO_FILE.exists():
        st.subheader("PO 초안")
        st.dataframe(pd.read_csv(PO_FILE), use_container_width=True, hide_index=True)


def render_assistant(event: dict) -> None:
    st.subheader("AI Personal Assistant")
    st.caption("실제 파이프라인 실행 및 Human-in-the-loop 승인")

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
    if cols[0].button("상태 초기화", use_container_width=True):
        reset_demo_state()
        st.rerun()
    if cols[1].button("실제 검색 실행", use_container_width=True):
        response = assistant_reply("대체품 찾아줘", event)
        st.session_state.messages.append({"role": "assistant", "content": response})
        st.rerun()


def main() -> None:
    initialize_session()
    inventory = load_inventory_from_db()
    shortages = shortage_rows(inventory)

    st.title("BuyBee 실제 데이터 대체 자재 승인 대시보드")
    st.caption("SQLite 재고 DB에서 부족 자재를 읽고, 승인 요청 시 실제 웹 검색 기반 후보 수집을 실행합니다.")

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

    st.sidebar.markdown("**실제 검색 설정**")
    st.sidebar.write("검색 제공자: SerpAPI")
    st.sidebar.write("검색 범위: 한국 사이트만")
    st.sidebar.write("상세 추출:", "OpenAI LLM" if os.environ.get("OPENAI_API_KEY") else "검색 결과 스니펫")
    if not os.environ.get("SERPAPI_API_KEY"):
        st.sidebar.warning("SERPAPI_API_KEY가 없어 실제 검색 실행은 실패합니다.")

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
