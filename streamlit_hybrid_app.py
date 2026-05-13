import streamlit as st
import pandas as pd
import time
import os
import glob
import json
from datetime import datetime

# 1. 페이지 설정 (넓은 화면 레이아웃)
st.set_page_config(page_title="BuyBee", layout="wide", page_icon="🔎")

# 2. 데이터 경로 설정 (미리 만들어둔 mock data 활용)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INV_FILE = os.path.join(BASE_DIR, 'inventory_data.csv')
MAT_FILE = os.path.join(BASE_DIR, 'material_master.csv')
VEN_FILE = os.path.join(BASE_DIR, 'vendor_sourcing.csv')
PO_FILE = os.path.join(BASE_DIR, 'PO_Result.csv')
REPORT_PATTERN = os.path.join(BASE_DIR, 'output', 'evaluation_report_batch*.json')
BUDGET_LIMIT_KRW = 5_000_000

# 3. 데이터 로드 함수
@st.cache_data
def load_data():
    df_inv = pd.read_csv(INV_FILE)
    df_mat = pd.read_csv(MAT_FILE)
    df_ven = pd.read_csv(VEN_FILE)
    return df_inv, df_mat, df_ven

try:
    df_inv, df_mat, df_ven = load_data()
except FileNotFoundError:
    st.error("데이터 파일을 찾을 수 없습니다. inventory_data.csv 들이 같은 폴더에 있는지 확인해주세요.")
    st.stop()

# 4. 세션 상태 초기화 (챗봇 대화 기록 및 현재 단계 저장)
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "안녕하세요! SCM Copilot입니다. 무엇을 도와드릴까요? (명령어 예: '재고 확인해줘')"}]
if "step" not in st.session_state:
    st.session_state.step = 0 # 0: 대기, 1: 재고 감지, 2: 웹 검색/검증, 3: 발주 초안 생성
if "selected_material" not in st.session_state:
    st.session_state.selected_material = None
if "po_created" not in st.session_state:
    st.session_state.po_created = False
if "approval_ready" not in st.session_state:
    st.session_state.approval_ready = False

def get_shortage():
    shortage_df = df_inv[df_inv['CURRENT_STOCK'] < df_inv['SAFETY_STOCK']]
    if shortage_df.empty:
        return None
    row = shortage_df.iloc[0]
    return {
        "material_id": row["MATERIAL_ID"],
        "material_name": row["MATERIAL_NAME"],
        "current_stock": int(row["CURRENT_STOCK"]),
        "safety_stock": int(row["SAFETY_STOCK"]),
        "shortage_qty": int(row["SAFETY_STOCK"] - row["CURRENT_STOCK"]),
    }

def get_recommendation(target_material_id="MAT-1001"):
    target_spec = df_mat[df_mat['MATERIAL_ID'] == target_material_id]['TECHNICAL_SPECIFICATION'].values[0]
    candidates = df_ven[df_ven['MATERIAL_ID'] == 'MAT-1002'].sort_values(
        ["FINAL_SCORE", "LEAD_TIME_DAYS"],
        ascending=[False, True],
    )
    best = candidates.iloc[0]
    sub_spec = df_mat[df_mat['MATERIAL_ID'] == best['MATERIAL_ID']]['TECHNICAL_SPECIFICATION'].values[0]
    return target_spec, sub_spec, candidates, best

def load_latest_evaluation_report():
    report_files = sorted(glob.glob(REPORT_PATTERN), key=os.path.getmtime, reverse=True)
    if not report_files:
        return None
    with open(report_files[0], "r", encoding="utf-8") as f:
        return json.load(f)

def get_recommendation_from_report(report):
    items = report.get("items", [])
    if not items:
        return None
    top_id = report.get("top_candidate_id")
    selected = next(
        (item for item in items if item.get("candidate_material", {}).get("candidate_id") == top_id),
        items[0],
    )
    return selected

