# -*- coding: utf-8 -*-
"""
방송국 URL에서 유튜브 URL + 구독자 수 수집

설계 반영
- youtube_url / youtube_subscribers 없는 행만 수집
- platform이 트위치, 유튜브, 씨미/ci.me/cime 인 행 제외
- 방송국에서 유튜브 URL 후보 확인
- 후보 1개: OK
- 후보 2개 이상: CHECK 표기 후 후보 전체 저장
- 유튜브 URL을 못 찾으면 youtube_url=NOT_FOUND, status=NOT
- 크롤링 중 에러는 status=ERROR로 남기고 youtube_url은 비워둠 → 재실행 시 다시 시도
- 이미 OK/CHECK/NOT 등 처리된 행은 기본적으로 건너뜀
- 단, youtube_url은 있는데 youtube_subscribers가 비어 있으면 유튜브만 열어서 구독자 수 보강
"""

import argparse
import json
import re
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, unquote

import pandas as pd
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

DEFAULT_INPUT = "bj_links_merged_final_with_followers_1p_검증분담표.csv"
DEFAULT_OUTPUT = "bj_links_youtube_url_subscribers_collected.csv"

EXCLUDE_PLATFORM_KEYWORDS = [
    "트위치", "twitch",
    "유튜브", "youtube",
    "씨미", "cime", "ci.me",
]

YOUTUBE_BAD_URL_KEYWORDS = [
    "youtube.com/musicpremium",
    "youtube.com/premium",
    "youtube.com/feed/",
    "youtube.com/account",
    "youtube.com/playlist?list=WL",
    "youtube.com/shorts/",
    "youtube.com/watch?",
    "youtube.com/results?",
]

CORPORATE_KEYWORDS = [
    "official", "offi", "studio", "스튜디오", "company", "corp", "기업",
    "hades", "하데스", "kevin", "케빈",
]


def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def is_missing_value(v):
    if pd.isna(v):
        return True
    s = str(v).strip()
    return s == "" or s.lower() in {"nan", "none", "null", "<na>"}


def is_not_found_value(v):
    return str(v).strip().upper() == "NOT_FOUND"


def is_youtube_url(url):
    if is_missing_value(url):
        return False
    u = str(url).strip().lower()
    return "youtube.com" in u or "youtu.be" in u


def is_excluded_platform(platform):
    p = "" if pd.isna(platform) else str(platform).strip().lower()
    return any(k in p for k in EXCLUDE_PLATFORM_KEYWORDS)


def clean_url(url):
    if not url:
        return ""
    url = str(url).strip()
    url = url.replace("\\u0026", "&")
    url = unquote(url)
    url = url.replace("\uFFFD", "")
    url = url.rstrip("/) \t\r\n")
    return url


def normalize_youtube_url(url):
    url = clean_url(url)
    if not is_youtube_url(url):
        return ""

    # 흔한 추적 파라미터 제거. 단 @핸들 한글 URL은 유지.
    url = url.replace("m.youtube.com", "www.youtube.com")

    # /featured, /videos 등은 채널 홈으로 정리
    url = re.sub(r"/(featured|videos|shorts|streams|playlists|community)$", "", url)

    return url


def is_bad_youtube_url(url):
    u = str(url).lower()
    return any(bad in u for bad in YOUTUBE_BAD_URL_KEYWORDS)


def dedupe_keep_order(items):
    seen = set()
    out = []
    for x in items:
        x = normalize_youtube_url(x)
        if not x:
            continue
        key = x.split("?")[0].rstrip("/")
        if key in seen:
            continue
        seen.add(key)
        out.append(x)
    return out


def parse_count_to_int(text):
    """23.8만 -> 238000, 6.8천 -> 6800, 1.56M -> 1560000"""
    if not text:
        return ""
    s = str(text).strip().replace(",", "")
    m = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*([만천억KkMm]?)", s)
    if not m:
        return ""
    num = float(m.group(1))
    unit = m.group(2)
    if unit == "억":
        num *= 100000000
    elif unit == "만":
        num *= 10000
    elif unit == "천":
        num *= 1000
    elif unit in ["K", "k"]:
        num *= 1000
    elif unit in ["M", "m"]:
        num *= 1000000
    return int(num)


