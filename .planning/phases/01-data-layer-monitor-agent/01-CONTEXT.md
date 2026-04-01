# Phase 1: 뼈대 세우기 — Data Layer & Monitor Agent - Context

**Gathered:** 2026-04-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Mock ERP Database(SQLite) 초기화 및 가용재고 기반 결품 조건을 감지하여 이벤트를 발생시키는 Rule-based Monitor Agent 로직 구축. 추가적으로 향후 RAG를 위한 환경 셋팅. (조달청 검색, 스펙 매칭, 파이프라인 통합은 모두 다음 Phase들의 영역임)

</domain>

<decisions>
## Implementation Decisions

### Mock ERP 데이터 적재 방식 (Seeding)
- **D-01:** 프로젝트 내의 기존 CSV(`material_master.csv` 등)를 파싱하지 않는다. 대신, 파이썬 파일 내부에 리스트(List of Dicts) 형태의 잘 정리된 더미 데이터를 깔끔하게 하드코딩하여 SQLite DB에 시딩(Seeding)한다.

### DB 접근 패턴 (Data Access)
- **D-02:** 확장성을 위한 SQLAlchemy 도입 같은 무거운 ORM은 배제한다. 순수 `sqlite3` 모듈을 사용하여 원시 SQL 쿼리를 실행하되, 반환된 데이터를 철저히 `Pydantic` 모델로 변환·검증하여 리턴한다.

### RAG용 사내 스펙 문서 데이터 형식
- **D-03:** 복잡한 PDF 파서를 배제하고, 개발 속도와 텍스트 파싱 효율을 높이기 위해 구동될 사내 스펙 모의 문서는 모두 마크다운(`.md`) 포맷으로 구성하여 LlamaIndex가 읽도록 설계한다.

### the agent's Discretion
- **Monitor Agent 반환 구조 (State):** 명시하지 않으셨으므로 향후 Phase 4 LangGraph 통합을 대비해 결품 이벤트를 발생시킬 때부터 `TypedDict` 등 State 호환용 객체 구조(단순 Dictionary 기반)로 이벤트 데이터를 리턴시키도록 구현합니다.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

No external specs — requirements fully captured in decisions above. (Refer to `PROJECT.md`, `ROADMAP.md` and `REQUIREMENTS.md` for core architecture)

</canonical_refs>

<specifics>
## Specific Ideas

- 하드코딩될 더미 자재 데이터는 요구사항(DATA-04)에 기재된 것처럼 최소 10종 이상을 준비한다.
- SQLite 데이터베이스 파일과 테이블 정의 스키마 모델(`db/models.py`) 분리.

</specifics>

<deferred>
## Deferred Ideas

None — Phase scope clearly bounded.

</deferred>

---

*Phase: 01-data-layer-monitor-agent*
*Context gathered: 2026-04-01*
