import csv
from datetime import datetime, timedelta, timezone
from urllib.parse import quote
from pathlib import Path
import time
import re

from playwright.sync_api import sync_playwright

# -----------------------------
# 설정값
# -----------------------------
# 최종 저장 파일명 앞에 붙일 스트리머명
STREAMER_NAME = "hanaco_nana"

# 검색할 해시태그 목록
HASHTAGS = ["#Nanart_", "#nanaclip_", "#nanaiary"]

# 최종 분석 대상으로 남길 날짜 범위 (KST 기준, 포함 범위)
FINAL_FILTER_START = "2026-03-01"
FINAL_FILTER_END = "2026-03-31"

# 검색 구간을 몇 일 단위로 나눌지(왠만하면유지하세요)
RANGE_STEP_DAYS = 2

# 시간대 설정
UTC = timezone.utc
KST = timezone(timedelta(hours=9))

# 현재 파이썬 파일이 있는 폴더를 기준 저장 경로로 사용
BASE_DIR = Path(__file__).resolve().parent

# 스크롤 종료 조건 관련 설정
MAX_NO_CHANGE = 8
SCROLL_WAIT_MS = 5000
INITIAL_WAIT_MS = 7000


def safe_text(locator):
    """locator에서 텍스트를 안전하게 읽어오고 실패 시 빈 문자열 반환"""
    try:
        return locator.inner_text().strip()
    except:
        return ""


def safe_attr(locator, name):
    """locator의 속성을 안전하게 읽어오고 실패 시 None 반환"""
    try:
        return locator.get_attribute(name)
    except:
        return None


def clean_text(text: str) -> str:
    """줄바꿈/여러 공백을 한 칸으로 정리"""
    if not text:
        return ""
    return " ".join(text.replace("\n", " ").split())


def sanitize_filename_part(text: str) -> str:
    """
    파일명에 넣기 어려운 문자 제거/치환
    예: #Nanart_ -> Nanart_
    """
    if not text:
        return ""

    text = text.strip()

    if text.startswith("#"):
        text = text[1:]

    text = re.sub(r'[\\/:*?"<>|]+', "_", text)
    text = re.sub(r"\s+", "_", text)
    text = text.strip("._")

    return text


def make_streamer_label(streamer_name: str) -> str:
    """스트리머명을 파일명용 문자열로 변환"""
    label = sanitize_filename_part(streamer_name)
    return label if label else "streamer"


def make_hashtag_label(hashtags):
    """해시태그 리스트를 파일명용 문자열로 변환"""
    cleaned_tags = []

    for tag in hashtags:
        cleaned = sanitize_filename_part(tag)
        if cleaned:
            cleaned_tags.append(cleaned)

    if not cleaned_tags:
        return "hashtags"

    label = "_".join(cleaned_tags)

    # 파일명이 너무 길어지는 것을 방지
    if len(label) > 80:
        label = label[:80]

    return label


def make_date_range_label(start_date: str, end_date: str) -> str:
    """최종 파일명에 넣을 날짜 범위 라벨 생성"""
    return f"{start_date}_to_{end_date}"


def generate_date_ranges(final_start: str, final_end: str, step_days: int = 2):
    """
    KST 기준 최종 분석 범위를 받아,
    UTC/KST 경계로 인한 누락을 줄이기 위해 앞 1일, 뒤 1일 버퍼를 둔 검색 구간 생성

    예:
    final_start = 2026-03-01
    final_end   = 2026-03-31

    -> 검색 범위는 2026-02-28 ~ 2026-04-01(until 미포함)
    """
    start_dt = datetime.strptime(final_start, "%Y-%m-%d") - timedelta(days=1)
    end_dt_exclusive = datetime.strptime(final_end, "%Y-%m-%d") + timedelta(days=1)

    ranges = []
    current = start_dt

    while current < end_dt_exclusive:
        next_dt = current + timedelta(days=step_days)
        if next_dt > end_dt_exclusive:
            next_dt = end_dt_exclusive

        ranges.append((
            current.strftime("%Y-%m-%d"),
            next_dt.strftime("%Y-%m-%d"),
        ))
        current = next_dt

    return ranges


def build_search_url(hashtags, start_date: str, end_date: str) -> str:
    """X 고급 검색용 live URL 생성"""
    hashtag_query = " OR ".join(hashtags)
    query_text = f"({hashtag_query}) since:{start_date} until:{end_date}"
    query = quote(query_text)
    return f"https://x.com/search?q={query}&src=typed_query&f=live"