def extract_subscriber_from_text(body_text):
    if not body_text:
        return ""

    # 한국어 UI: @handle · 구독자 6.8천명 · 동영상 10개
    patterns = [
        r"구독자\s*([0-9.,]+\s*[만천억KkMm]?)\s*명",
        r"([0-9.,]+\s*[만천억KkMm]?)\s*명의\s*구독자",
        r"([0-9.,]+\s*[KkMm]?)\s*subscribers",
    ]
    for pat in patterns:
        m = re.search(pat, body_text, flags=re.IGNORECASE)
        if m:
            return parse_count_to_int(m.group(1))
    return ""


def get_youtube_info(page, youtube_url, wait_sec=4):
    result = {
        "url": youtube_url,
        "channel_name": "",
        "subscribers": "",
        "status": "",
    }
    try:
        page.goto(youtube_url, wait_until="domcontentloaded", timeout=45000)
        time.sleep(wait_sec)

        # 가끔 consent/로딩 때문에 한 번 더 대기
        try:
            page.wait_for_load_state("networkidle", timeout=8000)
        except Exception:
            pass

        title = ""
        try:
            title = page.title().replace(" - YouTube", "").strip()
        except Exception:
            pass

        body = ""
        try:
            body = page.locator("body").inner_text(timeout=10000)
        except Exception:
            body = ""

        subscriber_count = extract_subscriber_from_text(body)

        # 채널명 보강: body의 첫쪽 제목 느낌 추출보다 title이 대체로 안정적
        channel_name = title
        if channel_name in ["YouTube", "404 Not Found", ""]:
            # body 초반 줄 중 쓸만한 첫 줄 선택
            for line in body.splitlines()[:30]:
                line = line.strip()
                if line and line not in {"홈", "동영상", "Shorts", "재생목록", "검색"}:
                    if "구독자" not in line and "동영상" not in line:
                        channel_name = line
                        break

        result["channel_name"] = channel_name
        result["subscribers"] = subscriber_count

        if subscriber_count != "":
            result["status"] = "subscriber_ok"
        else:
            result["status"] = "subscriber_not_found"
        return result

    except Exception as e:
        result["status"] = f"youtube_error: {type(e).__name__}: {e}"
        return result


def extract_youtube_links_from_page(page):
    links = []

    # href 추출
    try:
        hrefs = page.locator("a").evaluate_all("els => els.map(a => a.href).filter(Boolean)")
        links.extend(hrefs)
    except Exception:
        pass

    # html/text 안에 박힌 URL 추출
    try:
        html = page.content()
        links.extend(re.findall(r"https?://(?:www\.|m\.)?(?:youtube\.com|youtu\.be)[^\"'<>\s]+", html))
    except Exception:
        pass

    # data 속성류에서 뽑히는 경우
    try:
        all_attrs = page.locator("a, button").evaluate_all(
            """
            els => els.map(el => [
                el.href || '',
                el.getAttribute('data-url') || '',
                el.getAttribute('data-href') || '',
                el.getAttribute('onclick') || '',
                el.getAttribute('aria-label') || '',
                el.title || '',
                el.outerHTML || ''
            ].join(' '))
            """
        )
        for s in all_attrs:
            links.extend(re.findall(r"https?://(?:www\.|m\.)?(?:youtube\.com|youtu\.be)[^\"'<>\s]+", s))
    except Exception:
        pass

    links = [x for x in dedupe_keep_order(links) if not is_bad_youtube_url(x)]
    return links


