"""
방송국 URL에서 팬카페 URL + 회원수 + 게시글수 수집 통합 코드

기능
- fancafe_url 없는 행만 방송국에서 팬카페 URL 수집
- 이미 fancafe_url이 있는 행은 바로 회원수/게시글수 수집
- platform이 트위치, 유튜브, 씨미/ci.me/cime 인 행 제외
- 후보 URL 1개: OK
- 후보 URL 2개 이상: CHECK
- URL 못 찾음: NOT_FOUND / status=NOT
- 에러: status=ERROR로 저장 후 다음 행 진행
- 한 행 처리할 때마다 CSV 저장
- 출력 파일이 이미 있으면 이어서 실행
"""

import argparse
import json
import re
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote

import pandas as pd
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


# ============================================================
# 기본 파일명
# ============================================================
DEFAULT_INPUT = "bj_links_merged_final_with_followers_1p_검증분담표.csv"
DEFAULT_OUTPUT = "bj_links_fancafe_url_member_collected.csv"


# ============================================================
# 제외 플랫폼
# ============================================================
EXCLUDE_PLATFORM_KEYWORDS = [
    "트위치", "twitch",
    "유튜브", "youtube",
    "씨미", "cime", "ci.me",
]


# ============================================================
# 기본 유틸
# ============================================================
def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def is_missing_value(v):
    if pd.isna(v):
        return True
    s = str(v).strip()
    return s == "" or s.lower() in {"nan", "none", "null", "<na>"}


def is_not_found_value(v):
    return str(v).strip().upper() in {"NOT_FOUND", "SEARCH_ERROR"}


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


def only_digits(text):
    if text is None:
        return ""
    return "".join(re.findall(r"\d+", str(text)))


def parse_korean_count(text):
    """
    예:
    12,345명 -> 12345
    1.2만명 -> 12000
    멤버수 3.4만 -> 34000
    """
    if not isinstance(text, str):
        return ""

    t = text.replace(",", "").replace(" ", "")

    m = re.search(r"([0-9]+(?:\.[0-9]+)?)만", t)
    if m:
        return str(int(float(m.group(1)) * 10000))

    nums = re.findall(r"\d+", t)
    if nums:
        return nums[0]

    return ""


# ============================================================
# 컬럼 보장
# ============================================================
def ensure_columns(df):
    needed = {
        "fancafe_url": "",
        "fancafe_collect_status": "",
        "fancafe_collected_at": "",
        "fancafe_candidates": "",
        "fancafe_member_count": pd.NA,
        "fancafe_post_count": pd.NA,
        "fancafe_metric_status": "",
        "fancafe_metric_collected_at": "",
    }

    for col, default in needed.items():
        if col not in df.columns:
            df[col] = default
        df[col] = df[col].astype("object")

    return df


# ============================================================
# 방송국 페이지에서 팬카페 URL 추출
# ============================================================
def extract_fancafe_links_from_page(page):
    links = []

    # 1. a 태그 href 추출
    try:
        hrefs = page.locator("a").evaluate_all(
            "els => els.map(a => a.href).filter(Boolean)"
        )
        links.extend(hrefs)
    except Exception:
        pass

    # 2. html/text 안에 박힌 URL 추출
    try:
        html = page.content()
        links.extend(
            re.findall(
                r"https?://(?:www\.|m\.)?cafe\.(?:naver\.com|daum\.net)[^\"'<>\s]+",
                html
            )
        )
    except Exception:
        pass

    # 3. data-url, onclick, aria-label 등에서 추출
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
            links.extend(
                re.findall(
                    r"https?://(?:www\.|m\.)?cafe\.(?:naver\.com|daum\.net)[^\"'<>\s]+",
                    s
                )
            )
    except Exception:
        pass

    return dedupe_keep_order(links)


def click_fancafe_like_icons_and_collect(context, page, max_clicks=25):
    """
    href에 안 보이고 아이콘 클릭으로만 열리는 팬카페 링크 수집.
    """
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

            w, h = box.get("width", 0), box.get("height", 0)
            x, y = box.get("x", 0), box.get("y", 0)

            if w > 90 or h > 90:
                continue
            if y < 120 or y > 650:
                continue

            label = ""
            try:
                label = el.evaluate(
                    "el => [el.innerText, el.title, el.getAttribute('aria-label'), el.outerHTML].join(' ')"
                ) or ""
            except Exception:
                pass

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

            # 새로 뜬 페이지 정리
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

    more = click_fancafe_like_icons_and_collect(context, page)
    links = dedupe_keep_order(links + more)

    return links


def format_candidates(candidates):
    return json.dumps([{"url": url} for url in candidates], ensure_ascii=False)


