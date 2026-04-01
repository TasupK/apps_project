# BuyBee

## What This Is

BuyBee는 **Agent AI 기반 전략적 구매 시스템**의 PoC(Proof of Concept)다. 재고 부족 시 AI가 스스로 상황을 파악하고 사내 ERP(SAP Mock DB)를 모니터링하여 대체 부품을 자율적으로 탐색·평가·보고하는 시스템이다. 구매 담당자를 '단순 검색 기계'에서 '전략 기획자'로 전환하는 것이 목표다.

## Core Value

**재고 부족 이벤트 발생 시, 담당자의 개입 없이 AI가 대체 부품 후보와 스펙 비교 리포트를 자동 생성한다.**

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] **Monitor Agent**: Mock ERP DB(SQLite)를 주기적으로 스캔하여 가용재고 < 안전재고 조건 감지 및 이벤트 발생
- [ ] **Search Agent**: 조달청 API를 호출하여 파트넘버 기반 대체 부품 후보군 수집 및 JSON 파싱 (GPT-4o-mini)
- [ ] **Evaluation Agent**: LlamaIndex RAG로 사내 부품 스펙 문서를 벡터 검색하여 후보 부품과 1:1 스펙 교차 비교, 호환 점수 산출 (GPT-4o)
- [ ] **Reporting Agent**: 평가 결과를 JsonOutputParser로 정형화된 스펙 비교 리포트 생성
- [ ] **LangGraph Orchestration**: 4개 Agent를 State 공유 파이프라인으로 연결 (조건부 라우팅 포함)
- [ ] **Self-Correction**: Search 결과 없을 시 검색어 변형 후 최대 2회 재시도 (Feedback Loop)
- [ ] **Safety Gate**: 호환 점수 80점 미만 시 "대안 없음 알림" 및 인간 개입 요청
- [ ] **Human-in-the-Loop**: 담당자가 AI 리포트 검토 후 승인/반려 선택 (Approval Gate)
- [ ] **Mock ERP DB**: SAP S/4HANA 구조 미러링 (MARA 자재마스터, MARD 재고, MARC 테이블) — SQLite + Pydantic
- [ ] **Streamlit UI**: 재고 시뮬레이션 버튼, 알림 팝업, AI 스펙 비교 리포트 대시보드

### Out of Scope

- 실제 SAP S/4HANA 서버 연동 — PoC 단계, 리스크 배제를 위해 Mock DB로만 테스트
- 완전 자율 발주 (ERP 자동 발주) — 인간 최종 승인 필수 (안전성 원칙)
- 복잡한 예외 처리 및 에러 핸들링 — Happy Path 완성 최우선
- 모바일 UI — Streamlit 웹 대시보드만 구현

## Context

- **프로젝트 유형**: 6주 초단기 스프린트 PoC (Agent AI 연구회)
- **개발 전략**: GSD (Get Sh*t Done) & Vibe Coding — 핵심 기능(Happy Path) 완성 최우선
- **현재 문제**: ERP는 재고 알람만 제공, 대체 부품 탐색은 수동 (PDF 대조, 검색 포털 한계)
- **팀 구성**: 팀원별로 Phase를 분담하여 병렬 개발
- **KPI**: 스펙 매칭 정확도 80%+, 환각 발생률 < 5%, 업무 처리 속도 5배 향상

## Constraints

- **Timeline**: 6주 스프린트 — 완벽함보다 동작하는 PoC 우선
- **Tech Stack**: Python, LangChain/LangGraph, LlamaIndex, OpenAI GPT-4o & 4o-mini, SQLite, Pydantic, Streamlit
- **LLM 비용**: Monitor Agent는 순수 Python Rule-based ($0), Search는 GPT-4o-mini, Evaluation만 GPT-4o 사용
- **안전성**: 실제 ERP 미연동, 인간 Approval Gate 필수
- **단위 일관성**: Evaluation Agent에 단위 변환기 도구 제공 (mm/inch 혼용 문제 해결)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| LangGraph 사용 (LangChain 대신) | 멀티 에이전트 State 공유, 조건부 라우팅(Cyclic), Human-in-the-Loop 지원 | — Pending |
| LLM 이원화 (GPT-4o + 4o-mini) | 비용 최적화: 감시/탐색은 저렴한 모델, 핵심 추론만 고성능 모델 | — Pending |
| Mock DB (SQLite + Pydantic) | SAP 실서버 리스크 없이 독립 테스트 환경 구축 | — Pending |
| LlamaIndex RAG | 사내 PDF 부품 스펙 문서의 의미론적(Semantic) 검색 | — Pending |
| Streamlit UI | 빠른 대시보드 프로토타이핑, 6주 스프린트에 적합 | — Pending |
| Human-in-the-Loop 필수 | AI 100% 자율 발주의 책임 소재 및 대형 사고 위험 방지 | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd:transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-01 after initialization*
