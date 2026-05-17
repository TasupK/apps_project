# Phase 5 대시보드 UI / PO 생성 흐름 변경 사항

## 목적

이번 변경은 Phase 5 Streamlit 하이브리드 대시보드에서 Phase 4 승인 및 PO 생성 흐름을 더 명확하게 조작하고 시연할 수 있도록 보완한 것이다.

핵심 Phase 4 그래프 엔진 자체를 크게 바꾼 것이 아니라, 대시보드 화면에서 다음 작업을 자연스럽게 수행할 수 있도록 UI를 개선했다.

- 실제 진행된 단계만 화면에 표시
- 사용자가 최종 후보를 직접 선택
- 선택한 후보 기준으로 PO 생성
- Excel, Word, PDF 발주 문서 다운로드 지원

## 현재 흐름도

```text
[1. 부족 자재 선택]
        |
        v
[2. 대체 후보 검색 실행]
        |
        v
[3. Phase 2 후보 수집 및 상세 추출]
        |
        |  - SerpApi: 실제 웹 검색 결과 수집
        |  - OpenAI: 검색어 생성, 가격/납기/스펙 상세 추출
        |
        v
[4. Phase 3 후보 평가]
        |
        +----------------------------+
        |                            |
        v                            v
[recommend / conditional]      [review_required]
        |                            |
        |                            v
        |                    [구매 담당자 수동 검토]
        |                            |
        +-------------+--------------+
                      |
                      v
          [5. 사용자가 최종 후보 선택]
                      |
                      v
          [6. 선택한 후보로 PO 생성]
                      |
                      v
     [7. Excel / Word / PDF 발주 문서 다운로드]
```

## 화면 표시 기준

대시보드는 이제 단계별로 필요한 영역만 보여준다.

| 상태 | 화면에 표시되는 영역 |
| --- | --- |
| 초기 진입 | `#1 실시간 재고 현황`만 표시 |
| 후보 검색/평가 후 | `#1` + `#2 웹 리서치 · 후보 평가 결과` |
| PO 생성 후 | `#1` + `#2` + `#3 최종 발주 보고서` |

이전에는 `PO_Result.csv`가 남아 있으면 새 세션에서도 #3 영역이 먼저 보일 수 있었다. 이제는 현재 세션에서 `선택한 후보로 PO 생성` 버튼을 누른 뒤에만 #3 영역이 표시된다.

## 후보 선택 정책

Phase 3 평가 결과는 자동 최종 결정이 아니라, 구매 담당자의 의사결정을 돕는 참고 자료로 사용한다.

PO 생성 후보로 선택 가능:

- `recommend`
- `conditional_approve`
- `review_required`

PO 생성 후보에서 제외:

- `reject`

즉 `review_required` 후보도 구매 담당자가 직접 검토하고 선택하면 PO를 생성할 수 있다. 이 방식이 Human-in-the-loop 승인 흐름에 더 적합하다.

## UI 변경 사항

- 후보 테이블 아래에 `최종 후보 선택` 드롭다운 추가
- `선택한 후보로 PO 생성` 버튼 추가
- 노란색 `평가 1순위 후보` 카드를 최종 후보 선택 영역 위로 이동
- PO 생성 버튼을 누르기 전에는 `#3 최종 발주 보고서` 영역을 숨김
- 발표용처럼 보이는 설명 문구 제거 또는 업무 화면에 맞게 수정
- 일반 UI 문구에서 불필요한 `Phase 4`, `승인 게이트`, `자동 PO` 표현 정리
- 대시보드에 표시되는 `안전재고` 용어를 `최소 보유 수량`으로 통일

## PO 문서 다운로드

사용자가 최종 후보를 선택하고 `선택한 후보로 PO 생성` 버튼을 누르면 다음 문서를 다운로드할 수 있다.

- Excel 보고서
- Word PO 문서
- PDF PO 문서

추가된 의존성:

```txt
python-docx>=1.1
reportlab>=4.2
```

## API 키 사용 방식

대시보드는 `.env` 파일에서 API 키를 읽는다.

```env
PHASE2_SEARCH_PROVIDER=serpapi
SERPAPI_API_KEY=...
OPENAI_API_KEY=...
```

권장 구성은 SerpApi와 OpenAI 키를 둘 다 사용하는 것이다.

- `SERPAPI_API_KEY`: 실제 웹 검색 결과 수집
- `OPENAI_API_KEY`: 검색어 생성, 후보 페이지의 가격/납기/스펙 상세 추출

SerpApi만 있어도 실제 후보 검색은 가능하다. 다만 OpenAI 키가 없으면 가격, 납기, source type, 스펙 근거 추출 품질이 낮아질 수 있고, 그 결과 `review_required` 후보가 더 많이 나올 수 있다.

## 확인한 동작

SerpApi 키를 설정한 뒤 `MAT-BRG-002` 기준으로 실제 검색을 실행했다.

```txt
candidates = 6
next_action = manual_review
items = 6
```

이 경우 자동 승인 후보는 아니지만, 대시보드에서 `review_required` 후보를 직접 선택해 PO를 생성할 수 있도록 변경했다.

## 변경 파일

- `streamlit_hybrid_app.py`
  - 최종 후보 선택 드롭다운
  - 선택 후보 기준 PO 생성
  - `review_required` 후보 수동 선택 지원
  - 단계별 화면 표시 조건
  - Excel / Word / PDF PO 다운로드 버튼
  - UI 문구 정리
  - `안전재고` 표시명을 `최소 보유 수량`으로 변경

- `requirements.txt`
  - `python-docx` 추가
  - `reportlab` 추가

- `PHASE5_UI_CHANGES.md`
  - 팀 공유용 변경 사항 및 현재 흐름 정리

## 실행 방법

```powershell
cd C:\Users\user\Desktop\APPS\phase-4-1차\apps_project_repo
..\.venv\Scripts\python.exe -m streamlit run streamlit_hybrid_app.py --server.port 8501 --server.address localhost
```

브라우저 접속:

```txt
http://localhost:8501
```

## 주의 사항

- 이번 작업은 Phase 4 엔진 자체 수정이 아니라, Phase 5 대시보드에서 Phase 4 승인/PO 생성 흐름을 조작하고 보여주는 UI 변경이다.
- API 키는 `.env`에만 저장하고 커밋하지 않는다.
- `PO_Result.csv` 같은 실행 산출물은 커밋하지 않는다.