# ============================================================
# 팬카페 페이지에서 회원수 / 게시글수 수집
# ============================================================
def collect_naver_cafe_metrics(page, fancafe_url, wait_sec=2):
    """
    네이버 카페 기준 회원수 / 전체글 수 수집.
    구조 변경 가능성이 있어서 여러 방식으로 시도.
    """
    member_count = ""
    post_count = ""

    pc_url = normalize_fancafe_url(fancafe_url)
    page.goto(pc_url, wait_until="domcontentloaded", timeout=45000)
    time.sleep(wait_sec)

    try:
        page.wait_for_load_state("networkidle", timeout=6000)
    except Exception:
        pass

    # 네이버 카페는 iframe 안에 주요 내용이 있을 수 있음
    pages_to_check = [page]
    try:
        pages_to_check.extend(page.frames)
    except Exception:
        pass

    # 1. 회원수: 기존 Selenium 코드의 .mem-cnt-info em 대응
    member_selectors = [
        ".mem-cnt-info em",
        ".mem-cnt-info",
        ".cafe_info .member",
        ".info_area",
    ]

    for target in pages_to_check:
        if member_count:
            break

        for sel in member_selectors:
            try:
                loc = target.locator(sel).first
                if loc.count() > 0:
                    txt = loc.inner_text(timeout=2000)
                    val = parse_korean_count(txt)
                    if val:
                        member_count = val
                        break
            except Exception:
                continue

    # 2. 전체 텍스트에서 회원/멤버 패턴 찾기
    if not member_count:
        try:
            body_text = page.locator("body").inner_text(timeout=5000)
            patterns = [
                r"멤버수\s*([0-9,.]+)\s*만?",
                r"회원수\s*([0-9,.]+)\s*만?",
                r"멤버\s*([0-9,.]+)\s*만?\s*명?",
                r"회원\s*([0-9,.]+)\s*만?\s*명?",
            ]

            for pat in patterns:
                m = re.search(pat, body_text.replace("\n", " "))
                if m:
                    member_count = parse_korean_count(m.group(0))
                    if member_count:
                        break
        except Exception:
            pass

    # 3. 게시글수: 전체글 텍스트 찾기
    try:
        all_text = page.locator("body").inner_text(timeout=5000)
        compact = all_text.replace(" ", "").replace("\n", "")

        m = re.search(r"전체글([0-9,]+)", compact)
        if m:
            post_count = only_digits(m.group(1))
    except Exception:
        pass

    # 4. li 태그에서 전체글 찾기
    if not post_count:
        try:
            li_texts = page.locator("li").all_inner_texts()
            for txt in li_texts:
                compact = txt.replace(" ", "").replace("\n", "")
                if "전체글" in compact:
                    nums = re.findall(r"\d+", compact)
                    if nums:
                        post_count = "".join(nums)
                        break
        except Exception:
            pass

    return {
        "member_count": member_count if member_count else "0",
        "post_count": post_count if post_count else "0",
    }


def collect_daum_cafe_metrics(page, fancafe_url, wait_sec=2):
    """
    다음 카페는 구조가 다양해서 우선 URL 접속 후 텍스트 기반으로 최대한 추출.
    """
    member_count = ""
    post_count = ""

    pc_url = normalize_fancafe_url(fancafe_url)
    page.goto(pc_url, wait_until="domcontentloaded", timeout=45000)
    time.sleep(wait_sec)

    try:
        page.wait_for_load_state("networkidle", timeout=6000)
    except Exception:
        pass

    try:
        body_text = page.locator("body").inner_text(timeout=5000)
        compact = body_text.replace(" ", "").replace("\n", "")

        member_patterns = [
            r"회원수([0-9,.]+)만?",
            r"회원([0-9,.]+)명",
            r"멤버([0-9,.]+)명",
        ]

        for pat in member_patterns:
            m = re.search(pat, compact)
            if m:
                member_count = parse_korean_count(m.group(0))
                if member_count:
                    break

        post_patterns = [
            r"전체글([0-9,]+)",
            r"게시글([0-9,]+)",
        ]

        for pat in post_patterns:
            m = re.search(pat, compact)
            if m:
                post_count = only_digits(m.group(1))
                if post_count:
                    break

    except Exception:
        pass

    return {
        "member_count": member_count if member_count else "0",
        "post_count": post_count if post_count else "0",
    }


def collect_fancafe_metrics(page, fancafe_url, wait_sec=2):
    url = normalize_fancafe_url(fancafe_url)

    if "cafe.naver.com" in url.lower():
        return collect_naver_cafe_metrics(page, url, wait_sec=wait_sec)

    if "cafe.daum.net" in url.lower():
        return collect_daum_cafe_metrics(page, url, wait_sec=wait_sec)

    return {
        "member_count": "0",
        "post_count": "0",
    }


