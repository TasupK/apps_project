# Phase 3 Demo Log

**Purpose:** Phase 3 CLI 시연용 실행 로그와 결과 요약  
**Scenario:** `MAT-3001` M10 x 50mm SUS304 육각 볼트 부족 상황에서 웹 후보 mock 4개를 평가한다.

## 1. Run Batch Evaluation

```bash
python3 agents/evaluation_agent.py --batch --output output/evaluation_report_batch.json
```

Expected CLI output:

```text
Wrote evaluation report: output/evaluation_report_batch.json
```

## 2. Run Phase 2 Integration Evaluation

```bash
python3 agents/evaluation_agent.py --candidate-results output/candidate_results.fastener.json --output output/evaluation_report_batch.json
```

Expected CLI output:

```text
Wrote evaluation report: output/evaluation_report_batch.json
```

Live search 결과를 평가할 때는 Phase 2가 생성한 `output/candidate_results.json`을 같은 옵션으로 넘긴다.

```bash
python3 agents/evaluation_agent.py --candidate-results output/candidate_results.json --output output/evaluation_report_batch.json
```

## 3. Validate Contract

```bash
python3 -m unittest tests/test_phase3_evaluation.py tests/test_phase3_contract.py
```

Expected test output:

```text
Ran 25 tests
OK
```

## 4. Batch Result Summary

| Field | Value |
|---|---|
| `batch_report_id` | `BER-20260510-160010` |
| `generated_at` | `2026-05-10T16:00:10+09:00` |
| `candidate_count` | `4` |
| `next_action` | `approval_pending` |
| `top_candidate_id` | `WEB-006` |

## 5. Candidate Decisions

| Rank | Candidate | Vendor | Decision | Risk | Final Score | Summary |
|---:|---|---|---|---|---:|---|
| 1 | `WEB-006` | MISUMI Korea | `recommend` | `Low` | 97 | 원본 자재와 후보 자재의 재질이 동일합니다. |
| 2 | `WEB-007` | Daara Precision | `conditional_approve` | `Medium` | 84 | 재질이 SUS304에서 SUS316으로 상향되어 사용 가능성은 있으나 비용과 현장 조건 확인이 필요합니다. |
| 3 | `WEB-008` | Open Market Seller | `review_required` | `High` | 96 | 규격은 유사하지만 출처 신뢰도가 낮아 자동 추천할 수 없습니다. |
| 4 | `WEB-005` | Fastener Tech | `reject` | `High` | 43 | 필수 규격이 일치하지 않아 대체재로 추천하지 않습니다. |

## 6. Explainability Points

- `WEB-006`: 직경, 피치, 길이, 재질이 모두 동일하고 공식 대리점 출처라 최종 추천 후보로 선정된다.
- `WEB-007`: 규격은 맞지만 `SUS304 -> SUS316` 재질 상향이므로 비용과 현장 조건 확인이 필요하다.
- `WEB-008`: 규격은 맞지만 일반 마켓플레이스이며 재고/납기 표시가 없어 사람 검토로 분류된다.
- `WEB-005`: 출처 신뢰도는 높지만 길이 `50mm -> 55mm` 불일치라 자동 반려된다.

## 7. Phase 4 Handoff

Phase 4는 `output/evaluation_report_batch.json`의 `next_action`만 먼저 확인하면 된다.

| `next_action` | Meaning | Phase 4 Action |
|---|---|---|
| `approval_pending` | 승인 요청 가능한 후보가 있음 | `top_candidate_id = WEB-006` 기준으로 사용자 승인 요청 |

Phase 4는 Phase 3 점수를 다시 계산하지 않는다. 승인 메시지에는 `items` 안의 `decision_context`, `scores`, `source_trust_notes`, `spec_analysis.highlighted_differences`를 그대로 사용한다.
