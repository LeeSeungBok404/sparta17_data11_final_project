내일배움캠프 sparta-data11-practical-project
데이터 분석 및 머신러닝 최종 프로젝트 저장소입니다.

프로젝트 개요
프로젝트명: 데이터 분석 및 머신러닝 실전 프로젝트
프로젝트 기간: 2026.04.08 ~ 2026.05.13
프로젝트 주제: 미디어 / 이커머스
프로젝트 배경:

대시보드 사용자(페르소나 설정)
???

프로젝트 목표


최종 산출물


프로젝트 확장성


프로젝트 과정
문제 정의
분석 목적과 핵심 비즈니스 문제를 설정
KPI 설정
반응률, 전환률, 구매 관련 지표 정의
데이터 이해 및 전처리
데이터 구조 파악 및 정리
분석 수행
EDA 및 인사이트 도출
대시보드 제작
KPI 중심의 Tableau 시각화 구성
페르소나 제안
분석 결과를 바탕으로 실행 가능한 방향 제시

핵심 KPI(초안)
메인 KPI
구매 전환율
보조 KPI
오퍼 열람률
오퍼 완료율
거래 건수
총 거래 금액
고객당 평균 거래 금액
작업 환경
Python: 3.13
가상환경 및 패키지 관리: uv
주요 작업 도구: VSCode, Jupyter Notebook
설치된 주요 패키지
데이터 처리

pandas
numpy
시각화

matplotlib
seaborn
plotly
통계

scipy
statsmodels
pingouin
머신러닝

scikit-learn
xgboost
lightgbm
catboost
협업 규칙
자세한 협업 규칙은 아래 문서를 참고한다.

RULES.md
전체 폴더 구조 설명
sparta-data11-practical-project/
├─ integrated/                    # 공용 통합 작업 폴더
│  ├─ data/                       # 공동 데이터 (원본, 수정 금지)
│  └─ integrated_analysis.ipynb   # 공용 통합 분석 파일
│
├─ notebooks/
│  ├─ member1/            # 개인 작업물
│  ├─ member2/
│  ├─ member3/
│  ├─ member4/
│  └─ member5/
│
├─ pyproject.toml
├─ uv.lock
├─ README.md
└─ .gitignore
폴더 역할 정리

integrated/

팀 공용 데이터 및 통합 분석 파일을 관리하는 폴더
data/에는 원본 데이터만 보관
원본 데이터 직접 수정 금지
공용으로 반영할 코드/노트북만 관리
member1~5/

각자 전처리 / 시각화 / 실험용 노트북 작성 공간
개인 작업물은 본인 폴더에만 커밋
공용 반영이 필요한 내용만 협의 후 integrated/에 반영