# BuyBee

## What This Is

BuyBee는 **Agent AI 기반 전략적 구매 시스템**의 PoC(Proof of Concept)다. 재고 부족 시 AI가 상황을 파악하고, 자재 스펙을 바탕으로 웹 검색/제조사/공식 판매처 페이지에서 대체 부품 후보를 수집한 뒤 신뢰도와 호환성을 평가해 구매 담당자에게 승인 요청을 올리는 시스템이다. 구매 담당자를 '단순 검색 기계'에서 '전략 기획자'로 전환하는 것이 목표다.

## Core Value

**재고 부족 이벤트 발생 시, AI가 웹 기반 대체 부품 후보와 신뢰도 검증 리포트를 자동 생성하고, 담당자는 승인/반려 의사결정에 집중한다.**

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] **Monitor Agent**: Mock 재고 스냅샷을 주기적으로 스캔하여 현재고 < 안전재고 조건 감지 및 이벤트 발생
- [ ] **Web Research Agent**: 검색 쿼리를 생성하고 제조사/공식 판매처/마켓플레이스 페이지에서 후보 부품, 가격, 납기, 출처 URL 수집
- [ ] **Trust & Evaluation Agent**: 필수 스펙 Rule 검증, 출처 신뢰도 점수, 기술 호환 점수, 최종 추천 점수 산출
- [ ] **Reporting Agent**: 평가 결과를 JsonOutputParser로 정형화된 스펙 비교 리포트 생성
- [ ] **LangGraph Orchestration**: 4개 Agent를 State 공유 파이프라인으로 연결 (조건부 라우팅 포함)
- [ ] **Self-Correction**: Search 결과 없을 시 검색어 변형 후 최대 2회 재시도 (Feedback Loop)
- [ ] **Safety Gate**: 호환 점수 또는 출처 신뢰도 기준 미달 시 "검토 필요" 표시 및 자동 추천 차단
- [ ] **Human-in-the-Loop**: 담당자가 AI 리포트 검토 후 승인/반려 선택 (Approval Gate)
- [ ] **Mock Data Layer**: 자재 마스터, 재고 스냅샷, 웹 검색 후보 결과를 CSV/SQLite로 관리
- [ ] **Streamlit UI**: 재고 리스크, 웹 검색 후보, 신뢰도 검증표, 승인/반려 흐름을 보여주는 대시보드

### Out of Scope

- 실제 SAP S/4HANA 서버 연동 — PoC 단계, 리스크 배제를 위해 PO 초안 파일 생성으로 대체
- AI 단독 발주 — 인간 최종 승인 필수 (안전성 원칙)
- 복잡한 예외 처리 및 에러 핸들링 — Happy Path 완성 최우선
- 실제 메신저 앱 연동 — PoC는 Streamlit 내 채팅 UI로 대체

## Context

- **프로젝트 유형**: 6주 초단기 스프린트 PoC (Agent AI 연구회)
- **개발 전략**: GSD (Get Sh*t Done) & Vibe Coding — 핵심 기능(Happy Path) 완성 최우선
- **현재 문제**: 재고 알람 이후 대체 부품 탐색은 수동 (PDF 대조, 검색 포털, 판매처 페이지 확인)
- **팀 구성**: 팀원별로 Phase를 분담하여 병렬 개발
- **KPI**: 스펙 매칭 정확도 80%+, 환각 발생률 < 5%, 업무 처리 속도 5배 향상

## Constraints

- **Timeline**: 6주 스프린트 — 완벽함보다 동작하는 PoC 우선
- **Tech Stack**: Python, LangChain/LangGraph, OpenAI GPT 계열, 웹 검색/크롤링 도구, SQLite 또는 CSV, Pydantic, Streamlit
- **LLM 비용**: Monitor Agent는 순수 Python Rule-based ($0), Search는 GPT-4o-mini, Evaluation만 GPT-4o 사용
- **안전성**: 실제 ERP 미연동, 인간 Approval Gate 필수
- **검증 원칙**: 웹 검색 결과를 그대로 신뢰하지 않고 출처 공식성, 스펙 완전성, 가격/재고/납기 명시 여부를 점수화

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| LangGraph 사용 (LangChain 대신) | 멀티 에이전트 State 공유, 조건부 라우팅(Cyclic), Human-in-the-Loop 지원 | — Pending |
| LLM 이원화 (GPT-4o + 4o-mini) | 비용 최적화: 감시/탐색은 저렴한 모델, 핵심 추론만 고성능 모델 | — Pending |
| Mock Data (CSV/SQLite + Pydantic) | 실서버 리스크 없이 독립 테스트 환경 구축 | — Pending |
| 웹 검색 기반 소싱 | 조달청 API 초기 연동 난도를 낮추고 실제 구매 담당자의 검색 업무를 직접 대체 | — Pending |
| 신뢰도 점수화 | 웹 정보의 불확실성을 공식성/스펙 증거/가격·납기 명시 여부로 통제 | — Pending |
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