def create_po_draft(shortage, best):
    po_row = {
        "PO_DRAFT_NO": f"PO-DRAFT-{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "CREATED_AT": datetime.now().isoformat(timespec="seconds"),
        "SOURCE": "Human-approved web research result",
        "VENDOR_NAME": best["VENDOR_NAME"],
        "MATERIAL_ID": best["MATERIAL_ID"],
        "CANDIDATE_ID": best["CANDIDATE_ID"],
        "UNIT_PRICE_KRW": int(best["UNIT_PRICE_KRW"]),
        "ORDER_QTY": shortage["shortage_qty"],
        "TOTAL_AMOUNT_KRW": int(best["UNIT_PRICE_KRW"]) * shortage["shortage_qty"],
        "LEAD_TIME_DAYS": int(best["LEAD_TIME_DAYS"]),
        "SOURCE_URL": best["SOURCE_URL"],
        "FINAL_SCORE": int(best["FINAL_SCORE"]),
        "RISK_NOTE": best["RISK_NOTE"],
    }
    pd.DataFrame([po_row]).to_csv(PO_FILE, index=False)
    st.session_state.po_created = True
    return po_row

def create_po_draft_from_report(shortage, report, selected_item):
    candidate = selected_item["candidate_material"]
    scores = selected_item.get("scores", {})
    decision = selected_item.get("decision_context", {})
    unit_price = int(candidate.get("price_krw") or 0)
    po_row = {
        "PO_DRAFT_NO": f"PO-DRAFT-{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "CREATED_AT": datetime.now().isoformat(timespec="seconds"),
        "SOURCE": "Human-approved Phase 3 evaluation result",
        "VENDOR_NAME": candidate.get("vendor_name"),
        "MATERIAL_ID": shortage["material_id"],
        "CANDIDATE_ID": candidate.get("candidate_id"),
        "UNIT_PRICE_KRW": unit_price,
        "ORDER_QTY": shortage["shortage_qty"],
        "TOTAL_AMOUNT_KRW": unit_price * shortage["shortage_qty"],
        "LEAD_TIME_DAYS": candidate.get("lead_time_days"),
        "SOURCE_URL": candidate.get("source_url"),
        "FINAL_SCORE": scores.get("final_score"),
        "RISK_NOTE": decision.get("recommendation_reason"),
    }
    pd.DataFrame([po_row]).to_csv(PO_FILE, index=False)
    st.session_state.po_created = True
    return po_row

# 5. 하이브리드 투-패널 화면 분할 (대시보드 6.5 : 챗봇 3.5 비율)
col1, col2 = st.columns([6.5, 3.5])