def click_youtube_like_icons_and_collect(context, page, max_clicks=25):
    """href에 안 보이고 아이콘 클릭으로만 열리는 유튜브 링크 수집."""
    found = []

    try:
        candidates = page.locator("a, button").all()
    except Exception:
        return found

    clicked = 0
    original_url = page.url

    for el in candidates:
        if clicked >= max_clicks:
            break
        try:
            if not el.is_visible(timeout=500):
                continue
            box = el.bounding_box(timeout=500)
            if not box:
                continue

            # 너무 큰 영역/VOD/검색/메뉴 버튼 클릭 방지
            w, h = box.get("width", 0), box.get("height", 0)
            x, y = box.get("x", 0), box.get("y", 0)
            if w > 90 or h > 90:
                continue
            if y < 120:
                continue
            # SOOP/CHZZK 상단 외부 링크 아이콘은 보통 배너 아래~프로필 영역에 있음
            # VOD 카드 버튼을 줄이기 위해 너무 아래쪽은 제외
            if y > 650:
                continue

            label = ""
            try:
                label = el.evaluate("el => [el.innerText, el.title, el.getAttribute('aria-label'), el.outerHTML].join(' ')") or ""
            except Exception:
                pass

            # youtube 단서가 있거나, 작은 원형 SNS 아이콘일 가능성이 있는 버튼만 클릭
            lower = label.lower()
            if ("youtube" not in lower and "youtu" not in lower and "유튜브" not in lower):
                # 아이콘만 있는 경우 label이 비어 있을 수 있음. 좌측 프로필/배너 아래쪽 작은 버튼만 허용.
                if not (200 <= x <= 520 and 250 <= y <= 560 and w <= 60 and h <= 60):
                    continue

            before_pages = set(context.pages)
            before_url = page.url

            try:
                with context.expect_page(timeout=3000) as new_page_info:
                    el.click(timeout=1000, force=True)
                new_page = new_page_info.value
                try:
                    new_page.wait_for_load_state("domcontentloaded", timeout=8000)
                except Exception:
                    pass
                new_url = new_page.url
                if is_youtube_url(new_url) and not is_bad_youtube_url(new_url):
                    found.append(new_url)
                new_page.close()
                clicked += 1
                continue
            except PlaywrightTimeoutError:
                # 같은 탭 이동 가능성
                try:
                    time.sleep(1)
                    new_url = page.url
                    if new_url != before_url:
                        if is_youtube_url(new_url) and not is_bad_youtube_url(new_url):
                            found.append(new_url)
                        page.goto(original_url, wait_until="domcontentloaded", timeout=30000)
                        time.sleep(1)
                    clicked += 1
                except Exception:
                    try:
                        page.goto(original_url, wait_until="domcontentloaded", timeout=30000)
                    except Exception:
                        pass
            except Exception:
                # 클릭 실패는 그냥 다음 후보
                pass

            # 혹시 추가로 뜬 페이지 정리
            for pg in list(context.pages):
                if pg not in before_pages and pg != page:
                    try:
                        if is_youtube_url(pg.url) and not is_bad_youtube_url(pg.url):
                            found.append(pg.url)
                        pg.close()
                    except Exception:
                        pass

        except Exception:
            continue

    return dedupe_keep_order([x for x in found if not is_bad_youtube_url(x)])


def collect_youtube_candidates_from_broadcast(context, page, broadcast_url, wait_sec=2):
    page.goto(broadcast_url, wait_until="domcontentloaded", timeout=45000)
    time.sleep(wait_sec)
    try:
        page.wait_for_load_state("networkidle", timeout=6000)
    except Exception:
        pass

    links = extract_youtube_links_from_page(page)
    if not links:
        links = click_youtube_like_icons_and_collect(context, page)
    else:
        # href로 일부 보였어도 클릭 전용 아이콘이 더 있을 수 있어 추가 확인
        more = click_youtube_like_icons_and_collect(context, page)
        links = dedupe_keep_order(links + more)

    return [x for x in links if not is_bad_youtube_url(x)]


def simple_name_match(streamer_name, channel_name, url):
    s = "" if pd.isna(streamer_name) else str(streamer_name)
    c = "" if channel_name is None else str(channel_name)
    u = "" if url is None else str(url)
    # 특수문자 제거한 약식 비교
    def norm(x):
        return re.sub(r"[^0-9a-zA-Z가-힣]", "", x).lower()
    ns = norm(s)
    nc = norm(c + u)
    if len(ns) >= 2 and ns in nc:
        return True
    return False


def corporate_like(channel_name, url):
    text = f"{channel_name} {url}".lower()
    return any(k.lower() in text for k in CORPORATE_KEYWORDS)


def choose_candidate(candidates_info, streamer_name):
    """자동 선택은 하되, 2개 이상이면 무조건 CHECK 남김."""
    if not candidates_info:
        return None

    # 본인명 매칭 후보 우선, 그 다음 기업/소속사스러운 후보 제외, 그 다음 구독자수 높은 후보
    enriched = []
    for info in candidates_info:
        subs = info.get("subscribers", "")
        subs_num = int(subs) if str(subs).isdigit() else -1
        nm = simple_name_match(streamer_name, info.get("channel_name", ""), info.get("url", ""))
        corp = corporate_like(info.get("channel_name", ""), info.get("url", ""))
        enriched.append((nm, not corp, subs_num, info))

    enriched.sort(key=lambda x: (x[0], x[1], x[2]), reverse=True)
    return enriched[0][3]