def parse_count_text(text: str) -> str:
    """좋아요/리포스트/조회수 등의 텍스트를 정리"""
    return clean_text(text)


def utc_to_kst_string(utc_text: str) -> str:
    """
    예:
    2026-03-01T06:32:57.000Z
    2026-03-01T06:32:57Z
    2026-03-01T06:32:57+00:00

    -> 2026-03-01 15:32:57
    """
    if not utc_text:
        return ""

    try:
        dt_utc = datetime.fromisoformat(utc_text.replace("Z", "+00:00"))
        dt_kst = dt_utc.astimezone(KST)
        return dt_kst.strftime("%Y-%m-%d %H:%M:%S")
    except:
        return utc_text


def extract_date_only(post_time: str) -> str:
    """
    KST 문자열 'YYYY-MM-DD HH:MM:SS' 에서 날짜만 추출
    예외적으로 기존 ISO 형식이어도 앞 10글자로 처리 가능하게 보완
    """
    if not post_time:
        return ""

    if " " in post_time:
        return post_time.split(" ")[0]

    return post_time[:10]


def get_oldest_post_date(collected):
    """현재까지 수집한 게시물 중 가장 오래된 날짜 확인"""
    dates = []

    for post in collected:
        post_time = post.get("post_time", "")
        date_only = extract_date_only(post_time)
        if date_only:
            dates.append(date_only)

    if not dates:
        return "없음"

    return min(dates)


def filter_posts_by_date_range(posts, start_date: str, end_date: str):
    """
    KST 기준 post_time 날짜가 start_date ~ end_date(포함)인 게시물만 남김
    예: 2026-03-01 ~ 2026-03-31
    """
    filtered = []

    for post in posts:
        post_date = extract_date_only(post.get("post_time", ""))
        if not post_date:
            continue

        if start_date <= post_date <= end_date:
            filtered.append(post)

    return filtered


def extract_post_data(article):
    """게시물(article) 하나에서 필요한 정보 추출"""
    data = {
        "display_name": "",
        "account_id": "",
        "post_text": "",
        "post_time_utc": "",
        "post_time": "",   # KST
        "post_url": "",
        "reply_count": "",
        "repost_count": "",
        "like_count": "",
        "view_count": "",
    }

    time_locator = article.locator("time").first
    try:
        if time_locator.count() > 0:
            raw_post_time = safe_attr(time_locator, "datetime") or ""
            data["post_time_utc"] = raw_post_time
            data["post_time"] = utc_to_kst_string(raw_post_time)

            parent_a = time_locator.locator("xpath=..")
            href = safe_attr(parent_a, "href")
            if href:
                if href.startswith("http"):
                    data["post_url"] = href
                else:
                    data["post_url"] = "https://x.com" + href
    except:
        pass

    raw_article_text = safe_text(article)
    article_text = clean_text(raw_article_text)
    lines = [line.strip() for line in raw_article_text.split("\n") if line.strip()]

    if len(lines) >= 1:
        data["display_name"] = clean_text(lines[0])

    for line in lines[:10]:
        if line.startswith("@"):
            data["account_id"] = clean_text(line)
            break

    try:
        text_candidates = article.locator('[data-testid="tweetText"]')
        if text_candidates.count() > 0:
            data["post_text"] = clean_text(safe_text(text_candidates.first))
        else:
            data["post_text"] = article_text
    except:
        data["post_text"] = article_text

    try:
        reply = article.locator('[data-testid="reply"]').first
        data["reply_count"] = parse_count_text(safe_text(reply))
    except:
        pass

    try:
        repost = article.locator('[data-testid="retweet"]').first
        data["repost_count"] = parse_count_text(safe_text(repost))
    except:
        pass

    try:
        like = article.locator('[data-testid="like"]').first
        data["like_count"] = parse_count_text(safe_text(like))
    except:
        pass

    try:
        analytics_locator = article.locator('a[href*="/analytics"]').first
        if analytics_locator.count() > 0:
            analytics_text = safe_text(analytics_locator)
            data["view_count"] = parse_count_text(analytics_text)
        else:
            possible_view = article.locator('a[aria-label*="조회"], a[aria-label*="View"]').first
            data["view_count"] = parse_count_text(safe_text(possible_view))
    except:
        pass

    return data


