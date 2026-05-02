# Requirements: BuyBee

**Defined:** 2026-04-01
**Core Value:** 재고 부족 이벤트 발생 시, AI가 웹 기반 대체 부품 후보와 신뢰도 검증 리포트를 자동 생성하고 담당자의 승인/반려를 요청한다.

## v1 Requirements (PoC — 6주 스프린트)

### Data Layer (Mock Inventory + Web Research Cache)

- [ ] **DATA-01**: 자재 마스터 테이블/CSV 생성 (자재코드, 품명, 기술 스펙 텍스트)
- [ ] **DATA-02**: 재고 스냅샷 테이블/CSV 생성 (현재고, 안전재고, 부족 수량)
- [ ] **DATA-03**: 웹 검색 후보 캐시 생성 (후보 자재, 업체, 가격, 납기, 출처 URL)
- [ ] **DATA-04**: Pydantic 모델로 입력 데이터와 후보 데이터 스키마 검증
- [ ] **DATA-05**: 승인 결과와 PO 초안 이력을 CSV/JSON으로 저장

### Monitor Agent

- [ ] **MON-01**: Mock ERP DB를 주기적으로 스캔하여 가용재고 < 안전재고 조건 감지
- [ ] **MON-02**: 결품 조건 충족 시 자재코드 및 파트넘버를 담은 이벤트(Event) 발생
- [ ] **MON-03**: 순수 Python Rule-based 로직으로 구현 (LLM 호출 없음, $0 비용)
- [ ] **MON-04**: UI에서 재고 수동 조작(시뮬레이션) 시 즉시 트리거 발동

### Web Research Agent

- [ ] **SRCH-01**: 원본 자재 스펙에서 검색 쿼리 생성 (품명, 규격, 치수, 재질, 모델명)
- [ ] **SRCH-02**: 제조사 공식 페이지, 공식 판매처, 산업재몰, 마켓플레이스 결과 수집
- [ ] **SRCH-03**: 검색 결과에서 후보명, 스펙, 가격, 재고, 납기, 출처 URL 추출
- [ ] **SRCH-04**: 후보군 없을 시 검색어 변형 후 최대 2회 재시도 (Self-Correction)
- [ ] **SRCH-05**: 수집 결과를 정규화하여 Evaluation Agent로 전달

### Trust & Evaluation Agent

- [ ] **EVAL-01**: 자재 마스터에서 원본 자재의 필수 스펙 추출
- [ ] **EVAL-02**: 웹 후보 부품과 원본 자재를 1:1 스펙 교차 비교
- [ ] **EVAL-03**: 호환 점수(0-100) 산출 및 대체 가능 여부 판단
- [ ] **EVAL-04**: mm/inch 등 단위 혼용 문제 해결을 위한 단위 변환기 도구 사용
- [ ] **EVAL-05**: 공식 출처 여부, 스펙 증거, 가격/재고/납기 명시 여부로 출처 신뢰도 점수 산출
- [ ] **EVAL-06**: 호환 점수 또는 신뢰도 기준 미달 시 자동 추천 제외 또는 조건부 승인 표시

### Reporting Agent

- [ ] **RPT-01**: Evaluation 결과를 JsonOutputParser로 정형화된 JSON 리포트 생성
- [ ] **RPT-02**: 스펙 비교표, 호환 점수, 출처 신뢰도, 가격/납기, 리스크 메모를 포함한 구조화된 리포트
- [ ] **RPT-03**: UI 렌더링 오류 없도록 엄격한 JSON 서식 강제 (Parsing)

### LangGraph Orchestration

- [ ] **ORCH-01**: LangGraph로 4개 Agent 파이프라인 연결 (State 공유)
- [ ] **ORCH-02**: Web Research → 후보군 유무 조건부 라우팅 구현
- [ ] **ORCH-03**: Evaluation → 호환성/신뢰도 기반 조건부 라우팅
- [ ] **ORCH-04**: Search Agent 재시도 Feedback Loop (최대 2회 Cyclic)
- [ ] **ORCH-05**: Human-in-the-Loop: 담당자 승인/반려 전 워크플로우 일시 정지

### UI (Streamlit)

- [ ] **UI-01**: 재고 시뮬레이션 버튼 (가용재고를 안전재고 이하로 조작)
- [ ] **UI-02**: 결품 감지 시 알림 팝업 표시
- [ ] **UI-03**: 웹 검색 후보, 출처 URL, 신뢰도 점수, 스펙 비교 리포트 렌더링 대시보드
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
| 실시간 조달청 API 연동 | 초기 PoC는 웹 검색 기반으로 전환 |
| AI 단독 자동 발주 | 웹 정보 불확실성 때문에 Human-in-the-loop 승인 필수 |

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
