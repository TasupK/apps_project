# Phase 1 Discussion Log: Mock Data Layer & Monitor Agent

**Date:** 2026-05-07

## Areas Discussed

### 1. 추가적인 정규화 필드 (Additional normalization fields)
- **Options:** Precision Class, Material, Seal/Shield Type, Load Rating.
- **Decision:** **Precision Class** and **Material** selected for structured capture.
- **Rationale:** Essential for technical compatibility verification in later phases.

### 2. 동의어 사전 확장성 (Synonym dictionary scalability)
- **Options:** Static Dictionary, AI-on-Demand, Hybrid.
- **Decision:** **Static Dictionary** (Static only).
- **Rationale:** Prioritize predictability and reliability for the PoC scope.

### 3. 검색 키워드 우선순위 (Search keyword priority)
- **Options:** Brand-First, Dimension-First, Hybrid.
- **Decision:** **Dimension-First** (`[Synonym] [Dimensions] [Brand]`).
- **Rationale:** Focus on finding compatible alternatives rather than just the exact same brand/part.

## Deferred Ideas
- Seal/Shield type parsing (Bearing specific).
- AI-based synonym generation.
- Multi-plant stock handling.