# ==========================================
# 🖥️ [좌측 패널] 웹 대시보드 화면 (PC 모니터용)
# ==========================================
with col1:
    st.title("BuyBee 웹 리서치 기반 대체 자재 대시보드")
    
    # [Step 1] 재고 현황 시각화
    st.subheader("[Step 1] 재고 리스크 모니터링")
    chart_data = df_inv[['MATERIAL_NAME', 'CURRENT_STOCK', 'SAFETY_STOCK']].set_index('MATERIAL_NAME')
    st.bar_chart(chart_data, color=["#FF4B4B", "#0068C9"]) # 빨간색: 현재재고, 파란색: 안전재고
    
    shortage = get_shortage()
    if shortage:
        st.error(f"경고: '{shortage['material_name']}' 재고가 안전 수준 이하입니다. 부족 수량: {shortage['shortage_qty']}개")
    
    st.markdown("---")
    
    # [Step 2 & 3] 웹 검색 후보 검증 및 벤더 비교 (챗봇 진행에 따라 나타남)
    if st.session_state.step >= 2:
        st.subheader("[Step 2 & 3] 웹 검색 후보 검증 및 구매 전략")
        st.markdown("**자동 검증 결과: Rule 기반 스펙 비교 + 출처 신뢰도 평가 + 사용자 2차 검토 대기**")
        report = load_latest_evaluation_report()
        selected_item = get_recommendation_from_report(report) if report else None

        if selected_item:
            candidate = selected_item["candidate_material"]
            target = selected_item["target_material"]
            scores = selected_item["scores"]
            decision = selected_item["decision_context"]

            c1, c2 = st.columns(2)
            c1.info(f"**결품 자재 ({target['material_id']})**\n\n{target['description']}")
            c2.success(f"**웹 검색 후보 ({candidate['candidate_id']}) - {decision['decision']}**\n\n{candidate['spec']}")

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("추천 업체", candidate["vendor_name"])
            m2.metric("최종 점수", f"{scores['final_score']}/100")
            m3.metric("출처 신뢰도", f"{scores['source_trust_score']}/100")
            m4.metric("예상 납기", f"{candidate['lead_time_days']}일")

            rows = []
            for item in report.get("items", []):
                mat = item["candidate_material"]
                item_scores = item["scores"]
                item_decision = item["decision_context"]
                rows.append({
                    "CANDIDATE_ID": mat["candidate_id"],
                    "VENDOR_NAME": mat["vendor_name"],
                    "UNIT_PRICE_KRW": mat["price_krw"],
                    "LEAD_TIME_DAYS": mat["lead_time_days"],
                    "SOURCE_TYPE": mat["source_type"],
                    "FINAL_SCORE": item_scores["final_score"],
                    "DECISION": item_decision["decision"],
                    "RISK_NOTE": item_decision["recommendation_reason"],
                })
            st.markdown("**Phase 3 평가 후보 및 신뢰도 검증표**")
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            st.caption(f"출처 URL: {candidate['source_url']}")
        else:
            target_spec, sub_spec, candidates, best = get_recommendation()

            c1, c2 = st.columns(2)
            c1.info(f"**결품 자재 (MAT-1001)**\n\n{target_spec}")
            c2.success(f"**웹 검색 후보 ({best['MATERIAL_ID']}) - 기술 호환성 {best['TECH_COMPATIBILITY_PERCENT']}%**\n\n{sub_spec}")

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("추천 업체", best["VENDOR_NAME"])
            m2.metric("최종 점수", f"{best['FINAL_SCORE']}/100")
            m3.metric("출처 신뢰도", f"{best['SOURCE_RELIABILITY_SCORE']}/100")
            m4.metric("예상 납기", f"{best['LEAD_TIME_DAYS']}일")

            st.markdown("**웹 검색 후보 및 신뢰도 검증표**")
            st.dataframe(
                candidates[[
                    "CANDIDATE_ID", "VENDOR_NAME", "UNIT_PRICE_KRW", "LEAD_TIME_DAYS",
                    "SOURCE_TYPE", "TECH_COMPATIBILITY_PERCENT", "SOURCE_RELIABILITY_SCORE",
                    "FINAL_SCORE", "VALIDATION_STATUS", "RISK_NOTE"
                ]],
                use_container_width=True,
                hide_index=True,
            )
            st.caption(f"출처 URL: {best['SOURCE_URL']}")

    if st.session_state.po_created and os.path.exists(PO_FILE):
        st.markdown("---")
        st.subheader("[Step 5] PO 초안 생성 결과")
        st.dataframe(pd.read_csv(PO_FILE), use_container_width=True, hide_index=True)


