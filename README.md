# BuyBee

웹 리서치 기반 대체 자재 탐색 및 발주 초안 생성 PoC입니다.

## 실행

```bash
pip install -r requirements.txt
streamlit run streamlit_hybrid_app.py
```

브라우저에서 표시되는 로컬 주소로 접속하면 Phase 5 대시보드를 확인할 수 있습니다.

## Phase 1-4 파이프라인 실행

오프라인 검증용 실행:

```bash
python run_pipeline.py --search-provider llm_plan
```

실제 웹 검색/LLM 추출 실행:

```bash
cp .env.example .env
# .env에 SERPAPI_API_KEY, 필요 시 OPENAI_API_KEY 설정
python run_pipeline.py --search-provider serpapi --query-mode llm --extraction-mode llm
```

Phase 4 승인 대기 항목을 자동 승인까지 진행하려면:

```bash
python run_pipeline.py --auto-approve
```

`output/`의 실행 결과 JSON은 파이프라인 산출물입니다. 고정 계약 샘플은 `.planning/` 아래 파일을 기준으로 확인합니다.

## 현재 데모 흐름

1. 재고 부족 자재를 감지합니다.
2. 우측 승인 창에 `재고 확인해줘`를 입력해 부족 수량을 확인합니다.
3. `대체품 찾아줘`를 입력해 실제 Phase 2 웹 검색을 실행합니다.
4. 후보별 출처, 가격, 납기, URL, 리스크 근거를 비교합니다.
5. 승인 전에는 PO 초안 생성을 차단합니다.
6. 사용자가 챗봇에서 승인하면 실제 검색 후보 기준으로 `PO_Result.csv` 발주 초안을 생성합니다.

실제 웹 검색 실행에는 `SERPAPI_API_KEY`가 필요합니다. `OPENAI_API_KEY`가 있으면 검색 쿼리 생성과 상세 추출에 LLM을 사용하고, 없으면 결정적 검색어와 검색 결과 스니펫만 사용합니다.

Phase 3 추천/반려 설명과 Phase 5 리포트 기반 질문 응답은 기본적으로 룰 기반 fallback 문장을 사용합니다. LLM 문장 생성을 켜려면 `.env`에 다음 값을 설정합니다.

```bash
BUYBEE_ENABLE_LLM_EXPLANATIONS=true
BUYBEE_ENABLE_LLM_CHAT=true
OPENAI_API_KEY=...
```

## Phase 5 산출물

- `streamlit_hybrid_app.py`: DB 재고 리스크, 실제 검색 후보 비교, 승인 게이트, PO 결과를 보여주는 Streamlit 앱
- `output/candidate_results_<MATERIAL_ID>.json`: 실제 Phase 2 검색 실행 결과
- `output/evaluation_report_batch_<MATERIAL_ID>.json`: Fastener 자재일 때 생성되는 Phase 3 평가 결과
- `PO_Result.csv`: 승인 후 생성되는 Mock PO 초안
- `.planning/phase-5/PHASE_5.md`: 발표 데모 스크립트와 체크리스트

## 주요 변경 방향

- 조달청 API 의존을 제거하고 웹 검색/제조사/공식 판매처 기반 리서치로 전환
- Vector DB 단독 매칭 대신 필수 스펙 Rule 검증과 출처 신뢰도 점수 추가
- Human-in-the-loop 승인 전에는 PO 초안이 생성되지 않도록 통제
- 실제 SAP 연동 표현을 제거하고 PoC 단계에서는 Mock PO 파일 생성으로 한정