# ============================================================
# 처리 대상 판단
# ============================================================
def row_needs_processing(row, retry_not_found=False, force=False):
    if force:
        return True

    platform = row.get("platform", "")
    if is_excluded_platform(platform):
        return False

    broadcast_url = row.get("broadcast_url", "")
    fancafe_url = row.get("fancafe_url", "")
    collect_status = row.get("fancafe_collect_status", "")

    member_count = row.get("fancafe_member_count", "")
    post_count = row.get("fancafe_post_count", "")
    metric_status = row.get("fancafe_metric_status", "")

    # 이전 URL 수집 중 에러는 재시도
    if str(collect_status).startswith("ERROR"):
        return True

    # 이전 회원수/게시글수 수집 중 에러는 재시도
    if str(metric_status).startswith("ERROR"):
        return True

    # URL이 없으면 방송국 URL이 있을 때 처리
    if is_missing_value(fancafe_url):
        return not is_missing_value(broadcast_url)

    # NOT_FOUND는 기본 스킵, 옵션으로 재시도
    if is_not_found_value(fancafe_url):
        return retry_not_found

    # URL은 있는데 회원수/게시글수가 비어 있으면 처리
    if is_fancafe_url(fancafe_url):
        if is_missing_value(member_count) or is_missing_value(post_count):
            return True

    return False


# ============================================================
# 메인
# ============================================================
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
    print("팬카페 URL + 회원수 + 게시글수 수집 시작")
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
            current_url = row.get("fancafe_url", "")

            print(f"\n[{n}/{len(target_indices)}] index={idx} | {platform} | {streamer_name}")
            print(f"방송국: {broadcast_url}")
            print(f"기존 팬카페 URL: {current_url}")

            try:
                # ====================================================
                # 1. 팬카페 URL이 없으면 방송국에서 URL 먼저 수집
                # ====================================================
                if is_missing_value(current_url) or (
                    args.retry_not_found and is_not_found_value(current_url)
                ):
                    if is_missing_value(broadcast_url):
                        df.at[idx, "fancafe_url"] = ""
                        df.at[idx, "fancafe_collect_status"] = "ERROR: NO_BROADCAST_URL"
                        df.at[idx, "fancafe_collected_at"] = now_str()
                        df.to_csv(output_path, index=False, encoding="utf-8-sig")
                        print("상태: ERROR / 방송국 URL 없음")
                        continue

                    candidates = collect_fancafe_candidates_from_broadcast(
                        context,
                        page,
                        broadcast_url,
                        wait_sec=args.delay
                    )

                    if not candidates:
                        df.at[idx, "fancafe_url"] = "NOT_FOUND"
                        df.at[idx, "fancafe_collect_status"] = "NOT"
                        df.at[idx, "fancafe_candidates"] = ""
                        df.at[idx, "fancafe_collected_at"] = now_str()
                        df.at[idx, "fancafe_member_count"] = pd.NA
                        df.at[idx, "fancafe_post_count"] = pd.NA
                        df.at[idx, "fancafe_metric_status"] = ""
                        df.to_csv(output_path, index=False, encoding="utf-8-sig")

                        print("상태: NOT / 팬카페 URL 못 찾음")
                        continue

                    chosen_url = candidates[0]
                    df.at[idx, "fancafe_url"] = chosen_url
                    df.at[idx, "fancafe_collect_status"] = "CHECK" if len(candidates) >= 2 else "OK"
                    df.at[idx, "fancafe_candidates"] = format_candidates(candidates)
                    df.at[idx, "fancafe_collected_at"] = now_str()

                    current_url = chosen_url

                    print(f"후보 수: {len(candidates)}")
                    print(f"선택 팬카페: {chosen_url}")
                    print(f"URL 상태: {df.at[idx, 'fancafe_collect_status']}")

                    df.to_csv(output_path, index=False, encoding="utf-8-sig")

                # ====================================================
                # 2. 팬카페 URL이 있으면 회원수 / 게시글수 수집
                # ====================================================
                if is_fancafe_url(current_url):
                    metrics = collect_fancafe_metrics(
                        page,
                        current_url,
                        wait_sec=args.delay
                    )

                    df.at[idx, "fancafe_member_count"] = metrics["member_count"]
                    df.at[idx, "fancafe_post_count"] = metrics["post_count"]
                    df.at[idx, "fancafe_metric_status"] = "OK"
                    df.at[idx, "fancafe_metric_collected_at"] = now_str()

                    print(f"회원수: {metrics['member_count']}")
                    print(f"게시글수: {metrics['post_count']}")

                    df.to_csv(output_path, index=False, encoding="utf-8-sig")

                else:
                    print("회원수/게시글수 수집 생략: 유효한 팬카페 URL 없음")
                    df.to_csv(output_path, index=False, encoding="utf-8-sig")

            except Exception as e:
                df.at[idx, "fancafe_metric_status"] = f"ERROR: {type(e).__name__}: {e}"
                df.at[idx, "fancafe_metric_collected_at"] = now_str()

                if is_missing_value(df.at[idx, "fancafe_collect_status"]):
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