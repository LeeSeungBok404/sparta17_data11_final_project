"""
X 팔로워 수 수집 - 기존 x_followers_result.csv 이어서 진행 버전

핵심:
- 기존 결과 파일 x_followers_result.csv를 그대로 사용
- 숫자 / NOT_FOUND / SUSPENDED 는 완료 처리
- NO_FOLLOWER_TEXT / TIMEOUT / ERROR / X_STUCK 같은 애매한 실패는 결과 CSV에 저장하지 않음
- 애매한 실패는 debug 폴더에 png/html 저장 가능
- NO_FOLLOWER_TEXT/TIMEOUT은 복구 시도, X_STUCK는 즉시 안전 중단
- 수집 완료 후 channel_id 기준 최종본이 필요하면 별도 merge 코드로 생성

실행 예시:
python fetch_x_followers_cdp_continue.py --limit 500 --delay 2 --goto-wait 3 --max-consecutive-fail 5 --cooldown 90
python fetch_x_followers_cdp_continue.py --limit 500 --delay 2 --goto-wait 3 --max-consecutive-fail 5 --cooldown 90 --no-fail-debug
"""

import argparse
import csv
import random
import re
import time
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout


DEFAULT_INPUT = "bj_links_extracted_full.csv"
DEFAULT_OUTPUT = "x_followers_result.csv"
DEFAULT_CDP = "http://127.0.0.1:9222"
START_TIME_FILE = "x_followers_start_time.txt"
DEBUG_DIR = "x_followers_debug"
PROFILE_URL = "https://x.com/{username}"

DONE_STATUSES = {"NOT_FOUND", "SUSPENDED"}

AMBIGUOUS_STATUSES = {
    "",
    "NO_FOLLOWER_TEXT",
    "NO_FOLLOWER_LINK",
    "TIMEOUT",
    "LOGIN_REQUIRED",
    "ERROR_DETAIL",
    "UNKNOWN",
    "X_STUCK",
}


def now_text():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def normalize_username(username: str) -> str:
    return (username or "").strip().lstrip("@").lower()


def safe_filename(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", text or "")


def parse_count(text: str) -> str:
    if not text:
        return ""

    text = str(text).strip().replace(",", "").replace(" ", "")

    m_ko = re.search(r"([\d.]+)\s*(천|만|억)", text)
    if m_ko:
        num = float(m_ko.group(1))
        unit = m_ko.group(2)
        mult = {"천": 1_000, "만": 10_000, "억": 100_000_000}[unit]
        return str(int(num * mult))

    m_en = re.search(r"([\d.]+)\s*([KMB])", text, re.IGNORECASE)
    if m_en:
        num = float(m_en.group(1))
        unit = m_en.group(2).upper()
        mult = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}[unit]
        return str(int(num * mult))

    m_num = re.search(r"\d+", text)
    if m_num:
        return m_num.group(0)

    return ""


def is_done_value(value: str) -> bool:
    v = (value or "").strip()
    return v.isdigit() or v in DONE_STATUSES


def is_ambiguous_failure(value: str) -> bool:
    v = (value or "").strip()
    if v.isdigit() or v in DONE_STATUSES:
        return False
    return v in AMBIGUOUS_STATUSES or v.startswith("ERROR:")


def load_users(path: str):
    users = []
    seen = set()

    skip = {
        "home", "explore", "notifications", "messages", "i", "intent",
        "share", "hashtag", "search", "settings", "login", "signup",
    }

    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)

        for row in reader:
            url = (row.get("twitter_url") or "").strip()
            if not url:
                continue

            m = re.search(r"(?:twitter\.com|x\.com)/([A-Za-z0-9_]+)", url)
            if not m:
                continue

            username = m.group(1).strip()
            username_key = normalize_username(username)

            if not username_key or username_key in skip:
                continue

            # X 접속은 username 기준으로 한 번만
            if username_key in seen:
                continue
            seen.add(username_key)

            users.append({
                "channel_id": row.get("channel_id", ""),
                "streamer_name": row.get("streamer_name", ""),
                "username": username,
                "twitter_url": url,
            })

    return users


def load_done(path: str):
    """
    기존 x_followers_result.csv에서 완료된 username만 읽음.
    숫자 / NOT_FOUND / SUSPENDED 만 완료.
    NO_FOLLOWER_TEXT / TIMEOUT / ERROR는 완료 아님.
    """
    done = set()

    if not Path(path).exists():
        return done

    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)

        for row in reader:
            username_key = normalize_username(row.get("username", ""))
            followers_count = (row.get("followers_count") or "").strip()

            if username_key and is_done_value(followers_count):
                done.add(username_key)

    return done


