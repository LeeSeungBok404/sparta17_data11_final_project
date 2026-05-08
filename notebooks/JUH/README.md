# CME 후보 탐색 파이프라인

## 1. 프로젝트 개요
이 프로젝트는 **CME에 적합한 유튜브 채널(스트리머/크리에이터) 후보를 자동으로 수집, 평가, 선별**하기 위한 파이프라인이다.

핵심 목표는 다음과 같다.

- CME top30 레퍼런스 채널의 특성을 기준으로
- 유튜브에서 신규 후보 채널을 지속적으로 탐색하고
- 후보 채널의 최근 활동성과 CME 유사도를 계산한 뒤
- 최종 shortlist와 대시보드용 데이터까지 자동 생성하는 것

---

## 2. 전체 파이프라인 흐름

현재 파이프라인은 아래 순서로 동작한다.

1. **STEP 1 - CME 레퍼런스 수집**
   - CME top30 레퍼런스 채널의 최신 채널 정보와 최근 영상을 YouTube API로 다시 수집
   - 레퍼런스 채널 raw 및 기초 집계 생성

2. **STEP 2 - 일반 후보 Discovery 수집**
   - 세그먼트별 검색 키워드로 유튜브 후보 영상을 탐색
   - 기존에 이미 본 채널/영상은 state 파일을 이용해 중복 방지
   - 신규 후보 영상 raw 저장

3. **STEP 3 - 후보 데이터 준비**
   - 후보 채널 집계본을 읽어 한국 채널 추정, 최소 구독자수/영상수 기준 필터 적용
   - scoring 가능한 후보 테이블 생성

4. **STEP 4 - CME 레퍼런스 프로필 생성**
   - CME top30 기준 레퍼런스 채널만 필터링
   - 구독자수, 조회수, 참여율, 라이브 비율 등 reference 분포 요약 생성

5. **STEP 5 - CME 유사도 계산**
   - 후보 채널이 레퍼런스 채널 분포와 얼마나 유사한지 점수화
   - `씨미유사도점수`, `씨미유사도등급`, `라이브신호존재여부` 생성

6. **STEP 6 - shortlist 생성**
   - 유사도 + 참여율 + 조회수를 기준으로 최종 후보군 선별
   - 전체 shortlist와 세그먼트별 shortlist 생성

7. **STEP 7 - 대시보드용 데이터 저장**
   - summary / candidate table / segment table / reference table 생성
   - 대시보드에서 바로 읽을 수 있는 csv 저장

---

## 3. 폴더 구조

---

PROJECT_ROOT/
├─ .venv/                  # 가상환경
├─ 05_state/               # dedup / progress / state 파일
├─ 06_logs/                # 실행 로그
├─ 07_code/                # 실행 코드
│  ├─ config.py
│  ├─ run_pipeline.py
│  ├─ pipeline/
│  └─ utils/
├─ 08_raw/                 # API raw 수집 데이터
├─ 09_intermediate/        # 중간 집계 / 실험 / 분석 보조 결과
├─ 10_dashboard/           # 대시보드 입력용 데이터
├─ 11_final/               # 최종 핵심 결과
├─ output/                 # 과거 임시 산출물 / 정리 예정
└─ team_share/             # 팀 공유용 복사본


### 4.주요 결과 파일
1. 11_final/core_reference/cime_reference_profile_filtered.csv
2. 11_final/core_output/cime_similarity_scored_candidates.csv
3. 11_final/core_output/cime_final_shortlist.csv
4. 11_final/core_output/cime_final_shortlist_by_segment.csv
5. 10_dashboard/data/dashboard_summary.csv

### 5.현재 상태
- reference 수집 가능(소프트콘 랭킹 기반 씨미 스트리머 top30만)
- discovery 수집 가능
- candidate 준비 가능
- similarity 계산 가능
- shortlist 생성 가능
- dashboard용 csv 저장 가능

즉, end-to-end로 한 번 실행 가능한 상태입니다.

### 6. 현재 보완 중인 부분
- refresh step은 별도 파일로 존재하지만 아직 메인 파이프라인에는 미연결
- 키워드 / 세그먼트 설계는 계속 보완 중
- 일부 cime 표기는 추후 정리 예정