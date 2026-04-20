"""
소프트콘 버추얼 랭킹 크롤러 (Playwright 버전)
=================================================

[실행 방법]
1.본인 이니셜 폴더로 data 하위 폴더를 만들고 그 아래에 input, logs, processed, raw 폴더를 만든다
2.main.py를 본인 이니셜 폴더로 복사한 뒤 bash에 아래 명령어를 친다(본인 이니셜로 rename)
uv run python notebooks/LSB/main.py all
3.PROFIT!

[실행 흐름]
  0단계: Google 계정으로 소프트콘 로그인
         - session.json이 있으면 자동 로그인 (쿠키 복원)
         - 없거나 만료됐으면 이메일/비밀번호 입력 => 2단계 인증 시 수동 대기
  1단계: 랭킹 페이지(p)에서 스트리머 목록 수집 => data/input/ 에 CSV 저장
  2단계: 스트리머별 통계 페이지 접속 => CSV 다운로드 버튼 클릭 => data/raw/ 에 저장

[예외 처리 및 재시작 로직]
  - 1단계(랭킹 수집)에도 오류 시 브라우저 재시작 + 해당 페이지부터 이어서 수집
  - 네트워크 오류/타임아웃 시 크래시 대신 안전하게 재시도
  - 보안 검문소 감지 시 새로고침 => 실패 시 브라우저 재시작
  - Playwright TimeoutError 발생 시 자동 재시작
  - 다운로드 중 세션 만료 감지 => 브라우저 재시작으로 재로그인
  - 로그인 성공 검증 후에만 세션 저장 (깨진 세션 저장 방지)
  - 수집 실패 시 데이터 누락 방지 (seen set 보호)
  - Windows/Mac 자동 감지 (User-Agent)

[사용법]
  uv run python main.py collect       # 1단계만: 랭킹 수집
  uv run python main.py download      # 2단계만: 통계 CSV 다운로드 (기존 랭킹 CSV 필요)
  uv run python main.py all           # 1단계 + 2단계 연속 실행

[이어서 실행]
  - 2단계는 이미 다운로드된 파일이 있으면 자동 스킵 => 중간에 종료해도 다시 돌리면 이어서 진행
  - 재시작 한도 초과로 중단되면 data/logs/ 에 남은 목록/실패 목록 CSV 저장
"""

import csv
import platform
import re
import shutil
import sys
import time
import pandas as pd
from pathlib import Path
from playwright.sync_api import (
    sync_playwright, Page, Browser, BrowserContext,
    TimeoutError as PlaywrightTimeout,
)


# ============================================================
# 경로 설정
# ============================================================

BASE_DIR = Path(__file__).resolve().parent     # 이 파일이 위치한 폴더
DATA_DIR = BASE_DIR / "data"

INPUT_DIR  = DATA_DIR / "input"    # 1단계 결과: 랭킹 스트리머 목록 CSV
RAW_DIR    = DATA_DIR / "raw"      # 2단계 결과: 스트리머별 통계 CSV
LOG_DIR    = DATA_DIR / "logs"     # 실패/잔여 목록 CSV

for d in [INPUT_DIR, RAW_DIR, LOG_DIR]:
    d.mkdir(parents=True, exist_ok=True)


# ============================================================
# 설정값 (필요에 따라 수정)
# ============================================================

MEMBER_TAG = "LSB"                 # 조원 태그 (파일명에 사용)

# --- Google 로그인 계정 ---
GOOGLE_EMAIL = "sibchiljo9@gmail.com"
GOOGLE_PASSWORD = "Mnc-711!"
SESSION_FILE = BASE_DIR / "session.json"   # 로그인 세션 저장 파일

# --- 랭킹 수집 범위 ---
START_PAGE = 11                    # 수집 시작 페이지 (조별 분담)
END_PAGE = 12                      # 수집 종료 페이지

# --- 통계 다운로드 기간 (UTC, URL 인코딩) ---
# 한국시간 2025-01-01 00:00:00 ~ 2026-03-31 23:59:59
START_DT = "2024-12-31T15%3A00%3A00.000Z"
END_DT   = "2026-03-31T14%3A59%3A59.999Z"