def save_debug(page, username: str, status: str):
    if status in DONE_STATUSES:
        return

    p = Path(DEBUG_DIR)
    p.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = f"{safe_filename(username)}_{safe_filename(status)}_{ts}"

    try:
        page.screenshot(path=str(p / f"{base}.png"), full_page=True)
    except Exception:
        pass

    try:
        (p / f"{base}.html").write_text(page.content(), encoding="utf-8")
    except Exception:
        pass


def get_body_text(page) -> str:
    try:
        return page.locator("body").inner_text(timeout=5000)
    except Exception:
        return ""


def detect_status_from_body(body_text: str) -> str | None:
    text = body_text or ""

    suspended_patterns = [
        "계정이 일시 정지되었습니다",
        "이 계정은 X의 운영원칙을 위반했으므로 일시 정지되었습니다",
        "Account suspended",
        "This account is suspended",
    ]

    not_found_patterns = [
        "계정이 존재하지 않음",
        "This account doesn’t exist",
        "This account doesn't exist",
        "Account doesn’t exist",
        "Account doesn't exist",
        "다른 검색어를 시도해보세요",
        "Try searching for another",
    ]

    login_patterns = [
        "로그인하세요",
        "X에 로그인",
        "Sign in to X",
        "Log in to X",
    ]

    for p in suspended_patterns:
        if p in text:
            return "SUSPENDED"

    for p in not_found_patterns:
        if p in text:
            return "NOT_FOUND"

    stripped = text.strip()
    if stripped in {"", "X"} or len(stripped) < 10:
        return "X_STUCK"

    if any(p in text for p in login_patterns) and "프로필" not in text and "Profile" not in text:
        return "LOGIN_REQUIRED"

    return None


def extract_followers_from_profile(page, username: str) -> str:
    username_key = normalize_username(username)
    candidates = []

    for selector in ['a[href*="/followers"]', 'a[href*="/verified_followers"]']:
        try:
            links = page.query_selector_all(selector)
        except Exception:
            links = []

        for link in links:
            href = (link.get_attribute("href") or "").lower()
            if username_key in href or "/followers" in href or "/verified_followers" in href:
                candidates.append(link)

    for link in candidates:
        try:
            text = link.inner_text(timeout=2000).strip()
        except Exception:
            text = ""

        count = parse_count(text)
        if count.isdigit():
            return count

    body = get_body_text(page)
    patterns = [
        r"([\d,.]+(?:\.\d+)?\s*[KMB]?)\s+Followers",
        r"팔로워\s*([\d,.]+(?:\.\d+)?\s*(?:천|만|억)?)",
        r"([\d,.]+(?:\.\d+)?\s*(?:천|만|억)?)\s*팔로워",
    ]

    for pat in patterns:
        m = re.search(pat, body, re.IGNORECASE)
        if m:
            count = parse_count(m.group(1))
            if count.isdigit():
                return count

    return ""


def click_retry_button_if_present(page):
    selectors = [
        'button:has-text("Retry")',
        'div[role="button"]:has-text("Retry")',
        'span:has-text("Retry")',
        'button:has-text("다시 시도")',
        'div[role="button"]:has-text("다시 시도")',
        'span:has-text("다시 시도")',
    ]

    for selector in selectors:
        try:
            locator = page.locator(selector).first
            if locator.count() > 0 and locator.is_visible():
                locator.click(timeout=3000)
                time.sleep(5)
                return True
        except Exception:
            continue

    return False


def open_profile_once(page, username: str, goto_wait: float) -> str:
    try:
        try:
            page.evaluate("window.stop()")
        except Exception:
            pass

        page.goto(PROFILE_URL.format(username=username), wait_until="domcontentloaded", timeout=30000)
        time.sleep(goto_wait)

        body_text = get_body_text(page)

        detected = detect_status_from_body(body_text)
        if detected:
            return detected

        if page.query_selector('[data-testid="error-detail"]'):
            return "ERROR_DETAIL"

        followers = extract_followers_from_profile(page, username)
        if followers.isdigit():
            return followers

        time.sleep(1.5)
        body_text = get_body_text(page)

        detected = detect_status_from_body(body_text)
        if detected:
            return detected

        followers = extract_followers_from_profile(page, username)
        if followers.isdigit():
            return followers

        return "NO_FOLLOWER_TEXT"

    except PlaywrightTimeout:
        return "TIMEOUT"
    except Exception as e:
        return f"ERROR:{str(e)[:120]}"


