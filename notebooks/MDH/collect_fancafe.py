"""
방송국 URL에서 팬카페 URL 수집

설계 반영
- fancafe_url 없는 행만 수집
- platform이 트위치, 유튜브, 씨미/ci.me/cime 인 행 제외
- 방송국에서 팬카페 URL 후보 확인
- 후보 1개: OK
- 후보 2개 이상: CHECK 표기 후 후보 전체 저장
- 팬카페 URL을 못 찾으면 fancafe_url=NOT_FOUND, status=NOT
- 크롤링 중 에러는 status=ERROR로 남기고 fancafe_url은 비워둠 → 재실행 시 다시 시도
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
DEFAULT_OUTPUT = "bj_links_fancafe_url_collected.csv"

EXCLUDE_PLATFORM_KEYWORDS = [
    "트위치", "twitch",
    "유튜브", "youtube",
    "씨미", "cime", "ci.me",
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

def is_fancafe_url(url):
    if is_missing_value(url):
        return False
    u = str(url).strip().lower()
    return "cafe.naver.com" in u or "cafe.daum.net" in u

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

def normalize_fancafe_url(url):
    url = clean_url(url)
    if not is_fancafe_url(url):
        return ""
    # 모바일 링크를 PC 링크로 정규화
    url = url.replace("m.cafe.naver.com", "cafe.naver.com")
    url = url.replace("m.cafe.daum.net", "cafe.daum.net")
    return url

def dedupe_keep_order(items):
    seen = set()
    out = []
    for x in items:
        x = normalize_fancafe_url(x)
        if not x:
            continue
        key = x.split("?")[0].rstrip("/")
        if key in seen:
            continue
        seen.add(key)
        out.append(x)
    return out

def extract_fancafe_links_from_page(page):
    links = []

    # 1. href 추출
    try:
        hrefs = page.locator("a").evaluate_all("els => els.map(a => a.href).filter(Boolean)")
        links.extend(hrefs)
    except Exception:
        pass

    # 2. html/text 안에 박힌 URL 추출
    try:
        html = page.content()
        links.extend(re.findall(r"https?://(?:www\.|m\.)?cafe\.(?:naver\.com|daum\.net)[^\"'<>\s]+", html))
    except Exception:
        pass

    # 3. data 속성류에서 뽑히는 경우
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
            links.extend(re.findall(r"https?://(?:www\.|m\.)?cafe\.(?:naver\.com|daum\.net)[^\"'<>\s]+", s))
    except Exception:
        pass

    return dedupe_keep_order(links)

def click_fancafe_like_icons_and_collect(context, page, max_clicks=25):
    """href에 안 보이고 아이콘 클릭으로만 열리는 팬카페 링크 수집."""
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

            # 버튼 크기 및 위치 필터링 (기존 로직 유지)
            w, h = box.get("width", 0), box.get("height", 0)
            x, y = box.get("x", 0), box.get("y", 0)
            if w > 90 or h > 90:
                continue
            if y < 120 or y > 650:
                continue

            label = ""
            try:
                label = el.evaluate("el => [el.innerText, el.title, el.getAttribute('aria-label'), el.outerHTML].join(' ')") or ""
            except Exception:
                pass

            # 팬카페 단서가 있거나, 작은 아이콘일 가능성이 있는 버튼만 클릭
            lower = label.lower()
            if ("cafe" not in lower and "카페" not in lower and "팬카페" not in lower):
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
                if is_fancafe_url(new_url):
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
                        if is_fancafe_url(new_url):
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
                pass

            # 추가로 뜬 페이지 정리
            for pg in list(context.pages):
                if pg not in before_pages and pg != page:
                    try:
                        if is_fancafe_url(pg.url):
                            found.append(pg.url)
                        pg.close()
                    except Exception:
                        pass

        except Exception:
            continue

    return dedupe_keep_order(found)

def collect_fancafe_candidates_from_broadcast(context, page, broadcast_url, wait_sec=2):
    page.goto(broadcast_url, wait_until="domcontentloaded", timeout=45000)
    time.sleep(wait_sec)
    try:
        page.wait_for_load_state("networkidle", timeout=6000)
    except Exception:
        pass

    links = extract_fancafe_links_from_page(page)
    if not links:
        links = click_fancafe_like_icons_and_collect(context, page)
    else:
        more = click_fancafe_like_icons_and_collect(context, page)
        links = dedupe_keep_order(links + more)

    return links

def ensure_columns(df):
    needed = {
        "fancafe_url": "",
        "fancafe_collect_status": "",
        "fancafe_collected_at": "",
        "fancafe_candidates": "",
    }
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

    fancafe_url = row.get("fancafe_url", "")
    status = row.get("fancafe_collect_status", "")

    # 크롤링 중 에러난 건 재실행 시 다시 시도
    if str(status).startswith("ERROR"):
        return True

    # URL 없음 처리
    if is_missing_value(fancafe_url):
        return True

    # NOT_FOUND는 기본 skip, 옵션으로 재시도
    if is_not_found_value(fancafe_url):
        return retry_not_found

    return False

def format_candidates(candidates):
    return json.dumps([{"url": url} for url in candidates], ensure_ascii=False)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=DEFAULT_INPUT)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--max-rows", type=int, default=None)
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--retry-not-found", action="store_true")
    parser.add_argument("--force", action="store_true", help="이미 처리된 행도 다시 처리")
    parser.add_argument("--delay", type=float, default=2.0)
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
    print("팬카페 URL 수집 시작")
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

        for n, idx in enumerate(target_indices, start=1):
            row = df.loc[idx]
            streamer_name = row.get("streamer_name", "")
            platform = row.get("platform", "")
            broadcast_url = row.get("broadcast_url", "")

            print(f"\n[{n}/{len(target_indices)}] index={idx} | {platform} | {streamer_name}")
            print(f"방송국: {broadcast_url}")

            try:
                candidates = collect_fancafe_candidates_from_broadcast(
                    context, page, broadcast_url, wait_sec=args.delay
                )

                if not candidates:
                    df.at[idx, "fancafe_url"] = "NOT_FOUND"
                    df.at[idx, "fancafe_collect_status"] = "NOT"
                    df.at[idx, "fancafe_candidates"] = ""
                    df.at[idx, "fancafe_collected_at"] = now_str()
                    print("상태: NOT / 팬카페 URL 못 찾음")
                    df.to_csv(output_path, index=False, encoding="utf-8-sig")
                    continue

                # 첫 번째 후보를 대표 URL로 지정
                chosen_url = candidates[0]
                df.at[idx, "fancafe_url"] = chosen_url
                
                if len(candidates) >= 2:
                    df.at[idx, "fancafe_collect_status"] = "CHECK"
                else:
                    df.at[idx, "fancafe_collect_status"] = "OK"

                df.at[idx, "fancafe_candidates"] = format_candidates(candidates)
                df.at[idx, "fancafe_collected_at"] = now_str()

                print(f"후보 수: {len(candidates)}")
                print(f"팬카페: {df.at[idx, 'fancafe_url']}")
                print(f"상태: {df.at[idx, 'fancafe_collect_status']}")

                df.to_csv(output_path, index=False, encoding="utf-8-sig")

            except Exception as e:
                df.at[idx, "fancafe_url"] = ""
                df.at[idx, "fancafe_collect_status"] = f"ERROR: {type(e).__name__}: {e}"
                df.at[idx, "fancafe_collected_at"] = now_str()
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