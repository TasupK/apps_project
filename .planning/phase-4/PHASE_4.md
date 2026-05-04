# Phase 4: Orchestration & Human-in-the-Loop

**기간:** 4~5주차  
**담당:** 팀원 D 또는 통합 담당  
**목표:** Monitor, Web Research, Evaluation, Reporting 단계를 하나의 워크플로우로 연결하고 사용자 승인 지점을 구현한다.

## 핵심 역할

Phase 4는 각 팀원이 만든 모듈을 하나의 실행 흐름으로 묶는다. 이 단계의 핵심은 자동화가 아니라 통제된 자동화다. 평가 리포트가 생성된 뒤에는 반드시 사용자 승인 또는 반려 상태를 거쳐야 한다.

Phase 3 입력 계약: [Phase 3 to Phase 4 Contract](../shared/contracts/phase3_to_phase4_contract.md)

## 작업 범위

- 공통 `AgentState` 정의
- Monitor → Web Research 연결
- Web Research → Evaluation 연결
- Evaluation → Reporting 연결
- 후보 없음, 기준 미달, 승인 대기, 반려, 승인 상태 라우팅
- Phase 3의 `evaluation_report_batch.json` 읽기
- `next_action` 기반 승인/검토/후보 없음 라우팅
- 승인 전 워크플로우 일시 정지
- 승인 후 PO 초안 생성 단계로 전달
- End-to-End 테스트 시나리오 작성

## Phase 3 입력 처리

Phase 4는 Phase 3 폴더의 내부 평가 로직을 직접 참조하지 않고, 공용 계약에 정의된 `output/evaluation_report_batch.json`만 입력으로 받는다.

| `next_action` | Phase 4 상태 | 동작 |
|---|---|---|
| `approval_pending` | `APPROVAL_PENDING` | `top_candidate_id` 기준으로 사용자 승인 요청 |
| `manual_review` | `REVIEW_REQUIRED` | 자동 발주 금지, 사람 검토 요청 |
| `no_viable_candidate` | `REJECTED` 또는 재검색 상태 | PO 초안 생성 금지, 재검색/종료 처리 |

Phase 4는 Phase 3의 점수나 판정을 다시 계산하지 않는다. 승인 메시지에는 `items` 내부의 `decision_context`, `scores`, `spec_analysis.highlighted_differences`를 그대로 사용한다.

## 상태 정의 초안

| 상태 | 의미 | 다음 동작 |
|---|---|---|
| `IDLE` | 대기 상태 | 재고 모니터링 |
| `SHORTAGE_DETECTED` | 부족 자재 감지 | 웹 검색 실행 |
| `CANDIDATES_FOUND` | 후보 수집 완료 | 평가 실행 |
| `REVIEW_REQUIRED` | 검토 필요 | 사용자 확인 |
| `APPROVAL_PENDING` | 승인 대기 | 사용자 승인/반려 |
| `REJECTED` | 사용자 반려 | 검색 조건 변경 또는 종료 |
| `APPROVED` | 사용자 승인 | PO 초안 생성 |
| `PO_DRAFT_CREATED` | 발주 초안 생성 완료 | 종료 |

## 출력 포맷

```json
{
  "workflow_id": "WF-20260502-001",
  "status": "APPROVAL_PENDING",
  "shortage_event": {},
  "candidate_results": [],
  "evaluation_report_batch": {},
  "selected_candidate_id": "WEB-001",
  "approval": {
    "required": true,
    "approved": null,
    "approver": null,
    "approved_at": null
  }
}
```

## 완료 기준

- 각 Phase 산출물이 하나의 State로 연결된다.
- 평가 완료 후 승인 전에는 PO 초안이 생성되지 않는다.
- 반려 시 프로세스가 안전하게 중단되거나 재검색으로 이동한다.
- 승인 시 Phase 5 또는 PO 생성 함수로 필요한 데이터가 전달된다.
- Happy Path 시나리오가 처음부터 끝까지 실행된다.

## 테스트 체크리스트

- 후보가 없을 때 재시도 또는 종료 상태로 이동하는가?
- 평가 점수 미달 후보가 승인 대기로 가지 않는가?
- 승인 전 PO 파일이 생성되지 않는가?
- 반려 입력 후 PO 파일이 생성되지 않는가?
- 승인 입력 후 정확한 후보로 PO 초안이 생성되는가?

## 다음 Phase로 넘길 것

- 승인 완료된 후보 데이터
- 승인자/승인 시각
- PO 초안 생성에 필요한 업체명, 자재코드, 수량, 단가, 총액