def recover_x(page, cooldown: int, goto_wait: float):
    print(f"  [RECOVER] X 로딩 불안정 감지 -> {cooldown}초 대기")
    time.sleep(cooldown)

    try:
        page.evaluate("window.stop()")
    except Exception:
        pass

    try:
        print("  [RECOVER] 1차: 현재 페이지 새로고침")
        page.reload(wait_until="domcontentloaded", timeout=30000)
        time.sleep(max(goto_wait, 4))
    except Exception as e:
        print(f"  [RECOVER] 새로고침 오류: {str(e)[:80]}")

    try:
        print("  [RECOVER] 2차: x.com/home 진입")
        page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=30000)
        time.sleep(max(goto_wait, 5))
    except Exception as e:
        print(f"  [RECOVER] home 진입 오류: {str(e)[:80]}")

    try:
        clicked = click_retry_button_if_present(page)
        if clicked:
            print("  [RECOVER] Retry 버튼 클릭")
    except Exception:
        pass


def collect_one_with_recovery(page, username: str, args) -> str:
    for attempt in range(1, args.per_account_retries + 1):
        result = open_profile_once(page, username, args.goto_wait)

        if not is_ambiguous_failure(result):
            return result

        print(f"  [TRY] @{username:<20} attempt {attempt}/{args.per_account_retries} -> {result}")

        # X_STUCK는 검은 X 로고/빈 화면 상태라서 기다려도 잘 회복되지 않음.
        # 시간 낭비를 막기 위해 즉시 반환하고 main에서 안전 중단 처리한다.
        if result == "X_STUCK":
            return result

        # NO_FOLLOWER_TEXT/TIMEOUT/ERROR_DETAIL 정도만 복구 시도
        if attempt < args.per_account_retries:
            recover_x(page, args.cooldown, args.goto_wait)

    return result