def save_csv(file_path, rows):
    """CSV 저장"""
    with open(file_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "display_name",
                "account_id",
                "post_text",
                "post_time_utc",
                "post_time",
                "post_url",
                "reply_count",
                "repost_count",
                "like_count",
                "view_count",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def collect_posts_for_range(page, start_date, end_date, hashtags):
    """특정 날짜 구간에 대해 게시물 수집"""
    search_url = build_search_url(hashtags, start_date, end_date)

    print("\n" + "=" * 70)
    print(f"수집 시작: {start_date} ~ {end_date} (until 미포함)")
    print(f"검색 태그: {', '.join(hashtags)}")
    print(f"URL: {search_url}")
    print("=" * 70)

    page.goto(search_url, wait_until="domcontentloaded")
    page.wait_for_timeout(INITIAL_WAIT_MS)

    collected = []
    seen = set()

    no_change_count = 0
    scroll_round = 0

    while no_change_count < MAX_NO_CHANGE:
        articles = page.locator("article")
        count = articles.count()

        before_count = len(collected)

        for i in range(count):
            try:
                article = articles.nth(i)
                post = extract_post_data(article)

                url = post["post_url"]
                text = post["post_text"]

                if not url and not text:
                    continue

                    # url이 있으면 url 기준, 없으면 계정+본문 일부로 중복 제거
                unique_key = url if url else f"{post['account_id']}|{text[:50]}"
                if unique_key in seen:
                    continue

                seen.add(unique_key)
                collected.append(post)

            except Exception as e:
                print("게시물 하나 스킵:", e)

        after_count = len(collected)

        if after_count == before_count:
            no_change_count += 1
        else:
            no_change_count = 0

        scroll_round += 1
        oldest_date = get_oldest_post_date(collected)

        print(
            f"스크롤 {scroll_round}회 | "
            f"현재 수집 수: {len(collected)}개 | "
            f"가장 오래된 게시물 날짜(KST): {oldest_date} | "
            f"연속 무변화: {no_change_count}/{MAX_NO_CHANGE}"
        )

        page.mouse.wheel(0, 3000)
        page.wait_for_timeout(SCROLL_WAIT_MS)

    return collected


def main():
    total_start_time = time.time()

    streamer_label = make_streamer_label(STREAMER_NAME)
    hashtag_label = make_hashtag_label(HASHTAGS)
    date_range_label = make_date_range_label(FINAL_FILTER_START, FINAL_FILTER_END)

    date_ranges = generate_date_ranges(
        FINAL_FILTER_START,
        FINAL_FILTER_END,
        RANGE_STEP_DAYS,
    )

    print("자동 생성된 검색 구간:")
    for start_date, end_date in date_ranges:
        print(f"- {start_date} ~ {end_date} (until 미포함)")

    with sync_playwright() as p:
        # 미리 디버그 모드로 실행한 크롬에 연결
        browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")

        if not browser.contexts:
            raise RuntimeError("연결된 크롬 컨텍스트가 없습니다. 디버그 모드 크롬이 켜져 있는지 확인하세요.")

        context = browser.contexts[0]
        page = context.new_page()

        all_collected = []
        all_seen = set()

        for start_date, end_date in date_ranges:
            range_start_time = time.time()

            collected = collect_posts_for_range(page, start_date, end_date, HASHTAGS)

            added_count = 0
            for post in collected:
                unique_key = (
                    post["post_url"]
                    if post["post_url"]
                    else f"{post['account_id']}|{post['post_text'][:50]}"
                )
                if unique_key in all_seen:
                    continue
                all_seen.add(unique_key)
                all_collected.append(post)
                added_count += 1

            range_elapsed_seconds = int(time.time() - range_start_time)
            range_minutes = range_elapsed_seconds // 60
            range_seconds = range_elapsed_seconds % 60

            print(f"이 구간 합본 추가 수: {added_count}개")
            print(f"구간 소요 시간: {range_minutes}분 {range_seconds}초")

        final_filtered = filter_posts_by_date_range(
            all_collected,
            FINAL_FILTER_START,
            FINAL_FILTER_END,
        )

        final_filtered_csv = BASE_DIR / (
            f"{streamer_label}_{hashtag_label}_{date_range_label}.csv"
        )
        save_csv(final_filtered_csv, final_filtered)

        print("\n" + "=" * 70)
        print(f"최종 날짜 필터링 완료(KST 기준): {len(final_filtered)}개")
        print(f"최종 파일명: {final_filtered_csv}")

        total_elapsed_seconds = int(time.time() - total_start_time)
        total_minutes = total_elapsed_seconds // 60
        total_seconds = total_elapsed_seconds % 60

        print(f"총 소요 시간: {total_minutes}분 {total_seconds}초")
        print("=" * 70)

        page.close()


if __name__ == "__main__":
    main()