# --- 브라우저 재시작 제한 ---
MAX_RESTART_PER_STREAMER = 2       # 2단계: 한 스트리머당 최대 재시작 횟수
MAX_RESTART_PER_PAGE = 2           # 1단계: 한 페이지당 최대 재시작 횟수
MAX_RESTART_TOTAL = 10             # 전체 실행 동안 최대 재시작 횟수 (초과 시 중단)


# ============================================================
# URL 빌더
# ============================================================

# 랭킹 페이지 URL 템플릿 ({page}에 페이지 번호가 들어감)
RANKING_URL = (
    "https://viewership.softc.one/ranking/virtualsoftcone"
    "?startDateTime=2026-02-28T15%3A00%3A00.000Z"
    "&endDateTime=2026-03-31T14%3A59%3A59.999Z"
    "&page={page}"
)


def make_statistics_url(platform_key: str, channel_id: str) -> str:
    """스트리머 고유 채널 ID로 통계 페이지 URL 생성"""
    return (
        f"https://viewership.softc.one/channel/{platform_key}/{channel_id}/statistics"
        f"?startDateTime={START_DT}&endDateTime={END_DT}"
    )


# ============================================================
# 유틸 함수
# ============================================================

def safe_name(text: str) -> str:
    """파일명에 사용할 수 없는 문자(<>:"/\\|?*)를 _로 치환"""
    for ch in '<>:"/\\|?*':
        text = text.replace(ch, "_")
    return text.strip()


def make_output_path(plat: str, streamer_name: str, channel_id: str) -> Path:
    """통계 CSV 저장 경로 생성 (예: NAVERCHZZK_스트리머명_채널ID_statistics.csv)"""
    return RAW_DIR / f"{safe_name(plat)}_{safe_name(streamer_name)}_{channel_id}_statistics.csv"


def save_rows_to_csv(rows: list[dict], output_path: Path):
    """딕셔너리 리스트를 CSV 파일로 저장 (UTF-8 BOM, Excel 호환)"""
    if not rows:
        return
    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


# ============================================================
# 보안 검문소 감지 / 페이지 이동
# ============================================================

# 소프트콘 사이트의 보안 검문소(봇 차단) 페이지에 포함되는 키워드
CHECKPOINT_KEYWORDS = [
    "브라우저를 확인하지 못했습니다",
    "보안 검문소",
    "Vercel",
    "코드 21",
]

# 브라우저를 재시작해야 하는 오류 메시지 키워드
RESTART_KEYWORDS = [
    "보안 검문소", "재시작 필요",       # 우리가 raise하는 메시지
    "Target closed",                    # 브라우저 탭이 닫힘
    "browser has been closed",          # 브라우저가 종료됨
    "Connection closed",                # 연결 끊김
    "Target page",                      # 페이지 참조 불가
    "Timeout",                          # Playwright 타임아웃
    "net::ERR_",                        # 네트워크 오류 (ERR_CONNECTION_REFUSED 등)
]


def is_security_checkpoint(page: Page) -> bool:
    """
    현재 페이지가 보안 검문소(봇 차단 페이지)인지 확인.
    브라우저가 죽었거나 응답 없으면 예외 대신 True 반환 => 재시작 유도.
    """
    try:
        body_text = page.inner_text("body", timeout=5000)
        return any(kw in body_text for kw in CHECKPOINT_KEYWORDS)
    except Exception:
        return True  # 페이지 읽기 실패 => 비정상 상태 => 재시작 필요


def is_restart_needed(error: Exception) -> bool:
    """
    발생한 예외가 브라우저 재시작으로 해결 가능한 종류인지 판별.
    - PlaywrightTimeout: 페이지 로딩/요소 대기 시간 초과
    - RESTART_KEYWORDS에 해당하는 오류 메시지
    """
    if isinstance(error, PlaywrightTimeout):
        return True
    return any(kw in str(error) for kw in RESTART_KEYWORDS)


