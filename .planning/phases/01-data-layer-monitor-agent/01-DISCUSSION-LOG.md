# Phase 1: 뼈대 세우기 — Data Layer & Monitor Agent - Discussion Log
**Date:** 2026-04-01

## Q1: Mock ERP 데이터 적재 방식 (Seeding)
**Presented Options:**
- A) 기존 CSV 파일들을 파싱해서 적재해 주세요. (권장)
- B) 아니요, Python 코드 내부에 리스트 형식의 더미 데이터를 별도로 하드코딩해서 만들어주세요.
**User Selected:** B

## Q2: DB 접근 패턴 (Data Access)
**Presented Options:**
- A) 순수 `sqlite3` 모듈을 사용해 SQL을 실행하고, 쿼리된 결과를 Pydantic 모델로 변환하여 반환 (권장)
- B) SQLAlchemy 같은 ORM이나 쿼리 빌더를 도입
**User Selected:** A

## Q3: RAG용 사내 스펙 문서 데이터 형식
**Presented Options:**
- A) 실제 환경 조건을 반영해 모의 PDF 문서 형태로 구성할 예정입니다.
- B) 개발 및 텍스트 파싱을 간소화하기 위해 마크다운(.md) 포맷으로만 구성할 예정입니다. (권장)
- C) 기타 포맷
**User Selected:** B
