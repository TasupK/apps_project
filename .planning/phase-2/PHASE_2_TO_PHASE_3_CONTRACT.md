# Phase 2 to Phase 3 Contract

**Producer:** Phase 2 - Web Research Agent  
**Consumer:** Phase 3 - Trust & Evaluation Agent  
**Artifact:** `output/candidate_results.json`

## Contract Summary

Phase 2 provides normalized candidate evidence. Phase 3 consumes this artifact to parse specs, score compatibility, score source trust, and produce `evaluation_report_batch.json`.

Phase 2 must not pre-score candidates for final recommendation. Phase 3 owns scoring and decision logic.

## Field Mapping

| Phase 2 Field | Phase 3 Usage |
| --- | --- |
| `material_id` | `target_material.material_id` |
| `material_name` | `target_material.description` |
| `target_spec_text` | input for Phase 3 target spec parser |
| `candidates[].candidate_id` | `candidate_material.candidate_id` |
| `candidates[].vendor_name` | `candidate_material.vendor_name` |
| `candidates[].source_url` | `candidate_material.source_url` and source trust notes |
| `candidates[].source_type` | `candidate_material.source_type` and source trust scoring |
| `candidates[].price_krw` | `candidate_material.price_krw` and price scoring |
| `candidates[].lead_time_days` | `candidate_material.lead_time_days` and lead-time scoring |
| `candidates[].moq` | `candidate_material.moq` and MOQ scoring |
| `candidates[].spec_text` | input for Phase 3 candidate spec parser |
| `candidates[].spec_evidence` | source trust notes and review explanation |
| `candidates[].price_listed` | `source_trust_breakdown.price_visible` |
| `candidates[].stock_listed` | `source_trust_breakdown.stock_visible` |
| `candidates[].leadtime_listed` | `source_trust_breakdown.leadtime_visible` |

## Important Decisions

- Root `material_id` is always the original shortage material from Phase 1.
- Candidate internal material IDs, if available, must be stored as `candidate_material_id`.
- Phase 2 sends `spec_text` and `spec_evidence` as text. Phase 3 owns parsing those strings into structured `spec` objects.
- `source_url` may be `null` when no URL is available. Phase 3 should treat that as weak source evidence.
- `price_krw`, `lead_time_days`, and `moq` may be `null` when the source does not list them. Phase 3 decides how to penalize missing values.
- For the current Phase 3 fastener MVP, Phase 2 provides `.planning/phase-2/fastener_shortage_event.sample.json` and `.planning/phase-2/candidate_results.fastener.sample.json`. These samples use `MAT-3001` and candidates `WEB-005` through `WEB-008` so Phase 3 can validate real parsing and decision behavior without inventing its own Phase 2 input.

## Required Candidate Fields

Every candidate passed to Phase 3 must include:

- `candidate_id`
- `candidate_material_id`
- `vendor_name`
- `source_url`
- `source_type`
- `price_krw`
- `min_price_krw`
- `lead_time_days`
- `moq`
- `price_listed`
- `stock_listed`
- `leadtime_listed`
- `spec_text`
- `spec_evidence`

## Handoff Checklist

- `candidate_results.json` exists.
- At least two candidates are present for the MVP happy path.
- `source_type` values are Phase 3 snake_case enums.
- Root `material_id` has not been replaced by a candidate material ID.
- Missing values use `null`.
- Booleans are real JSON booleans, not strings.
- Fastener interop sample can be evaluated by Phase 3 without changing candidate IDs or source type enums.
