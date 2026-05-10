# Phase 2 to Phase 3 Contract

**Producer:** Phase 2 - Web Research Agent  
**Consumer:** Phase 3 - Trust & Evaluation Agent  
**Artifact:** `output/candidate_results.json`

## 계약 요약

Phase 2는 정규화된 후보 자재 근거를 제공한다. Phase 3는 이 산출물을 읽어서 스펙을 파싱하고, 호환성 점수와 출처 신뢰도 점수를 계산한 뒤 `evaluation_report_batch.json`을 만든다.

Phase 2는 후보에 대해 최종 추천 점수를 미리 계산하지 않는다. 점수 계산과 최종 의사결정은 Phase 3가 담당한다.

## 필드 매핑

| Phase 2 Field | Phase 3 Usage |
| --- | --- |
| `material_id` | `target_material.material_id` |
| `material_name` | `target_material.description` |
| `target_spec_text` | Phase 3 target spec parser 입력 |
| `candidates[].candidate_id` | `candidate_material.candidate_id` |
| `candidates[].vendor_name` | `candidate_material.vendor_name` |
| `candidates[].source_url` | `candidate_material.source_url` 및 source trust notes |
| `candidates[].source_type` | `candidate_material.source_type` 및 source trust scoring |
| `candidates[].price_krw` | `candidate_material.price_krw` 및 price scoring |
| `candidates[].lead_time_days` | `candidate_material.lead_time_days` 및 lead-time scoring |
| `candidates[].moq` | `candidate_material.moq` 및 MOQ scoring |
| `candidates[].spec_text` | Phase 3 candidate spec parser 입력 |
| `candidates[].spec_evidence` | source trust notes 및 review explanation |
| `candidates[].price_listed` | `source_trust_breakdown.price_visible` |
| `candidates[].stock_listed` | `source_trust_breakdown.stock_visible` |
| `candidates[].leadtime_listed` | `source_trust_breakdown.leadtime_visible` |

## 중요한 결정 사항

- root `material_id`는 항상 Phase 1에서 감지한 원본 부족 자재 ID다.
- 후보 자재의 내부 material ID가 있을 경우 root `material_id`에 넣지 않고 `candidate_material_id`에 저장한다.
- Phase 2는 `spec_text`와 `spec_evidence`를 텍스트로 전달한다. 이 문자열을 구조화된 `spec` 객체로 파싱하는 책임은 Phase 3에 있다.
- URL을 확보하지 못한 경우 `source_url`은 `null`일 수 있다. Phase 3는 이를 약한 출처 근거로 취급한다.
- 출처에 가격, 납기, MOQ가 명시되지 않은 경우 `price_krw`, `lead_time_days`, `moq`는 `null`일 수 있다. 누락값을 어떻게 감점할지는 Phase 3가 결정한다.
- 현재 Phase 3 fastener MVP 연동을 위해 Phase 2는 `.planning/phase-2/fastener_shortage_event.sample.json`과 `.planning/phase-2/candidate_results.fastener.sample.json`을 제공한다. 이 샘플은 `MAT-3001`과 `WEB-005`부터 `WEB-008`까지의 후보를 사용해서 Phase 3가 별도 입력을 새로 만들지 않고도 실제 파싱과 의사결정 흐름을 검증할 수 있게 한다.
- LLM을 사용하는 경우에도 최종 출력 필드명, enum, `null` 처리 규칙은 이 계약을 따라야 한다.

## 필수 후보 필드

Phase 3로 전달되는 모든 후보는 아래 필드를 포함해야 한다.

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

## 인수인계 체크리스트

- `candidate_results.json`이 존재한다.
- MVP happy path 기준 최소 2개 이상의 후보가 존재한다.
- `source_type` 값은 Phase 3가 기대하는 snake_case enum이다.
- root `material_id`가 후보 자재 ID로 바뀌지 않았다.
- 누락값은 빈 문자열이나 임의의 0이 아니라 `null`을 사용한다.
- boolean 값은 문자열이 아니라 실제 JSON boolean이다.
- fastener 연동 샘플은 candidate ID와 source type enum을 바꾸지 않고 Phase 3에서 평가할 수 있다.
- LLM이 생성한 검색 쿼리나 추출 결과를 사용하더라도 Phase 2 contract test가 통과해야 한다.

## Live Search 환경변수

실제 키가 들어가는 `.env` 파일은 각자 로컬에만 둔다. Git에는 올리지 않는다.

공유용 예시는 repo root의 `.env.example`을 사용한다.

```env
PHASE2_SEARCH_PROVIDER=serpapi
SERPAPI_API_KEY=
OPENAI_API_KEY=
```

PowerShell에서 일시적으로 설정할 경우:

```powershell
$env:PHASE2_SEARCH_PROVIDER="serpapi"
$env:SERPAPI_API_KEY="..."
$env:OPENAI_API_KEY="..."
```

SerpAPI 기반 live search 실행 예시:

```powershell
python agents\web_research_agent.py --sample-input --search-mode live --search-provider serpapi --query-mode llm --extraction-mode llm --max-candidates 5 --output output\candidate_results.json
```