def read_start_time():
    p = Path(START_TIME_FILE)

    if p.exists():
        try:
            txt = p.read_text(encoding="utf-8").strip()
            return datetime.strptime(txt, "%Y-%m-%d %H:%M:%S"), False
        except Exception:
            pass

    dt = datetime.now()
    p.write_text(dt.strftime("%Y-%m-%d %H:%M:%S"), encoding="utf-8")
    return dt, True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=DEFAULT_INPUT)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--cdp", default=DEFAULT_CDP)
    parser.add_argument("--delay", type=float, default=2.0)
    parser.add_argument("--goto-wait", type=float, default=3.0)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--cooldown", type=int, default=90)
    parser.add_argument("--per-account-retries", type=int, default=2)
    parser.add_argument("--max-consecutive-fail", type=int, default=5)
    parser.add_argument("--no-fail-debug", action="store_true")
    args = parser.parse_args()

    print("=" * 80)
    print("X 팔로워 수 수집 - 기존 결과 이어서 진행")
    print("=" * 80)
    print(f"현재 시각: {now_text()}")
    print(f"입력 CSV: {args.input}")
    print(f"결과 CSV: {args.output}")
    print(f"CDP 주소: {args.cdp}")
    print()

    print("[1/4] 입력 CSV 로드")
    users = load_users(args.input)
    print(f"  X URL 보유자 unique username: {len(users)}명")

    print("[2/4] 기존 완료 결과 확인")
    done = load_done(args.output)
    print(f"  이미 완료된 username: {len(done)}명")
    print("  완료 기준: 숫자 팔로워 수 + NOT_FOUND + SUSPENDED")
    print("  NO_FOLLOWER_TEXT / TIMEOUT / ERROR 는 저장하지 않고 다음 실행 때 재시도")

    todo = [u for u in users[args.start:] if normalize_username(u["username"]) not in done]

    if args.limit > 0:
        todo = todo[:args.limit]

    print(f"  이번 실행 대상: {len(todo)}명")

    print("[3/4] 시작 시각")
    start_dt, is_new = read_start_time()
    label = "새로 기록" if is_new else "이전 실행 기록"
    print(f"  최초 시작 시각: {start_dt.strftime('%Y-%m-%d %H:%M:%S')} ({label})")
    print()

    if not todo:
        print("처리할 대상이 없습니다.")
        return

    fieldnames = ["channel_id", "streamer_name", "username", "twitter_url", "followers_count"]
    write_header = not Path(args.output).exists()

    out_f = open(args.output, "a", encoding="utf-8-sig", newline="")
    writer = csv.DictWriter(out_f, fieldnames=fieldnames)

    if write_header:
        writer.writeheader()

    success = 0
    final_fail = 0
    ambiguous_fail = 0
    status_counts = {}
    consecutive_ambiguous = 0
    batch_start = time.time()

    print("[4/4] Chrome CDP 연결")
    print("  Chrome을 --remote-debugging-port=9222 옵션으로 열고 X 로그인 상태여야 합니다.")

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(args.cdp)

        if not browser.contexts:
            raise RuntimeError("연결된 브라우저 컨텍스트가 없습니다. 디버그 Chrome을 확인하세요.")

        context = browser.contexts[0]
        page = context.new_page()

        try:
            print()

            for i, user in enumerate(todo, start=1):
                uname = user["username"]
                result = collect_one_with_recovery(page, uname, args)

                if is_ambiguous_failure(result):
                    consecutive_ambiguous += 1
                    ambiguous_fail += 1
                    status = result.split(":")[0]
                    status_counts[status] = status_counts.get(status, 0) + 1

                    print(f"  [{i}/{len(todo)}] ?? @{uname:<20} -> {result} (저장 안 함)")

                    if not args.no_fail_debug:
                        save_debug(page, uname, status)

                    # X_STUCK는 보통 브라우저/X 세션 자체가 먹통인 상태.
                    # 다음 계정으로 넘어가도 줄줄이 실패하므로 즉시 안전 중단.
                    if result == "X_STUCK":
                        print()
                        print("=" * 80)
                        print("안전 중단")
                        print("=" * 80)
                        print("X_STUCK가 발생했습니다. Chrome/X 세션이 먹통일 가능성이 높아 즉시 중단합니다.")
                        print(f"마지막 계정: @{uname} -> {result}")
                        print("이 계정은 결과 CSV에 저장하지 않았고, Chrome 재시작 후 다음 실행 때 다시 시도됩니다.")
                        break

                    if consecutive_ambiguous >= args.max_consecutive_fail:
                        print()
                        print("=" * 80)
                        print("안전 중단")
                        print("=" * 80)
                        print(f"애매한 실패가 {consecutive_ambiguous}회 연속 발생했습니다.")
                        print(f"마지막 계정: @{uname} -> {result}")
                        print("이 계정은 결과 CSV에 저장하지 않았고, 다음 실행 때 다시 시도됩니다.")
                        break

                else:
                    consecutive_ambiguous = 0

                    if result.isdigit():
                        mark = "OK"
                        success += 1
                        save_value = result
                        status = "OK"
                    elif result in DONE_STATUSES:
                        mark = "XX"
                        final_fail += 1
                        save_value = result
                        status = result
                    else:
                        # 이론상 거의 안 옴. 그래도 애매한 건 저장 안 함.
                        mark = "??"
                        ambiguous_fail += 1
                        status = result
                        save_value = ""

                    if save_value:
                        writer.writerow({**user, "followers_count": save_value})
                        out_f.flush()

                    status_counts[status] = status_counts.get(status, 0) + 1
                    print(f"  [{i}/{len(todo)}] {mark} @{uname:<20} -> {save_value or result}")

                if i % 10 == 0 or i == len(todo):
                    elapsed = time.time() - batch_start
                    remaining = len(todo) - i
                    per_item = elapsed / max(1, min(10, i))
                    eta_sec = int(per_item * remaining)
                    eh, er = divmod(eta_sec, 3600)
                    em, es = divmod(er, 60)

                    print(
                        f"  -- 진행 {i}/{len(todo)} | 성공 {success} / 확정실패 {final_fail} / 애매실패 {ambiguous_fail} "
                        f"| 남은 예상 {eh}시간 {em}분 {es}초 --"
                    )
                    print(f"  -- 상태별: {status_counts} --")
                    batch_start = time.time()

                if i < len(todo):
                    time.sleep(args.delay + random.uniform(0, 0.4))

        finally:
            try:
                page.close()
            except Exception:
                pass

    out_f.close()

    end_dt = datetime.now()
    elapsed_total = end_dt - start_dt
    h, rem = divmod(int(elapsed_total.total_seconds()), 3600)
    m, s = divmod(rem, 60)

    # 중간 안전중단이어도 시작시간 파일은 지우지 않음.
    # 전체 완료 여부를 정확히 알기 어렵기 때문에 사용자가 필요 시 직접 삭제.
    if len(todo) == 0:
        try:
            Path(START_TIME_FILE).unlink(missing_ok=True)
        except Exception:
            pass

    print()
    print("=" * 80)
    print("수집 종료")
    print("=" * 80)
    print(f"성공: {success}명")
    print(f"확정 실패: {final_fail}명")
    print(f"애매 실패 저장 안 함: {ambiguous_fail}명")
    print(f"상태별: {status_counts}")
    print(f"결과 파일: {Path(args.output).resolve()}")
    print(f"시작 시각: {start_dt.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"종료 시각: {end_dt.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"소요 시간: {h}시간 {m}분 {s}초")


if __name__ == "__main__":
    main()
