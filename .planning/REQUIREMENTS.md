# Requirements: BuyBee

**Defined:** 2026-04-01
**Core Value:** 재고 부족 이벤트 발생 시, 담당자의 개입 없이 AI가 대체 부품 후보와 스펙 비교 리포트를 자동 생성한다.

## v1 Requirements (PoC — 6주 스프린트)

### Data Layer (Mock ERP DB)

- [ ] **DATA-01**: SAP MARA(자재마스터) 구조를 미러링한 SQLite 테이블 생성
- [ ] **DATA-02**: SAP MARD(재고) 구조를 미러링한 SQLite 테이블 생성 (가용재고, 안전재고 포함)
- [ ] **DATA-03**: SAP MARC(플랜트 데이터) 구조를 미러링한 SQLite 테이블 생성
- [ ] **DATA-04**: Pydantic 모델로 DB 스키마 검증 및 Mock 데이터 시딩
- [ ] **DATA-05**: 사내 부품 스펙 문서(PDF/텍스트)를 LlamaIndex로 벡터화하여 인덱스 생성

### Monitor Agent

- [ ] **MON-01**: Mock ERP DB를 주기적으로 스캔하여 가용재고 < 안전재고 조건 감지
- [ ] **MON-02**: 결품 조건 충족 시 자재코드 및 파트넘버를 담은 이벤트(Event) 발생
- [ ] **MON-03**: 순수 Python Rule-based 로직으로 구현 (LLM 호출 없음, $0 비용)
- [ ] **MON-04**: UI에서 재고 수동 조작(시뮬레이션) 시 즉시 트리거 발동

### Search Agent

- [ ] **SRCH-01**: Monitor Agent에서 자재코드/파트넘버를 State로 전달받아 조달청 API 호출
- [ ] **SRCH-02**: 조달청 API 응답에서 대체 부품 후보군 JSON 파싱
- [ ] **SRCH-03**: GPT-4o-mini로 핵심 스펙만 추출하여 노이즈 제거
- [ ] **SRCH-04**: 후보군 없을 시 검색어 변형 후 최대 2회 재시도 (Self-Correction)
- [ ] **SRCH-05**: 2회 재시도 후에도 후보 없으면 Evaluation Agent로 빈 결과 전달

### Evaluation Agent

- [ ] **EVAL-01**: LlamaIndex RAG로 사내 부품 스펙 문서에서 원본 자재 스펙 추출
- [ ] **EVAL-02**: 조달청 후보 부품과 원본 자재를 1:1 스펙 교차 비교
- [ ] **EVAL-03**: 호환 점수(0-100) 산출 및 대체 가능 여부 판단
- [ ] **EVAL-04**: mm/inch 등 단위 혼용 문제 해결을 위한 단위 변환기 도구 사용
- [ ] **EVAL-05**: 호환 점수 80점 미만 시 프로세스 중단, 담당자에게 "대안 없음" 알림
- [ ] **EVAL-06**: GPT-4o 사용 (프로젝트 핵심 추론 엔진)

### Reporting Agent

- [ ] **RPT-01**: Evaluation 결과를 JsonOutputParser로 정형화된 JSON 리포트 생성
- [ ] **RPT-02**: 스펙 비교표, 호환 점수, 추천 사유를 포함한 구조화된 리포트
- [ ] **RPT-03**: UI 렌더링 오류 없도록 엄격한 JSON 서식 강제 (Parsing)

### LangGraph Orchestration

- [ ] **ORCH-01**: LangGraph로 4개 Agent 파이프라인 연결 (State 공유)
- [ ] **ORCH-02**: Search → 후보군 유무 조건부 라우팅 구현
- [ ] **ORCH-03**: Evaluation → 점수 기반 조건부 라우팅 (80점 이상/미만)
- [ ] **ORCH-04**: Search Agent 재시도 Feedback Loop (최대 2회 Cyclic)
- [ ] **ORCH-05**: Human-in-the-Loop: 담당자 승인/반려 전 워크플로우 일시 정지

### UI (Streamlit)

- [ ] **UI-01**: 재고 시뮬레이션 버튼 (가용재고를 안전재고 이하로 조작)
- [ ] **UI-02**: 결품 감지 시 알림 팝업 표시
- [ ] **UI-03**: AI 스펙 비교 리포트 JSON 렌더링 대시보드
- [ ] **UI-04**: 담당자 승인/반려 Action 버튼 (Human-in-the-Loop UI)
- [ ] **UI-05**: 워크플로우 단계별 진행 상태 표시

## v2 Requirements (PoC 이후 확장)

### 실제 SAP 연동

- **SAP-01**: SAP S/4HANA RFC/BAPI 실서버 연동
- **SAP-02**: 승인 시 실제 ERP 발주 자동 생성

### 고도화

- **ADV-01**: 멀티 조달처 비교 (조달청 외 추가 소싱 채널)
- **ADV-02**: 과거 납기 이력 및 벤더 평가 점수 반영
- **ADV-03**: 이메일/Slack 알림 연동

## Out of Scope

| Feature | Reason |
|---------|--------|
| 실제 SAP S/4HANA 연동 | PoC 단계, 실서버 리스크 배제 |
| 완전 자율 발주 | 인간 최종 승인 필수 (안전성 원칙) |
| 복잡한 에러 핸들링 | Happy Path 완성 최우선 |
| 모바일 UI | Streamlit 웹 대시보드만 구현 |
| 실시간 조달청 API 연동 | PoC는 Mock API 또는 샘플 응답 사용 가능 |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| DATA-01 ~ DATA-05 | Phase 1 | Pending |
| MON-01 ~ MON-04 | Phase 1 | Pending |
| SRCH-01 ~ SRCH-05 | Phase 2 | Pending |
| EVAL-01 ~ EVAL-06 | Phase 3 | Pending |
| RPT-01 ~ RPT-03 | Phase 3 | Pending |
| ORCH-01 ~ ORCH-05 | Phase 4 | Pending |
| UI-01 ~ UI-05 | Phase 5 | Pending |

**Coverage:**
- v1 requirements: 30 total
- Mapped to phases: 30
- Unmapped: 0 ✓

---
*Requirements defined: 2026-04-01*
*Last updated: 2026-04-01 after initial definition*
