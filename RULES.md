프로젝트 규칙
협업 기본 원칙
작업 시작 전 최신 코드를 git pull로 먼저 동기화한다.
개인 작업은 가급적 본인 폴더에서 진행한다.
공용 파일 수정 시 반드시 팀원과 공유한다.
충돌 가능성이 있는 작업은 미리 이야기하고 진행한다.
환경 구축 방법
1. 저장소 초대 받기
Git 관리자에게 GitHub ID 또는 이메일을 전달한 뒤, 저장소 초대를 수락한다.

2. 저장소 클론 및 환경 설정
# 저장소 클론
git clone https://github.com/leegolem/sparta-data11-practical-project.git
cd sparta-data11-practical-project

# 가상환경 생성 및 패키지 설치
uv sync

# 가상환경 활성화 방법은 사용하는 터미널에 따라 아래와 같다.
## Git Bash 사용 시
source .venv/Scripts/activate

## PowerShell 사용 시
.venv\Scripts\Activate.ps1

# 가상환경이 정상적으로 활성화되면 터미널 앞에
(sparta-data11-practical-project) 또는 (.venv) 와 같은 표시가 나타날 수 있다.
3. 연결 확인 방법
초대 수락 및 환경 설정이 끝난 뒤, 아래 순서로 정상 연결 여부를 확인한다.

1. git pull
2. 본인이 배정받은 member 폴더에서 테스트 파일 생성 또는 수정
3. git add "본인폴더명"
4. git commit -m "test: OOO 작업 환경 연결 확인"
5. git push
작업 시작 루틴
작업 시작 전 반드시 git pull을 실행한다.
원격 저장소(GitHub)의 최신 작업물을 먼저 로컬에 동기화한 뒤 작업한다.
라이브러리 추가 규칙 (uv)
새 라이브러리를 추가한 경우 아래 순서를 따른다.

추가한 사람
uv add 패키지명 실행
변경된 pyproject.toml, uv.lock 파일을 함께 커밋
push까지 반영
다른 팀원
git pull
uv sync
작업물 받기 (조원이 해야 할 일)
기본적으로 아래 명령어를 먼저 실행한다.

git pull
- 아래 중 하나라도 해당하면 추가로 uv sync를 실행한다.
    - pyproject.toml이 변경된 경우
    - uv.lock이 변경된 경우
    - import error 또는 라이브러리 관련 에러가 발생한 경우
- 이 경우:
    - uv sync
Git 작업 주의사항
git add . 사용 금지
개인 작업물 커밋 시 git add . 사용을 금지한다.
반드시 필요한 파일만 명시적으로 add한다.
개인 작업물은 아래처럼 본인 폴더만 add한다.
git add "본인폴더명"
공용 파일 수정 시
수정한 파일만 명시적으로 add한다.
커밋 메시지에는 어떤 파일을 어떻게 수정했는지 드러나도록 작성한다.
공용 파일 수정 전에는 팀원과 먼저 공유하거나 협의한다.
파일 및 데이터 관리 규칙
대용량 파일은 GitHub에 업로드하지 않는다.
원본 데이터는 integrated/data/에만 보관한다.
공용 반영이 필요한 내용만 협의 후 integrated/에 반영한다.
공용 저장소에는 코드, 문서, 설정 파일 위주로 관리한다.
대용량 데이터 및 산출물은 아래 구글 드라이브에서 관리한다.
구글 드라이브🔗
오류 발생시 대처헙
git pull 전에 커밋해서 충돌이 발생한 경우

git pull --rebase origin main으로 최신 내용을 먼저 반영한다.
충돌이 발생하면 충돌 내용을 수정한다.
git add 수정한파일 -> git rebase --continue 순서로 진행한다.
git push --force는 팀 협의 없이 사용하지 않는다.
라이브러리 관련 오류가 발생한 경우

먼저 git pull을 실행한다.
이후 uv sync를 실행한다.
그래도 해결되지 않으면 pyproject.toml, uv.lock 변경 여부를 확인한다.
프로젝트 파일 구성
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