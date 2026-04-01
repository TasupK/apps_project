# Roadmap: BuyBee

**Created:** 2026-04-01
**Strategy:** Happy Path 관통 최우선 — 예외 처리보다 핵심 파이프라인 동작 증명

## Milestone 1: PoC 완성 (6주)

### Phase 1: 뼈대 세우기 — Data Layer & Monitor Agent
*주차: 1~2주차 | 담당: 팀원 A*

**Goal:** Mock ERP DB 세팅 및 재고 알람 연동 — AI 파이프라인의 감각 기관 구축

**Plans:**
1. **Mock ERP DB 설계 및 구축**
   - SQLite + Pydantic으로 MARA, MARD, MARC 테이블 생성
   - Mock 자재 데이터 시딩 (부품 10종 이상)
   - 가용재고/안전재고 필드 설정

2. **부품 스펙 문서 벡터화 (RAG 준비)**
   - LlamaIndex로 사내 부품 스펙 PDF/텍스트 인덱싱
   - 벡터 스토어 생성 및 기본 검색 테스트

3. **Monitor Agent 구현**
   - 순수 Python Rule-based 재고 스캔 로직
   - 가용재고 < 안전재고 감지 시 이벤트 발생
   - 자재코드 + 파트넘버 State 객체 생성

**Deliverables:**
- `db/mock_erp.py` — SQLite Mock DB 초기화 스크립트
- `db/models.py` — Pydantic 스키마 (MARA, MARD, MARC)
- `db/seed_data.py` — Mock 자재 데이터
- `rag/indexer.py` — LlamaIndex 벡터 인덱스 생성
- `agents/monitor_agent.py` — Monitor Agent
- `tests/test_monitor.py` — 결품 감지 단위 테스트

**Requirements covered:** DATA-01~05, MON-01~04

---

### Phase 2: 손발 — Search Agent & 조달청 API
*주차: 2~3주차 | 담당: 팀원 B*

**Goal:** 조달청 API 데이터 수집 파이프라인 구축 및 Self-Correction 구현

**Plans:**
1. **조달청 API 연동 (또는 Mock)**
   - 조달청 API 클라이언트 구현 (또는 샘플 응답 Mock)
   - 파트넘버 기반 부품 검색 요청/응답 처리

2. **Search Agent 구현**
   - GPT-4o-mini로 API 응답에서 핵심 스펙 추출
   - 후보군 JSON 파싱 및 정규화
   - Self-Correction: 후보 없을 시 검색어 변형 후 재시도 (최대 2회)

3. **LangGraph State 설계**
   - AgentState 공유 객체 정의
   - Monitor → Search State 전달 연결

**Deliverables:**
- `tools/procurement_api.py` — 조달청 API 클라이언트
- `agents/search_agent.py` — Search Agent (GPT-4o-mini)
- `graph/state.py` — LangGraph AgentState 정의
- `tests/test_search.py` — 검색 및 재시도 로직 테스트

**Requirements covered:** SRCH-01~05, ORCH-01 (부분)

---

### Phase 3: 두뇌 — Evaluation Agent & Reporting Agent
*주차: 3~4주차 | 담당: 팀원 C*

**Goal:** 핵심 AI 스펙 매칭 엔진 구현 — 스펙 교차 검증 및 리포트 생성

**Plans:**
1. **Evaluation Agent 구현**
   - LlamaIndex RAG로 원본 자재 스펙 추출
   - 조달청 후보 부품과 1:1 스펙 비교 프롬프트 설계
   - 단위 변환기 Tool 구현 (mm ↔ inch 등)
   - 호환 점수(0-100) 산출 로직
   - Hallucination 제어: 환각 발생률 < 5% 목표

2. **Reporting Agent 구현**
   - JsonOutputParser 기반 엄격한 출력 포맷 강제
   - 스펙 비교표 + 호환 점수 + 추천 사유 JSON 구조 설계

3. **Safety Gate 구현**
   - 호환 점수 80점 미만 시 "대안 없음" 알림 로직
   - 인간 개입 요청 State 업데이트

