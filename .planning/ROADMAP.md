# Roadmap: BuyBee

**Created:** 2026-04-01
**Strategy:** Happy Path 관통 최우선 — 예외 처리보다 핵심 파이프라인 동작 증명

## Milestone 1: PoC 완성 (6주)

## Phase Files

- [Phase 1: Mock Data Layer & Monitor Agent](phase-1/PHASE_1.md)
- [Phase 1 Format Contract](phase-1/PHASE_1_FORMAT_CONTRACT.md)
- [Phase 2: Web Research Agent & Source Collection](phase-2/PHASE_2.md)
- [Phase 3: Trust & Evaluation Agent](phase-3/PHASE_3.md)
- [Phase 3 Format Contract](phase-3/PHASE_3_FORMAT_CONTRACT.md)
- [Phase 3 Material Decision Matrix](phase-3/PHASE_3_MATERIAL_DECISION_MATRIX.md)
- [Phase 4: Orchestration & Human-in-the-Loop](phase-4/PHASE_4.md)
- [Phase 5: Streamlit UI & Demo](phase-5/PHASE_5.md)

### Phase 1: 뼈대 세우기 — Mock Data Layer & Monitor Agent
*주차: 1~2주차 | 담당: 팀원 A*

**Goal:** 자재 마스터/재고 스냅샷/웹 후보 캐시 세팅 및 재고 알람 연동

**Plans:**
1. **Mock 데이터 설계 및 구축**
   - CSV 또는 SQLite + Pydantic으로 자재 마스터, 재고 스냅샷, 웹 후보 캐시 구성
   - Mock 자재/후보 데이터 시딩 (부품 10종 이상)
   - 가용재고/안전재고 필드 설정

2. **스펙 추출/검색 쿼리 준비**
   - 자재 마스터의 기술 스펙에서 핵심 키워드 추출
   - 검색 쿼리 템플릿과 필수 스펙 체크리스트 정의

3. **Monitor Agent 구현**
   - 순수 Python Rule-based 재고 스캔 로직
   - 가용재고 < 안전재고 감지 시 이벤트 발생
   - 자재코드 + 파트넘버 State 객체 생성

**Deliverables:**
- `data/` 또는 CSV — Mock 데이터
- `db/models.py` — Pydantic 스키마
- `db/seed_data.py` — Mock 자재 데이터
- `tools/query_builder.py` — 검색 쿼리 생성기
- `agents/monitor_agent.py` — Monitor Agent
- `tests/test_monitor.py` — 결품 감지 단위 테스트

**Requirements covered:** DATA-01~05, MON-01~04

---

### Phase 2: 손발 — Web Research Agent & 신뢰도 수집
*주차: 2~3주차 | 담당: 팀원 B*

**Goal:** 웹 검색 기반 후보 수집 파이프라인과 출처 증거 수집 구현

**Plans:**
1. **웹 검색 후보 수집**
   - 자재 스펙 기반 검색 쿼리 생성
   - 제조사/공식 판매처/산업재몰/마켓플레이스 결과 수집
   - 후보별 출처 URL, 가격, 재고, 납기, 스펙 증거 저장

2. **Search Agent 구현**
   - GPT-4o-mini 또는 규칙 기반 파서로 검색 결과에서 핵심 스펙 추출
   - 후보군 JSON/CSV 파싱 및 정규화
   - Self-Correction: 후보 없을 시 검색어 변형 후 재시도 (최대 2회)

3. **LangGraph State 설계**
   - AgentState 공유 객체 정의
   - Monitor → Search State 전달 연결

**Deliverables:**
- `tools/web_search.py` — 웹 검색/후보 수집 도구
- `tools/source_validator.py` — 출처 신뢰도 평가 도구
- `agents/search_agent.py` — Search Agent (GPT-4o-mini)
- `graph/state.py` — LangGraph AgentState 정의
- `tests/test_search.py` — 검색 및 재시도 로직 테스트

**Requirements covered:** SRCH-01~05, ORCH-01 (부분)

---

### Phase 3: 두뇌 — Trust/Evaluation Agent & Reporting Agent
*주차: 3~4주차 | 담당: 팀원 C*

**Goal:** 핵심 AI 스펙 매칭 엔진 구현 — 스펙 교차 검증 및 리포트 생성

**Plans:**
1. **Evaluation Agent 구현**
   - 자재 마스터에서 원본 자재 스펙 추출
   - 웹 후보 부품과 1:1 스펙 비교 프롬프트 설계
   - 단위 변환기 Tool 구현 (mm ↔ inch 등)
   - 호환 점수와 출처 신뢰도 점수 산출 로직
   - Hallucination 제어: 환각 발생률 < 5% 목표

2. **Reporting Agent 구현**
   - JsonOutputParser 기반 엄격한 출력 포맷 강제
   - 스펙 비교표 + 호환 점수 + 출처 신뢰도 + 추천 사유 JSON 구조 설계

3. **Safety Gate 구현**
   - 호환 점수 또는 출처 신뢰도 기준 미달 시 "검토 필요" 알림 로직
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
| 1 | Mock Data Layer & Monitor Agent | 1~2주 | 팀원 A | DATA-01~05, MON-01~04 |
| 2 | Search Agent | 2~3주 | 팀원 B | SRCH-01~05 |
| 3 | Evaluation & Reporting Agent | 3~4주 | 팀원 C | EVAL-01~06, RPT-01~03 |
| 4 | LangGraph 파이프라인 통합 | 4~5주 | 팀원 D | ORCH-01~05 |
| 5 | Streamlit UI & 데모 | 5~6주 | 팀원 A+D | UI-01~05 |

## Tech Stack

```
Orchestration   : LangChain / LangGraph
Knowledge Base   : 웹 검색 결과 캐시 + 선택적 Vector DB
LLM             : OpenAI GPT-4o (Evaluation) + GPT-4o-mini (Search)
Mock Data       : CSV or SQLite + Pydantic
UI              : Streamlit
Language        : Python 3.11+
```

---
*Roadmap created: 2026-04-01*
*Last updated: 2026-04-01 after initialization*
