# Phase 2 Known Limits

## MVP Limits

- Live web search is optional for the MVP. Mock candidate data must remain available for demos and tests.
- Phase 2 does not guarantee that a candidate is technically compatible. It only preserves searchable specs and evidence for Phase 3.
- Phase 2 does not calculate final scores, risk levels, approval conditions, or rejection reasons.
- Phase 2 does not create PO drafts or workflow states.
- `spec_text` may be semi-structured text. Phase 3 owns strict spec parsing.
- `source_url` may be `null` for cache-only or incomplete mock records.
- Prices are treated as unit prices in KRW when listed. Currency conversion is out of scope for the MVP.
- Stock quantity extraction is out of scope. Phase 2 only records whether stock was listed.

## Recommended Implementation Order

1. Create `.planning/phase-2/shortage_event.sample.json` from the Phase 1 contract.
2. Create `.planning/phase-2/mock_candidates.csv` for the Phase 2-owned mock cache.
3. Implement `agents/web_research_agent.py` with mock mode first.
4. Generate `output/candidate_results.json`.
5. Add contract tests for required fields, enum normalization, null handling, and root/candidate material ID separation.