**Deliverables:**
- `tools/unit_converter.py` — 단위 변환기 Tool
- `agents/evaluation_agent.py` — Evaluation Agent (GPT-4o + RAG)
- `agents/reporting_agent.py` — Reporting Agent (JsonOutputParser)
- `tests/test_evaluation.py` — 스펙 매칭 정확도 테스트
- `tests/test_reporting.py` — JSON 포맷 검증 테스트

**Requirements covered:** EVAL-01~06, RPT-01~03

---

### Phase 4: 연결 — LangGraph 전체 파이프라인 통합
*주차: 4~5주차 | 담당: 팀원 D*

**Goal:** 4개 Agent를 단일 LangGraph 워크플로우로 통합 — 조건부 라우팅 및 Human-in-the-Loop

**Plans:**
1. **LangGraph 그래프 구성**
   - 4개 Node 연결: Monitor → Search → Evaluation → Reporting
   - 조건부 엣지: Search 결과 유무 라우팅
   - 조건부 엣지: Evaluation 점수 기반 라우팅 (80점 이상/미만)
   - Cyclic 라우팅: Search 재시도 Feedback Loop

2. **Human-in-the-Loop 구현**
   - Evaluation 통과 후 워크플로우 일시 정지
   - 담당자 승인/반려 State 처리
   - 반려 시 Search Agent 재실행 피드백

3. **End-to-End 파이프라인 테스트**
   - Happy Path 시나리오 전체 관통 테스트
   - 각 조건부 라우팅 케이스 검증

**Deliverables:**
- `graph/workflow.py` — LangGraph 전체 워크플로우
- `graph/nodes.py` — 각 Agent를 Node로 래핑
- `graph/edges.py` — 조건부 라우팅 엣지 함수
- `tests/test_pipeline.py` — End-to-End 파이프라인 테스트

**Requirements covered:** ORCH-01~05

---

### Phase 5: 화면 — Streamlit UI 대시보드 완성
*주차: 5~6주차 | 담당: 팀원 A+D*

**Goal:** 데모 대시보드 완성 및 최종 시나리오 리허설

**Plans:**
1. **Streamlit UI 구현**
   - 재고 시뮬레이션 버튼 (가용재고 조작)
   - 결품 감지 알림 팝업
   - 워크플로우 단계별 진행 상태 표시

2. **AI 리포트 렌더링**
   - JSON 리포트를 시각적 스펙 비교표로 렌더링
   - 호환 점수 시각화
   - 담당자 승인/반려 버튼

3. **데모 시나리오 리허설**
   - Happy Path 전체 시나리오 데모 준비
   - KPI 검증: 스펙 매칭 정확도 80%+, 환각 < 5%, 속도 5배

**Deliverables:**
- `ui/app.py` — Streamlit 메인 앱
- `ui/components/` — 리포트 렌더링 컴포넌트
- `demo/scenario.md` — 데모 시나리오 스크립트
- `README.md` — 프로젝트 실행 가이드

**Requirements covered:** UI-01~05

---

## Phase Summary

| Phase | Name | 주차 | 담당 | Requirements |
|-------|------|------|------|-------------|
| 1 | Data Layer & Monitor Agent | 1~2주 | 팀원 A | DATA-01~05, MON-01~04 |
| 2 | Search Agent | 2~3주 | 팀원 B | SRCH-01~05 |
| 3 | Evaluation & Reporting Agent | 3~4주 | 팀원 C | EVAL-01~06, RPT-01~03 |
| 4 | LangGraph 파이프라인 통합 | 4~5주 | 팀원 D | ORCH-01~05 |
| 5 | Streamlit UI & 데모 | 5~6주 | 팀원 A+D | UI-01~05 |

## Tech Stack

```
Orchestration   : LangChain / LangGraph
Vector DB (RAG) : LlamaIndex
LLM             : OpenAI GPT-4o (Evaluation) + GPT-4o-mini (Search)
Mock DB         : SQLite + Pydantic
UI              : Streamlit
Language        : Python 3.11+
```

---
*Roadmap created: 2026-04-01*
*Last updated: 2026-04-01 after initialization*