def ensure_columns(df):
    needed = {
        "youtube_url": "",
        "youtube_subscribers": "",
        "youtube_collect_status": "",
        "youtube_collected_at": "",
        "youtube_candidates": "",
    }

    # 이전 버전에서 생겼던 불필요 컬럼은 결과 파일에서 제거
    drop_cols = [
        "youtube_channel_name",
        "youtube_candidate_count",
        "youtube_manual_check",
        "youtube_manual_check_reason",
    ]
    df = df.drop(columns=[c for c in drop_cols if c in df.columns])

    for col, default in needed.items():
        if col not in df.columns:
            df[col] = default
        df[col] = df[col].astype("object")
    return df


def row_needs_processing(row, retry_not_found=False, force=False):
    if force:
        return True

    platform = row.get("platform", "")
    if is_excluded_platform(platform):
        return False

    broadcast_url = row.get("broadcast_url", "")
    if is_missing_value(broadcast_url):
        return False

    youtube_url = row.get("youtube_url", "")
    subs = row.get("youtube_subscribers", "")
    status = row.get("youtube_collect_status", "")

    # 크롤링 중 에러난 건 재실행 시 다시 시도
    if str(status).startswith("ERROR"):
        return True

    # 이미 URL이 있고 구독자만 비어 있으면 구독자 보강
    if is_youtube_url(youtube_url) and is_missing_value(subs):
        return True

    # URL 없음 / 기존 원본 결측이면 수집 대상
    if is_missing_value(youtube_url):
        return True

    # NOT_FOUND는 기본 skip, 옵션으로 재시도
    if is_not_found_value(youtube_url):
        return retry_not_found

    return False


