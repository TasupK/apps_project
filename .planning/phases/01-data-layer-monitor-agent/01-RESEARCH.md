<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Mock ERP 데이터 적재 방식: 기존 CSV 파싱이 배제하고, 리스트 형태 더미 데이터로 하드코딩 시딩한다.
- DB 접근 패턴: SQLAlchemy 배제. 순수 `sqlite3` + `Pydantic` 변환 조합 사용.
- RAG용 사내 스펙 문서: 복잡한 PDF 파서 배제. 모든 스펙 문서를 마크다운(.md) 포맷으로 작성.

### the agent's Discretion
- Monitor Agent 반환 구조: 향후 LangGraph 통합을 위해 `TypedDict` 등 State 호환 객체 구조 리턴.

### Deferred Ideas (OUT OF SCOPE)
None
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DATA-01 | MARA (자재마스터) SQLite 테이블 생성 | `sqlite3` 스키마 작성 패턴 |
| DATA-02 | MARD (재고) SQLite 테이블 생성 | `sqlite3` 스키마 작성 패턴 |
| DATA-03 | MARC (플랜트) SQLite 테이블 생성 | `sqlite3` 스키마 작성 패턴 |
| DATA-04 | Pydantic 스키마 검증 및 데이터 시딩 | Pydantic v2 모델 검증 패턴 |
| DATA-05 | LlamaIndex 마크다운 문서 벡터화 | LlamaIndex SimpleDirectoryReader 객체 |
| MON-01 | 주기적 스캔 및 가용재고 < 안전재고 감지 | Python schedule 또는 수동 진입점 확인 |
| MON-02 | 이벤트 발생 및 자재 정보 리턴 | TypedDict 설계 |
| MON-03 | 순수 Python Rule-based ($0 비용) | LLM 호출 제외 아키텍처 |
| MON-04 | UI 시뮬레이션을 위한 즉시 트리거 | 함수 형태의 진입점(entrypoint) 제공 |
</phase_requirements>

# Phase 1: data-layer-monitor-agent - Research

**Researched:** 2026-04-01
**Domain:** Local Database (SQLite), Data Validation (Pydantic), Rule-based Monitoring
**Confidence:** HIGH

## Summary

이 단계는 AI 에이전트 파이프라인이 행동할 수 있도록 기반 환경을 구축하는 과정입니다. SQLite와 Pydantic을 조합하여 가볍고 의존성 낮은 데이터 계층을 만들고, 상태 관리에 용이한 Monitor Agent를 구현합니다.

**Primary recommendation:** `sqlite3` 커서의 `row_factory`를 `sqlite3.Row`로 설정하여 쿼리 결과를 딕셔너리 형태로 받은 뒤 즉시 Pydantic 모델로 변환(Parsing)하는 패턴을 사용하십시오.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `sqlite3` | Built-in | Mock ERP DB | Python 기본 내장, 추가 종속성 없음, 단일 파일 배포 용이 |
| `pydantic` | 2.x | Data validation | 타입 힌트 기반의 강력하고 빠른 런타임 검증을 제공하며 LangChain/LangGraph와 호환성 우수 |
| `typing_extensions` | 역호환성 | TypedDict 정의 | LangGraph State 객체 정의 시 표준화된 방식 제공 |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `llama-index-core` | 최신 | RAG 기초 설정 | RAG 인덱스를 초기화하고 문서 객체를 다룰 때 |
| `llama-index-readers-file` | 최신 | Markdown 파싱 | 로컬 `.md` 문서들을 LlamaIndex 노드로 로드할 때 |

## Architecture Patterns

### Recommended Project Structure
```text
db/
├── make_db.py       # DB 및 테이블 생성, 데이터 시딩 스크립트
├── models.py        # Pydantic 모델 분리 (MARA, MARD, MARC)
├── seed_data.py     # 하드코딩된 더미 자재 데이터 리스트
└── client.py        # (선택적) sqlite3 연결 인터페이스 도우미
agents/
├── monitor_agent.py # 재고 감시 및 State 반환 로직 탑재
tests/
└── test_monitor.py  # 단위 테스트
```

### Pattern 1: SQLite to Pydantic
**What:** `sqlite3` 행 데이터를 Pydantic 데이터 클래스로 직렬화하는 패턴
**When to use:** DB에서 정보를 가져올 때마다 항상 검증된 객체 상태로 다루고 싶을 때
**Example:**
```python
import sqlite3
from typing import List
from db.models import MARDModel

def get_low_stock_items(db_path: str) -> List[MARDModel]:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM mard WHERE available_stock < safety_stock")
        rows = cur.fetchall()
        return [MARDModel(**dict(row)) for row in rows]
```

### Anti-Patterns to Avoid
- **In-memory DB 남용:** `sqlite3.connect(':memory:')`는 스크립트 단위의 1회성 테스트에만 유용하며, Streamlit UI나 여러 Agent가 상태를 공유하는 본 프로젝트에는 파일 기반(`.db`) 형식 사용 필수.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| 타입 검증 로직 | 수동 `if/else` 및 `try/except` 블록 | `Pydantic` | Pydantic은 필드별 에러 트래킹 기능이 내장되어 있어 훨씬 견고함 |
| 문서 청킹 | 억지 텍스트 분리 구문 작성 (split) | LlamaIndex `MarkdownNodeParser` | 헤더(`#`) 구조를 이해하고 논리적 단위로 청크 분해 가능 |

## Common Pitfalls

### Pitfall 1: SQLite 외래키 무시 현상
**What goes wrong:** MARD가 MARA의 레코드를 참조하는데 MARA 데이터가 없는 상태에서 INSERT를 시도해도 오류가 발생하지 않음.
**Why it happens:** SQLite는 기본적으로 하위 호환성을 위해 외래키 제약조건(Foreign Key constraints)이 꺼져 있습니다.
**How to avoid:** DB Connect 직후 항상 `conn.execute("PRAGMA foreign_keys = ON;")`을 실행하도록 습관화하세요.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | Core Run | ✓ | 3.11+ | — |
| Pydantic | validation | ✗ | — | `pip install pydantic` 실행 필요 |
| LlamaIndex | RAG Index | ✗ | — | `pip install llama-index` 실행 필요 |

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest |
| Quick run command | `pytest tests/test_monitor.py` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| MON-01 | 가용재고 부족 감지 및 이벤트 리턴 검증 | unit | `pytest tests/test_monitor.py` | ❌ Wave 0 |

## Sources

### Primary (HIGH confidence)
- Python 3 SQLite3 docs — `sqlite3.Row` factory standard.
- Pydantic V2 Documentation — validation syntax.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - `sqlite3` + `pydantic` 조합은 ORM을 배제한 상태에서 가장 권장되는 견고한 아키텍처 모델임.
- Architecture: HIGH - LangGraph State와 호환되는 Dictionaries 또는 Pydantic 반환이 권장됨.

**Research date:** 2026-04-01
**Valid until:** 2026-05-01
