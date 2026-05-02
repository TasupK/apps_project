# BuyBee

웹 리서치 기반 대체 자재 탐색 및 발주 초안 생성 PoC입니다.

## 실행

```bash
pip install -r requirements.txt
streamlit run streamlit_hybrid_app.py
```

## 현재 데모 흐름

1. 재고 부족 자재를 감지합니다.
2. 자재 마스터의 기술 스펙을 기준으로 웹 검색 후보를 정리합니다.
3. 후보별 기술 호환성, 출처 신뢰도, 가격, 납기를 비교합니다.
4. 사용자가 챗봇에서 승인하면 `PO_Result.csv` 발주 초안을 생성합니다.

## 주요 변경 방향

- 조달청 API 의존을 제거하고 웹 검색/제조사/공식 판매처 기반 리서치로 전환
- Vector DB 단독 매칭 대신 필수 스펙 Rule 검증과 출처 신뢰도 점수 추가
- Human-in-the-loop 승인 전에는 PO 초안이 생성되지 않도록 통제
- 실제 SAP 연동 표현을 제거하고 PoC 단계에서는 Mock PO 파일 생성으로 한정