def goto_with_retry(page: Page, url: str, max_refresh: int = 2) -> bool:
    """
    URL로 이동한 뒤, 보안 검문소가 감지되면 새로고침으로 재시도.
    - 성공(정상 페이지): True
    - 실패(검문소 해제 불가 / 네트워크 오류): False
    네트워크 오류나 타임아웃이 발생해도 크래시 없이 False를 반환.
    """
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(5000)  # JS 렌더링 대기
    except Exception:
        return False  # 페이지 이동 자체 실패

    if not is_security_checkpoint(page):
        return True   # 정상 페이지 도달

    # 보안 검문소 감지 => 새로고침으로 해제 시도
    for attempt in range(max_refresh):
        print(f"  보안 검문 감지 => 새로고침 {attempt + 1}/{max_refresh}")
        try:
            page.reload(wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(8000)
        except Exception:
            return False

        if not is_security_checkpoint(page):
            return True

    return False  # 새로고침으로도 해제 불가


# ============================================================
# 브라우저 생성 / 로그인 / 재시작
# ============================================================

def create_browser(pw) -> tuple[Browser, BrowserContext, Page]:
    """
    Playwright Chromium 브라우저 생성.
    - headless=False: 브라우저 창을 표시 (봇 감지 우회에 유리)
    - channel="chrome": 시스템에 설치된 Chrome 사용
    - session.json이 있으면 쿠키/로그인 상태 자동 복원
    - navigator.webdriver 속성 제거 (봇 감지 우회)
    - OS에 따라 적절한 User-Agent 자동 설정
    """
    browser = pw.chromium.launch(
        headless=False,
        channel="chrome",
        args=[
            "--disable-blink-features=AutomationControlled",  # 자동화 탐지 방지
            "--no-first-run",
            "--no-default-browser-check",
        ],
    )

    # OS에 맞는 User-Agent 설정 (Mac에서 Windows UA 쓰면 의심받을 수 있음)
    if platform.system() == "Darwin":
        ua = (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/136.0.0.0 Safari/537.36"
        )
    else:
        ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/136.0.0.0 Safari/537.36"
        )

    # 브라우저 컨텍스트 옵션 (저장된 세션이 있으면 쿠키 복원 포함)
    context_opts = dict(
        viewport={"width": 1280, "height": 900},
        locale="ko-KR",
        timezone_id="Asia/Seoul",
        user_agent=ua,
    )
    if SESSION_FILE.exists():
        context_opts["storage_state"] = str(SESSION_FILE)

    context = browser.new_context(**context_opts)

    # navigator.webdriver = true 제거 (Selenium/Playwright 자동화 탐지 우회)
    context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
    """)

    page = context.new_page()
    return browser, context, page


def is_logged_in(page: Page) -> bool:
    """
    소프트콘 메인 페이지에 접속해서 로그인 상태 확인.
    '로그인' 버튼이 보이면 미로그인, 안 보이면 로그인 상태.
    """
    try:
        page.goto("https://viewership.softc.one", wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(3000)
        login_btn = page.query_selector("button:has-text('로그인')")
        return login_btn is None
    except Exception:
        return False


def login_google(page: Page, context: BrowserContext):
    """
    소프트콘 사이트에 Google OAuth로 로그인.

    [흐름]
    1. 저장된 세션(session.json)이 유효하면 => 스킵
    2. 소프트콘 로그인 페이지 => 'Google 계정으로 로그인' 클릭
    3. Google 이메일 입력 => '다음'
    4. Google 비밀번호 입력 => '다음'
    5. 2단계 인증이 필요하면 => 사용자가 브라우저에서 직접 처리 (최대 5분 대기)
    6. 로그인 성공 검증 후 session.json에 세션 저장

    [세션 저장]
    - 성공 시에만 저장 => 다음 실행 때 자동 로그인
    - 실패 시 저장하지 않음 => 깨진 세션으로 인한 연쇄 실패 방지
    """
    # 이미 로그인 상태면 스킵
    if is_logged_in(page):
        print("이미 로그인 상태 (저장된 세션 유효)")
        return

    print("로그인 시작...")

    # 소프트콘 로그인 페이지로 이동
    page.goto("https://viewership.softc.one/auth/signin", wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(3000)

    # Google 로그인 버튼 클릭 => accounts.google.com으로 리다이렉트
    page.click("button:has-text('Google 계정으로 로그인')")
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(3000)

    # 이메일 입력 (Google 로그인 첫 화면)
    email_input = page.query_selector("input[type='email']")
    if email_input:
        page.fill("input[type='email']", GOOGLE_EMAIL)
        page.click("button:has-text('다음')")
        page.wait_for_timeout(3000)

    # 비밀번호 입력
    pw_input = page.query_selector("input[type='password']:visible")
    if pw_input:
        page.fill("input[type='password']:visible", GOOGLE_PASSWORD)
        page.click("button:has-text('다음')")
        page.wait_for_timeout(5000)

    # 2단계 인증 등 추가 확인이 필요한 경우 => 사용자 수동 처리 대기
    if "accounts.google.com" in page.url:
        print()
        print("=" * 60)
        print("  Google 추가 인증이 필요합니다!")
        print("  브라우저에서 직접 인증을 완료해주세요.")
        print("  (2단계 인증, 기기 확인 등)")
        print("  완료되면 자동으로 진행됩니다. (최대 5분 대기)")
        print("=" * 60)
        print()
        page.wait_for_url("**/viewership.softc.one/**", timeout=300000)
        page.wait_for_timeout(3000)

    # 로그인 성공 여부 검증 => 실패 시 깨진 세션 저장 방지
    if not is_logged_in(page):
        print("로그인 실패 — 세션을 저장하지 않습니다.")
        raise Exception("Google 로그인 실패 — 계정 정보 또는 2단계 인증을 확인해주세요.")

    # 성공 시에만 세션 저장 (다음 실행 때 자동 로그인)
    context.storage_state(path=str(SESSION_FILE))
    print(f"로그인 완료! 세션 저장됨 ({SESSION_FILE.name})")


def restart_browser(pw, browser: Browser | None) -> tuple[Browser, BrowserContext, Page]:
    """
    브라우저를 완전히 종료 => 새로 생성 => 세션으로 자동 로그인.
    크롤링 중 보안 검문소/브라우저 오류 발생 시 호출됨.
    """
    if browser:
        try:
            browser.close()
        except Exception:
            pass
    time.sleep(2)

    browser, context, page = create_browser(pw)
    login_google(page, context)
    print("  브라우저 재시작 + 로그인 완료")
    return browser, context, page


# ============================================================
# 1단계: 랭킹 수집
# - 지정된 페이지 범위(START_PAGE ~ END_PAGE)의 랭킹 데이터를 수집
# - 오류 발생 시 브라우저 재시작 후 해당 페이지부터 이어서 수집
# ============================================================

def collect_one_page(page: Page, pg: int, seen: set) -> list[dict]:
    """
    랭킹 한 페이지의 스트리머 데이터를 수집.

    - 튜터 코드 구조 유지
    - 랭킹 행만 필터링
    - rank 보정 없음
    - 순서 보장을 위해 rank 기준 정렬만 수행
    """
    url = RANKING_URL.format(page=pg)

    if not goto_with_retry(page, url):
        raise Exception("보안 검문소 해제 불가 => 브라우저 재시작 필요")

    page.wait_for_timeout(3000)

    anchors = page.query_selector_all("a[href*='/channel/']")
    results = []
    local_seen = set()

    for a in anchors:
        href = a.get_attribute("href") or ""
        text = (a.inner_text() or "").strip()

        m = re.search(r"/channel/([^/]+)/([^/?#]+)", href)
        if not m:
            continue

        platform_key = m.group(1)
        channel_id = m.group(2)

        if channel_id in seen or channel_id in local_seen:
            continue

        lines = [line.strip() for line in text.split("\n") if line.strip()]

        # 랭킹 행만 통과
        if len(lines) < 2:
            continue
        if not lines[0].isdigit():
            continue

        local_seen.add(channel_id)

        results.append({
            "page": pg,
            "rank": lines[0],
            "streamer_name": lines[1],
            "platform_key": platform_key,
            "channel_id": channel_id,
            "detail_url": href,
        })

    results.sort(key=lambda x: int(x["rank"]))
    seen.update(local_seen)
    return results


def run_collect(pw, browser, context, page) -> tuple[Path | None, Browser, BrowserContext, Page]:
    """
    1단계 실행: 랭킹 수집 => CSV 저장.

    [재시도 로직]
    - 페이지별로 재시도 루프 (최대 MAX_RESTART_PER_PAGE회 브라우저 재시작)
    - 전체 재시작 횟수가 MAX_RESTART_TOTAL 초과 시 수집 중단
    - 브라우저가 재시작될 수 있으므로 갱신된 browser/context/page를 반환
    """
    print("\n[1단계] 랭킹 수집 시작\n")

    all_results = []
    seen = set()           # 전체 페이지에 걸쳐 중복 channel_id 방지
    total_restarts = 0

    for pg in range(START_PAGE, END_PAGE + 1):
        print("=" * 60)
        print(f"페이지 {pg} 이동")

        # 페이지별 재시작 재시도 루프
        success = False
        restart_count = 0

        while not success and restart_count < MAX_RESTART_PER_PAGE:
            try:
                page_results = collect_one_page(page, pg, seen)
                all_results.extend(page_results)
                print(f"  수집 완료: {len(page_results)}명")
                success = True

            except Exception as e:
                if is_restart_needed(e) and restart_count < MAX_RESTART_PER_PAGE:
                    restart_count += 1
                    total_restarts += 1
                    print(f"  [재시작 {restart_count}/{MAX_RESTART_PER_PAGE}] {str(e)[:80]}")

                    if total_restarts > MAX_RESTART_TOTAL:
                        print(f"\n[중단] 전체 재시작 {MAX_RESTART_TOTAL}회 초과")
                        break

                    browser, context, page = restart_browser(pw, browser)
                else:
                    # 재시작으로 해결 안 되는 오류 => 이 페이지 포기, 다음 페이지로
                    print(f"  [실패] 페이지 {pg} 수집 불가: {e}")
                    break

        if total_restarts > MAX_RESTART_TOTAL:
            break

    # 수집 결과 CSV 저장
    if not all_results:
        print("수집된 데이터 없음")
        return None, browser, context, page

    output_file = INPUT_DIR / f"{MEMBER_TAG}_streamers_p{START_PAGE}_p{END_PAGE}.csv"
    save_rows_to_csv(all_results, output_file)

    print("=" * 60)
    print(f"랭킹 저장 완료: {output_file.resolve()}")
    print(f"총 수집: {len(all_results)}명 (브라우저 재시작 {total_restarts}회)")
    return output_file, browser, context, page


# ============================================================
# 2단계: 통계 CSV 다운로드
# - 1단계에서 수집한 스트리머 목록을 순회하며 통계 CSV 다운로드
# - 이미 다운로드한 파일은 자동 스킵 (이어서 실행 가능)
# - 오류 시 브라우저 재시작 후 같은 스트리머부터 재시도
# - 세션 만료 시 재로그인 후 재시도
# ============================================================

def is_session_expired(page: Page) -> bool:
    """
    통계 페이지에서 세션 만료(로그아웃) 상태인지 확인.
    로그인 상태면 'CSV 다운로드' 버튼이 보여야 하는데,
    '로그인' 버튼만 보이면 세션 만료로 판단.
    """
    try:
        body_text = page.inner_text("body", timeout=3000)
        has_csv_btn = "CSV 다운로드" in body_text
        has_login_btn = "로그인" in body_text
        return has_login_btn and not has_csv_btn
    except Exception:
        return False


def download_one_streamer(page: Page, url: str) -> Path:
    """
    한 스트리머의 통계 페이지에서 CSV 파일 다운로드.

    [흐름]
    1. 통계 페이지로 이동 (보안 검문소 시 새로고침 재시도)
    2. 세션 만료 감지 시 예외 발생 => 호출측에서 브라우저 재시작
    3. 'CSV 다운로드' 버튼 대기 => 클릭
    4. Playwright의 expect_download로 다운로드 완료 대기
    5. 다운로드된 임시 파일 경로 반환
    """
    # 페이지 이동 (실패 시 예외 => 호출측에서 재시작 처리)
    if not goto_with_retry(page, url):
        raise Exception("보안 검문소 해제 불가 => 브라우저 재시작 필요")

    # 세션 만료 감지 (로그아웃 상태면 CSV 버튼이 안 보임)
    if is_session_expired(page):
        raise Exception("세션 만료 감지 => 브라우저 재시작 필요")

    # CSV 다운로드 버튼이 렌더링될 때까지 대기 (최대 35초)
    page.wait_for_selector("button:has-text('CSV 다운로드')", timeout=35000)
    page.wait_for_timeout(3000)  # 테이블 데이터 렌더링 안정화

    # 다운로드 이벤트 감지 + 버튼 클릭 (최대 90초 대기)
    with page.expect_download(timeout=90000) as download_info:
        page.click("button:has-text('CSV 다운로드')")

    download = download_info.value
    return Path(download.path())   # Playwright 관리 임시 파일 경로


def run_download(pw, browser: Browser, context: BrowserContext, page: Page, input_csv: Path):
    """
    2단계 실행: 스트리머별 통계 CSV 다운로드.

    [이어서 실행]
    - data/raw/ 에 이미 파일이 있는 스트리머는 자동 스킵
    - 중간에 종료해도 다시 실행하면 남은 것만 처리

    [재시도 로직]
    - 스트리머별 최대 MAX_RESTART_PER_STREAMER회 브라우저 재시작
    - 전체 MAX_RESTART_TOTAL회 초과 시 중단 + 남은 목록 CSV 저장
    - 재시작 불가 오류 => 실패 목록에 기록 후 다음 스트리머로
    """
    print(f"\n[2단계] 통계 다운로드 시작\n")

    if not input_csv.exists():
        print(f"입력 CSV를 찾을 수 없습니다: {input_csv}")
        return

    with open(input_csv, "r", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    print(f"입력 파일: {input_csv.resolve()}")
    print(f"대상 수: {len(rows)}명")

    failed_rows = []       # 실패한 스트리머 정보
    total_restarts = 0

    for i, row in enumerate(rows, start=1):
        streamer_name = row["streamer_name"]
        platform_key = row["platform_key"]
        channel_id = row["channel_id"]
        page_num = row.get("page", "")
        rank = row.get("rank", "")
        detail_url = row.get("detail_url", "")
        plat = row.get("platform", parse_platform(platform_key))

        output_path = make_output_path(plat, streamer_name, channel_id)
        url = make_statistics_url(platform_key, channel_id)

        print("=" * 80)
        print(f"[{i}/{len(rows)}] {streamer_name} (page={page_num}, rank={rank})")

        # 이미 다운로드한 파일이 있으면 스킵 (이어서 실행 핵심 로직)
        if output_path.exists():
            print(f"  이미 존재 => 스킵")
            continue

        # 재시작 포함 재시도 루프
        success = False
        restart_count = 0

        while not success and restart_count < MAX_RESTART_PER_STREAMER:
            try:
                temp_path = download_one_streamer(page, url)
                
                platform = row.get("platform", parse_platform(platform_key))
                append_metadata_to_downloaded_csv(
                    temp_path=temp_path,
                    output_path=output_path,
                    streamer_name=streamer_name,
                    platform=platform,
                    channel_id=channel_id,
                )
                print(f"  저장 완료: {output_path.name}")
                success = True
                page.wait_for_timeout(2000)  # 연속 요청 방지 대기

            except Exception as e:
                if is_restart_needed(e) and restart_count < MAX_RESTART_PER_STREAMER:
                    restart_count += 1
                    total_restarts += 1
                    print(f"  [재시작 {restart_count}/{MAX_RESTART_PER_STREAMER}] {str(e)[:80]}")

                    # 전체 재시작 한도 초과 => 남은 목록 저장 후 중단
                    if total_restarts > MAX_RESTART_TOTAL:
                        print(f"\n[중단] 전체 재시작 {MAX_RESTART_TOTAL}회 초과")
                        remaining = rows[i - 1:]  # 현재 스트리머 포함 남은 전부
                        remaining_path = LOG_DIR / f"{MEMBER_TAG}_remaining_after_checkpoint.csv"
                        save_rows_to_csv(remaining, remaining_path)
                        print(f"남은 대상 저장: {len(remaining)}건 => {remaining_path}")
                        return

                    browser, context, page = restart_browser(pw, browser)
                else:
                    # 재시작으로 해결 안 되는 오류 => 실패 기록 후 다음 스트리머
                    print(f"  [실패] {type(e).__name__}: {str(e)[:100]}")
                    failed_rows.append({
                        "page": page_num, "rank": rank,
                        "streamer_name": streamer_name,
                        "platform": plat,
                        "platform_key": platform_key,
                        "channel_id": channel_id,
                        "detail_url": detail_url,
                        "error_type": type(e).__name__,
                        "error_message": str(e)[:200],
                    })
                    break

    # 전체 완료 후 실패 목록 저장
    if failed_rows:
        failed_path = LOG_DIR / f"{MEMBER_TAG}_failed_streamers.csv"
        save_rows_to_csv(failed_rows, failed_path)
        print(f"\n실패 목록 저장: {failed_path.resolve()} ({len(failed_rows)}건)")
    else:
        print("\n실패 없음")

    print(f"총 브라우저 재시작 횟수: {total_restarts}회")
    


def parse_platform(platform_key: str) -> str:
    if platform_key == "naverchzzk":
        return "CHZZK"
    elif platform_key == "afreeca":
        return "SOOP"
    return platform_key.upper()


def append_metadata_to_downloaded_csv(
    temp_path: Path,
    output_path: Path,
    streamer_name: str,
    platform: str,
    channel_id: str,
):
    with open(temp_path, "r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    if not rows:
        return

    fieldnames = list(rows[0].keys()) + ["streamer_name", "platform", "channel_id"]

    for row in rows:
        row["streamer_name"] = streamer_name
        row["platform"] = platform
        row["channel_id"] = channel_id

    with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
        

def merge_raw_csvs() -> Path:
    """
    data/raw/ 아래의 *_statistics.csv 파일들을 하나로 병합해서
    data/processed/ 아래에 페이지 범위가 포함된 최종 CSV로 저장한다.
    """
    processed_dir = DATA_DIR / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)

    output_path = processed_dir / f"final_streamer_data_p{START_PAGE}_p{END_PAGE}.csv"

    dfs = []
    files = list(RAW_DIR.glob("*_statistics.csv"))

    print("\n[3단계] raw CSV 병합 시작\n")
    print("찾은 파일 수:", len(files))

    for file in files:
        print("처리 중:", file.name)
        try:
            df = pd.read_csv(file)

            required_cols = ["streamer_name", "platform", "channel_id"]
            for col in required_cols:
                if col not in df.columns:
                    raise ValueError(f"{col} 컬럼 없음")

            dfs.append(df)

        except Exception as e:
            print("에러:", file.name, e)

    if not dfs:
        raise ValueError("병합할 데이터프레임이 없습니다.")

    final_df = pd.concat(dfs, ignore_index=True)
    final_df.to_csv(output_path, index=False, encoding="utf-8-sig")

    print("=" * 60)
    print("통합 완료")
    print("shape:", final_df.shape)
    print("저장 위치:", output_path.resolve())

    file_size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"파일 크기: {file_size_mb:.2f} MB")

    return output_path


# ============================================================
# 메인
# ============================================================

def main():
    """
    실행 모드에 따라 1단계/2단계/전체를 수행.
    - collect:  1단계(랭킹 수집)만 실행
    - download: 2단계(통계 다운로드)만 실행 (기존 랭킹 CSV 필요)
    - all:      1단계 => 2단계 연속 실행 (기본값)
    """
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"

    if mode not in ("collect", "download", "all"):
        print("사용법: uv run python main.py [collect|download|all]")
        sys.exit(1)

    with sync_playwright() as pw:
        browser, context, page = create_browser(pw)

        try:
            # 0단계: Google 로그인 (세션이 있으면 자동, 없으면 수동 인증 대기)
            login_google(page, context)

            # 1단계: 랭킹 수집
            if mode in ("collect", "all"):
                # 브라우저가 재시작될 수 있으므로 갱신된 객체를 받음
                ranking_csv, browser, context, page = run_collect(pw, browser, context, page)
            else:
                # download 모드: 기존에 수집된 랭킹 CSV 사용
                ranking_csv = INPUT_DIR / f"{MEMBER_TAG}_streamers_p{START_PAGE}_p{END_PAGE}.csv"

            # 2단계: 통계 다운로드
            if mode in ("download", "all") and ranking_csv:
                run_download(pw, browser, context, page, ranking_csv)
                
            # 3단계: raw 데이터 통합
            if mode == "all":
                print("\n[3단계] raw 데이터 통합 시작\n")
                merge_raw_csvs()
                print("\n[3단계] raw 데이터 통합 종료\n")

        finally:
            browser.close()
            print("\n브라우저 종료 완료")


if __name__ == "__main__":
    main()