def format_candidates(candidates_info, streamer_name):
    parts = []
    for info in candidates_info:
        nm = simple_name_match(streamer_name, info.get("channel_name", ""), info.get("url", ""))
        corp = corporate_like(info.get("channel_name", ""), info.get("url", ""))
        parts.append({
            "url": info.get("url", ""),
            "channel_name": info.get("channel_name", ""),
            "subscribers": info.get("subscribers", ""),
            "status": info.get("status", ""),
            "name_match": nm,
            "corporate_like": corp,
        })
    return json.dumps(parts, ensure_ascii=False)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=DEFAULT_INPUT)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--max-rows", type=int, default=None)
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--retry-not-found", action="store_true")
    parser.add_argument("--force", action="store_true", help="이미 처리된 행도 다시 처리")
    parser.add_argument("--delay", type=float, default=2.0)
    parser.add_argument("--youtube-wait", type=float, default=4.0)
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    if output_path.exists():
        print(f"[이어하기] 기존 출력 파일을 읽습니다: {output_path}")
        df = pd.read_csv(output_path, dtype="object", encoding="utf-8-sig")
    else:
        print(f"[새로 시작] 입력 파일을 읽습니다: {input_path}")
        df = pd.read_csv(input_path, dtype="object", encoding="utf-8-sig")

    df = ensure_columns(df)

    target_indices = [
        idx for idx, row in df.iterrows()
        if row_needs_processing(row, retry_not_found=args.retry_not_found, force=args.force)
    ]

    if args.max_rows is not None:
        target_indices = target_indices[:args.max_rows]

    print("=" * 70)
    print("유튜브 URL / 구독자 수 수집 시작")
    print(f"입력 파일: {input_path}")
    print(f"출력 파일: {output_path}")
    print(f"전체 행 수: {len(df)}")
    print(f"처리 대상 수: {len(target_indices)}")
    print("=" * 70)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=args.headless)
        context = browser.new_context(
            viewport={"width": 1400, "height": 950},
            locale="ko-KR",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()
        youtube_page = context.new_page()

        for n, idx in enumerate(target_indices, start=1):
            row = df.loc[idx]
            streamer_name = row.get("streamer_name", "")
            platform = row.get("platform", "")
            broadcast_url = row.get("broadcast_url", "")
            current_youtube_url = row.get("youtube_url", "")

            print(f"\n[{n}/{len(target_indices)}] index={idx} | {platform} | {streamer_name}")
            print(f"방송국: {broadcast_url}")

            try:
                # 이미 유튜브 URL이 있는데 구독자만 비어 있는 경우: 방송국 재방문 없이 구독자만 보강
                if is_youtube_url(current_youtube_url) and is_missing_value(row.get("youtube_subscribers", "")):
                    info = get_youtube_info(youtube_page, current_youtube_url, wait_sec=args.youtube_wait)
                    if info.get("subscribers", "") != "":
                        df.at[idx, "youtube_subscribers"] = str(info["subscribers"])
                        df.at[idx, "youtube_collect_status"] = "OK"
                    else:
                        df.at[idx, "youtube_collect_status"] = "OK_SUBSCRIBER_NOT_FOUND"
                    df.at[idx, "youtube_collected_at"] = now_str()
                    df.at[idx, "youtube_candidates"] = format_candidates([info], streamer_name)
                    print(f"유튜브: {current_youtube_url}")
                    print(f"구독자: {info.get('subscribers', '')}")
                    print(f"상태: {df.at[idx, 'youtube_collect_status']}")
                    df.to_csv(output_path, index=False, encoding="utf-8-sig")
                    continue

                # 방송국에서 유튜브 후보 찾기
                candidates = collect_youtube_candidates_from_broadcast(
                    context, page, broadcast_url, wait_sec=args.delay
                )

                if not candidates:
                    df.at[idx, "youtube_url"] = "NOT_FOUND"
                    df.at[idx, "youtube_subscribers"] = ""
                    df.at[idx, "youtube_collect_status"] = "NOT"
                    df.at[idx, "youtube_candidates"] = ""
                    df.at[idx, "youtube_collected_at"] = now_str()
                    print("상태: NOT / 유튜브 URL 못 찾음")
                    df.to_csv(output_path, index=False, encoding="utf-8-sig")
                    continue

                candidates_info = []
                for yurl in candidates:
                    info = get_youtube_info(youtube_page, yurl, wait_sec=args.youtube_wait)
                    candidates_info.append(info)

                chosen = choose_candidate(candidates_info, streamer_name)
                if chosen is None:
                    df.at[idx, "youtube_url"] = "NOT_FOUND"
                    df.at[idx, "youtube_collect_status"] = "NOT"
                else:
                    df.at[idx, "youtube_url"] = chosen.get("url", "")
                    if chosen.get("subscribers", "") != "":
                        df.at[idx, "youtube_subscribers"] = str(chosen["subscribers"])
                    else:
                        df.at[idx, "youtube_subscribers"] = ""

                    if len(candidates_info) >= 2:
                        df.at[idx, "youtube_collect_status"] = "CHECK"
                    else:
                        if chosen.get("subscribers", "") != "":
                            df.at[idx, "youtube_collect_status"] = "OK"
                        else:
                            df.at[idx, "youtube_collect_status"] = "OK_SUBSCRIBER_NOT_FOUND"
        
                df.at[idx, "youtube_candidates"] = format_candidates(candidates_info, streamer_name)
                df.at[idx, "youtube_collected_at"] = now_str()

                print(f"후보 수: {len(candidates_info)}")
                print(f"유튜브: {df.at[idx, 'youtube_url']}")
                print(f"구독자: {df.at[idx, 'youtube_subscribers']}")
                print(f"상태: {df.at[idx, 'youtube_collect_status']}")

                df.to_csv(output_path, index=False, encoding="utf-8-sig")

            except Exception as e:
                # ERROR는 url을 비워둬서 다음 실행 때 재시도 가능하게 함
                df.at[idx, "youtube_url"] = ""
                df.at[idx, "youtube_collect_status"] = f"ERROR: {type(e).__name__}: {e}"
                df.at[idx, "youtube_collected_at"] = now_str()
                print(f"상태: ERROR / {type(e).__name__}: {e}")
                df.to_csv(output_path, index=False, encoding="utf-8-sig")
                continue

        browser.close()

    print("\n" + "=" * 70)
    print("완료")
    print(f"저장 파일: {output_path}")
    print("=" * 70)


if __name__ == "__main__":
    main()
