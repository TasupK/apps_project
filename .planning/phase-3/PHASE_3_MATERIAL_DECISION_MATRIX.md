# Phase 3 Material Decision Matrix

**Owner:** Team Member C  
**Status:** MVP template  
**Purpose:** 재질 판단을 AI의 주관적 해석이 아니라 사전 정의된 정책 테이블로 통제한다.

## Important Note

이 문서는 Phase 3가 사용할 재질 판정 구조를 정의한다.  
실제 운영용 최종 값은 Phase 1에서 확인한 회사 재고 DB의 실제 자재군을 기준으로 확정한다.

즉:

- **지금 확정하는 것**: 재질 판정 테이블의 형식과 판정 방식
- **나중에 Phase 1 연동 후 확정하는 것**: 회사가 실제 사용하는 재질 조합 값

## Decision Principle

재질 비교는 다음 순서로 진행한다.

1. `material_group`가 같은지 확인
2. 같은 그룹이면 `material_rank`를 비교
3. 그룹이 다르면 기본적으로 `reject`
4. 동일 등급은 `recommend`
5. 상향 대체는 `conditional_approve`
6. 하향 대체는 `review_required` 또는 `reject`

## Material Group Definition

| Group | Description |
|---|---|
| `stainless` | SUS 계열 스테인리스 |
| `carbon_steel_strength` | 강도등급이 명확한 탄소강 |
| `unknown` | 그룹 분류 불가 |

## Sample Material Master for MVP

이 표는 샘플값이다. 실제 값은 Phase 1 재고 DB 확인 후 갱신한다.

| material_code | material_label | material_group | material_rank | Notes |
|---|---|---|---:|---|
| `SUS304` | SUS304 | `stainless` | 1 | 기준 스테인리스 |
| `SUS316` | SUS316 | `stainless` | 2 | 상향 대체 가능 후보 |
| `4.8` | Steel 4.8 | `carbon_steel_strength` | 1 | 저강도 |
| `8.8` | Steel 8.8 | `carbon_steel_strength` | 2 | 범용 강도 |
| `10.9` | Steel 10.9 | `carbon_steel_strength` | 3 | 고강도 |

## Sample Decision Matrix

| Original | Candidate | Same Group | Rank Direction | Decision | Risk | Rule Reason |
|---|---|---|---|---|---|---|
| `SUS304` | `SUS304` | Yes | Same | `recommend` | `Low` | 동일 재질 |
| `SUS304` | `SUS316` | Yes | Upgrade | `conditional_approve` | `Medium` | 상향 대체, 비용 확인 필요 |
| `SUS316` | `SUS304` | Yes | Downgrade | `review_required` | `Medium` | 내식성 저하 가능성 |
| `8.8` | `10.9` | Yes | Upgrade | `conditional_approve` | `Medium` | 상향 대체 |
| `10.9` | `8.8` | Yes | Downgrade | `reject` | `High` | 강도 저하 |
| `SUS304` | `8.8` | No | N/A | `reject` | `High` | 그룹 불일치 |
| `Unknown` | `Unknown` | No | N/A | `review_required` | `High` | 재질 정보 부족 |

## MVP Rules Reflected in Code

현재 `agents/evaluation_agent.py`는 아래 명시 룰을 먼저 적용한다. 이 표에 없는 조합은 `material_group`과 `material_rank` 기준의 보수적 fallback으로 처리한다.

| Original | Candidate | Decision | Risk | Notes |
|---|---|---|---|---|
| `SUS304` | `SUS304` | `recommend` | `Low` | 동일 재질 |
| `SUS304` | `SUS316` | `conditional_approve` | `Medium` | 상향 대체, 비용/현장 조건 확인 |
| `SUS316` | `SUS304` | `review_required` | `Medium` | 하향 대체, 내식성 검토 |
| `8.8` | `8.8` | `recommend` | `Low` | 동일 강도 등급 |
| `8.8` | `10.9` | `conditional_approve` | `Medium` | 상향 대체, 체결 조건 확인 |
| `10.9` | `8.8` | `reject` | `High` | 강도 하향 |
| `SUS304` | `8.8` | `reject` | `High` | 재질 계열 불일치 |

## Phase 1 Confirmation Checklist

Phase 1이 실제 재고 DB를 확인한 뒤 아래 질문을 확정해야 한다.

| Question | Why It Matters |
|---|---|
| 실제 fastener 재질이 `SUS304`, `SUS316`, `8.8`, `10.9` 외에 더 있는가? | matrix 범위 확장 필요 |
| `SUS304 -> SUS316`을 항상 상향 대체로 볼 수 있는가? | 비용/현장 조건 확인 문구 조정 |
| `SUS316 -> SUS304`를 어떤 조건에서 허용할 수 있는가? | `review_required` 유지 또는 `reject` 변경 |
| 표면처리, 도금, 열처리 정보가 재질 필수 스펙에 포함되는가? | parser와 critical spec 확장 필요 |
| 회사 구매 정책상 특정 재질 하향 대체가 금지되어 있는가? | material rule을 `reject`로 고정 필요 |

## Output Usage

Phase 3는 아래 필드를 계산할 때 이 매트릭스를 참조한다.

- `decision_context.decision`
- `decision_context.risk_level`
- `decision_context.recommendation_reason`
- `decision_context.approval_conditions`
- `decision_context.rejection_reason`

## Handoff Rule

Phase 1에서 실제 자재 DB 분석이 끝나면 아래 두 항목을 업데이트한다.

- `Sample Material Master for MVP`
- `Sample Decision Matrix`
- `MVP Rules Reflected in Code`
- `Phase 1 Confirmation Checklist`

이후에도 문서 형식과 판정 로직 구조는 유지한다.