# ==========================================
# 💬 [우측 패널] 메신저 챗봇 UI (모바일 호환)
# ==========================================
with col2:
    st.subheader("AI Personal Assistant")
    st.caption("웹 리서치 결과를 검토하고 승인하는 Human-in-the-loop 창")
    
    # 채팅화면 박스 (고정 높이)
    chat_container = st.container(height=550)
    
    # 이전 대화 내용 그대로 출력
    with chat_container:
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
                
    # 챗봇 입력창
    if prompt := st.chat_input("명령어 입력 (ex. 대체품 찾아줘, 승인할게)"):
        
        # 1. 유저 메시지 기록
        st.session_state.messages.append({"role": "user", "content": prompt})
        with chat_container:
            with st.chat_message("user"):
                st.markdown(prompt)
        
        # 2. AI 응답 로직 (간단한 키워드 매칭으로 시연 최적화)
        with chat_container:
            with st.chat_message("assistant"):
                message_placeholder = st.empty()
                full_response = ""
                
                # 시나리오 트리거
                if "재고" in prompt or "위험" in prompt:
                    st.session_state.step = 1
                    st.session_state.approval_ready = False
                    shortage = get_shortage()
                    full_response = f"현재 **{shortage['material_id']} ({shortage['material_name']})**의 재고가 {shortage['current_stock']}개로 안전재고({shortage['safety_stock']}개)를 밑돌고 있습니다.\n\n자재 스펙을 기반으로 웹에서 대체 후보를 검색하고 출처 신뢰도까지 검증할까요?"
                
                elif "대체" in prompt or "찾아" in prompt or "업체" in prompt or "검색" in prompt:
                    st.session_state.step = 2
                    st.session_state.approval_ready = True
                    shortage = get_shortage()
                    report = load_latest_evaluation_report()
                    selected_item = get_recommendation_from_report(report) if report else None
                    if selected_item:
                        candidate = selected_item["candidate_material"]
                        scores = selected_item["scores"]
                        decision = selected_item["decision_context"]
                        total = int(candidate.get("price_krw") or 0) * shortage["shortage_qty"]
                        full_response = f"왼쪽 대시보드에 Phase 3 평가 결과를 띄웠습니다.\n\n1순위는 **{candidate['vendor_name']}**의 **{candidate['candidate_id']}**입니다. 최종 점수 {scores['final_score']}점, 출처 신뢰도 {scores['source_trust_score']}점, 납기 {candidate['lead_time_days']}일입니다.\n\n예상 발주 금액은 {total:,}원으로 예산 한도({BUDGET_LIMIT_KRW:,}원) 내입니다. 판단: {decision['recommendation_reason']} 최종 승인하시겠습니까?"
                    else:
                        _, _, _, best = get_recommendation()
                        total = int(best["UNIT_PRICE_KRW"]) * shortage["shortage_qty"]
                        full_response = f"왼쪽 대시보드에 웹 검색 후보와 1차 검증 결과를 띄웠습니다.\n\n1순위는 **{best['VENDOR_NAME']}**의 **{best['MATERIAL_ID']}**입니다. 기술 호환성 {best['TECH_COMPATIBILITY_PERCENT']}%, 출처 신뢰도 {best['SOURCE_RELIABILITY_SCORE']}점, 납기 {best['LEAD_TIME_DAYS']}일입니다.\n\n예상 발주 금액은 {total:,}원으로 예산 한도({BUDGET_LIMIT_KRW:,}원) 내입니다. 다만 {best['RISK_NOTE']} 최종 승인하시겠습니까?"
                    # Streamlit 화면 즉시 렌더링을 위해 rerun 효과

                elif "반려" in prompt or "거절" in prompt or "보류" in prompt or "중단" in prompt:
                    st.session_state.step = 2
                    st.session_state.approval_ready = False
                    full_response = "요청을 보류했습니다. PO 초안은 생성하지 않았습니다.\n\n필요하면 검색 조건을 바꿔 다른 후보를 다시 찾겠습니다."
                    
                elif "발주" in prompt or "승인" in prompt or "진행" in prompt or "응" in prompt or "어" in prompt:
                    if not st.session_state.approval_ready:
                        full_response = "아직 승인할 검증 리포트가 없습니다. 먼저 `대체품 찾아줘`라고 입력해 후보와 출처 신뢰도 검증 결과를 확인해주세요."
                    else:
                        st.session_state.step = 3
                        st.session_state.approval_ready = False
                        shortage = get_shortage()
                        report = load_latest_evaluation_report()
                        selected_item = get_recommendation_from_report(report) if report else None
                        if selected_item:
                            po_row = create_po_draft_from_report(shortage, report, selected_item)
                        else:
                            _, _, _, best = get_recommendation()
                            po_row = create_po_draft(shortage, best)
                        full_response = f"**[승인 완료 및 PO 초안 생성]**\n\n사용자 승인에 따라 `{os.path.basename(PO_FILE)}` 파일을 생성했습니다.\n\n전표 초안: {po_row['PO_DRAFT_NO']}\n업체: {po_row['VENDOR_NAME']}\n수량: {po_row['ORDER_QTY']}개\n예상 금액: {po_row['TOTAL_AMOUNT_KRW']:,}원\n\n실제 SAP 전송 전 검토용 Mock 결과물입니다."
                
                else:
                    full_response = "말씀하신 내용을 이해하지 못했습니다. (팁: '재고 확인해줘' -> '대체품 찾아줘' -> '승인할게' 순서로 입력해보세요)"
                
                # 타이핑 애니메이션 효과
                if full_response:
                    displayed_text = ""
                    for chunk in full_response.split():
                        displayed_text += chunk + " "
                        message_placeholder.markdown(displayed_text + "▌")
                        time.sleep(0.04)
                    message_placeholder.markdown(displayed_text)
                    st.session_state.messages.append({"role": "assistant", "content": full_response})
                    
        # Step 2일 경우 대시보드 업데이트를 위해 화면 전체 새로고침
        if st.session_state.step == 2:
            time.sleep(0.5)
            st.rerun()
