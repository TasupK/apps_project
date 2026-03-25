import streamlit as st
import pandas as pd
import time
import os

# 1. 페이지 설정 (넓은 화면 레이아웃)
st.set_page_config(page_title="SCM Copilot", layout="wide", page_icon="📦")

# 2. 데이터 경로 설정 (미리 만들어둔 mock data 활용)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INV_FILE = os.path.join(BASE_DIR, 'inventory_data.csv')
MAT_FILE = os.path.join(BASE_DIR, 'material_master.csv')
VEN_FILE = os.path.join(BASE_DIR, 'vendor_sourcing.csv')

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
    st.session_state.step = 0 # 0: 대기, 1: 재고 감지, 2: 대체재 탐색, 3: 발주 승인

# 5. 하이브리드 투-패널 화면 분할 (대시보드 6.5 : 챗봇 3.5 비율)
col1, col2 = st.columns([6.5, 3.5])

# ==========================================
# 🖥️ [좌측 패널] 웹 대시보드 화면 (PC 모니터용)
# ==========================================
with col1:
    st.title("📊 SCM 지능형 조달 대시보드")
    
    # [Step 1] 재고 현황 시각화
    st.subheader("[Step 1] 실시간 재고 현황 모니터링")
    chart_data = df_inv[['MATERIAL_NAME', 'CURRENT_STOCK', 'SAFETY_STOCK']].set_index('MATERIAL_NAME')
    st.bar_chart(chart_data, color=["#FF4B4B", "#0068C9"]) # 빨간색: 현재재고, 파란색: 안전재고
    
    shortage = df_inv[df_inv['CURRENT_STOCK'] < df_inv['SAFETY_STOCK']]
    if not shortage.empty:
        st.error(f"⚠️ 경고: '{shortage.iloc[0]['MATERIAL_NAME']}' 의 재고가 안전 수준 이하로 떨어졌습니다!")
    
    st.markdown("---")
    
    # [Step 2 & 3] AI 스펙 분석 및 벤더 비교 (챗봇 진행에 따라 나타남)
    if st.session_state.step >= 2:
        st.subheader("[Step 2 & 3] AI 분석 기반 대체재 및 공급망 비교")
        st.markdown("**🔍 AI 규격 분석 결과 (Vector DB 매칭 완료)**")
        
        target_spec = df_mat[df_mat['MATERIAL_ID'] == 'MAT-1001']['TECHNICAL_SPECIFICATION'].values[0]
        sub_spec = df_mat[df_mat['MATERIAL_ID'] == 'MAT-1002']['TECHNICAL_SPECIFICATION'].values[0]
        
        c1, c2 = st.columns(2)
        c1.info(f"**📌 결품 자재 (MAT-1001)**\n\n{target_spec}")
        c2.success(f"**💡 발견된 대체 자재 (MAT-1002) - 일치도 95%**\n\n{sub_spec}")
        
        st.markdown("**🤝 공급업체 납기 및 단가 비교표**")
        st.dataframe(df_ven, use_container_width=True, hide_index=True)


# ==========================================
# 💬 [우측 패널] 메신저 챗봇 UI (모바일 호환)
# ==========================================
with col2:
    st.subheader("🤖 AI Personal Assistant")
    st.caption("사내 메신저를 통한 승인 워크플로우 대기창")
    
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
                    full_response = "현재 **MAT-1001 (Ball Bearing 6204-ZZ)**의 재고가 10개로 안전재고(50개)를 밑돌고 있습니다.\n\nERP 마스터 데이터를 뒤져 다른 제조사의 호환 가능한 대체재를 검색할까요?"
                
                elif "대체" in prompt or "찾아" in prompt or "업체" in prompt or "검색" in prompt:
                    st.session_state.step = 2
                    full_response = "왼쪽 대시보드에 95% 일치하는 **대체재(MAT-1002)** 스펙과 비교표를 띄웠습니다.\n\n비교 분석 결과, **'Seoul Bearings Co.'**가 15,000원으로 단가는 조금 높지만 당일 도착(납기 1일)이 가능하여 긴급 조달 1순위로 추천합니다.\n\n총 75만 원으로 해당 부서의 소모품 예산 한도(500만 원) 내입니다. 이대로 발주를 진행할까요?"
                    # Streamlit 화면 즉시 렌더링을 위해 rerun 효과
                    
                elif "발주" in prompt or "승인" in prompt or "진행" in prompt or "응" in prompt or "어" in prompt:
                    st.session_state.step = 3
                    full_response = "✅ **[결제 확정 및 ERP 전송 완료]**\n\n승인되었습니다. SAP ERP에 구매 오더(PO #4500019293) 시스템 전표를 발행했습니다. 수고하셨습니다!"
                
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
