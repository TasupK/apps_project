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

이후에도 문서 형식과 판정 로직 구조는 유지한다.
