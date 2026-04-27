import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from config import (
    API_KEYS,
    REQUEST_SLEEP,
    CHECKPOINT_EVERY,
    REGION_CODE,
    RELEVANCE_LANGUAGE,
    SEARCH_ORDERS,
    NEGATIVE_TERMS,
    LIGHT_NEGATIVE_TERMS,
    SCARCE_SEGMENTS,
    MAX_SEARCH_PAGES,
    SEARCH_MAX_RESULTS,
    FINAL_VIDEO_COLS,
    CANDIDATE_VIDEO_RAW_PATH,
    CANDIDATE_VIDEO_KR_PATH,
    USED_VIDEO_IDS_PATH,
    USED_CHANNELS_PATH,
    VIDEO_CATEGORY_MAP_PATH,
    DISCOVERY_PROGRESS_PATH,
    DISCOVERY_BAD_QUERIES_PATH,
    DISCOVERY_QUERY_STATS_PATH,
    DISCOVERY_QUERY_ERROR_COUNTS_PATH,
    TARGET_SEGMENTS,
    BASE_KEYWORDS,
    MODIFIERS,
    DISCOVERY_WEEKLY_BUDGET,
    DISCOVERY_MAX_NEW_CHANNELS_PER_QUERY,
    DISCOVERY_MAX_NEW_ROWS_PER_SEGMENT,
)
from utils.io_utils import (
    load_json,
    save_json,
    append_csv_safe,
    print_section,
    print_kv,
)
from utils.youtube_api_utils import (
    YouTubeAPIClient,
    QuotaExhaustedError,
    safe_int,
    parse_duration_to_sec,
)

# -----------------------------------------------------
# mode / keyword
# -----------------------------------------------------
QUERY_MODE = "new_only"
FORCE_ACTIVE_SEGMENTS = [
    "ASMR",
    "원신",
    "젠레스존제로",
    "블루아카이브",
    "붕괴스타레일",
    "명조",
    "명일방주",
    "니케",
    "애니송커버",
    "JPOP커버",
]

QUERY_ZERO_STREAK_LIMIT = {
    "버튜버": 8,
    "로블록스": 8,
    "마인크래프트": 8,
    "발로란트": 8,
    "JPOP커버": 8,
    "애니송커버": 10,
    "성우더빙": 4,
    "ASMR": 10,
    "코스프레": 4,
    "원신": 10,
    "젠레스존제로": 10,
    "블루아카이브": 10,
    "붕괴스타레일": 10,
    "명조": 10,
    "명일방주": 10,
    "니케": 10,
}

MAX_SEARCH_PAGES_BY_SEGMENT = {
    "ASMR": 2,
    "원신": 2,
    "젠레스존제로": 2,
    "블루아카이브": 2,
    "붕괴스타레일": 2,
    "명조": 2,
    "명일방주": 2,
    "니케": 2,
    "애니송커버": 2,
    "JPOP커버": 2,
}

LEGACY_KEYWORDS = {k: v[:] for k, v in BASE_KEYWORDS.items()}
NEW_KEYWORDS = {
    "JPOP커버": [
        "보컬로이드 커버 라이브", "vocaloid cover korean",
        "우타이테 커버 방송", "니코동 노래 커버", "보카로 커버 방송",
        "아니송 커버 라이브", "anisong cover live korean",
    ],
    "애니송커버": [
        "애니 ost 커버 방송", "서브컬처 노래 커버", "오타쿠 노래 커버",
        "anisong cover korean", "애니메이션 주제가 커버", "덕후 노래 커버",
    ],
    "ASMR": [
        "한국어 asmr", "한국 asmr 방송", "korean asmr",
        "한국 여성 asmr", "여자 asmr 방송", "남자 asmr 방송",
        "귀청소 asmr 한국어", "상황극 asmr 한국어", "노토킹 asmr 한국어",
        "팅글 asmr 한국어", "입소리 asmr 한국어", "수면 asmr 한국어",
        "버튜버 한국어 asmr", "버츄얼 한국어 asmr",
    ],
    "원신": [
        "원신 버튜버 방송", "원신 서브컬처 방송", "원신 여성 스트리머",
        "genshin korean vtuber", "genshin korea live streamer",
        "원신 오타쿠 방송", "원신 캐릭터 토크 방송",
    ],
    "젠레스존제로": [
        "젠존제 버튜버 방송", "젠레스 서브컬처 방송",
        "zenless korean vtuber", "zzz korea live streamer",
        "젠존제 여성 스트리머", "젠존제 캐릭터 토크 방송",
    ],
    "블루아카이브": [
        "블루아카 버튜버 방송", "블루아카 여성 스트리머",
        "blue archive korean vtuber", "블루아카 서브컬처 방송",
        "블루아카 캐릭터 토크", "블루아카 오타쿠 방송",
    ],
    "붕괴스타레일": [
        "붕스 버튜버 방송", "붕괴 스타레일 여성 스트리머",
        "honkai star rail korean vtuber", "붕스 서브컬처 방송",
        "붕스 캐릭터 토크", "붕스 오타쿠 방송",
    ],
    "명조": [
        "명조 방송", "명조 라이브", "명조 스트리머",
        "wuthering waves live korean", "wuthering waves streamer korea",
        "명조 버튜버", "명조 실시간", "명조 게임방송",
        "명조 합방", "명조 korean live",
        "명조 여성 스트리머", "명조 서브컬처 방송",
        "명조 캐릭터 토크", "wuthering waves korean vtuber",
    ],
    "명일방주": [
        "명일방주 방송", "명일방주 라이브", "명일방주 스트리머",
        "arknights live korean", "arknights streamer korea",
        "명일방주 버튜버", "명일방주 실시간", "명일방주 게임방송",
        "arknights korean live", "명방 방송",
        "명일방주 여성 스트리머", "명일방주 서브컬처 방송",
        "명일방주 캐릭터 토크", "arknights korean vtuber",
    ],
    "니케": [
        "니케 방송", "니케 라이브", "니케 스트리머",
        "nikke live korean", "nikke streamer korea",
        "승리의 여신 니케 방송", "승리의 여신 니케 라이브",
        "니케 버튜버", "니케 실시간", "nikke korean live",
        "니케 여성 스트리머", "니케 서브컬처 방송",
        "니케 캐릭터 토크", "nikke korean vtuber",
    ],
}

STANDARD_VIDEO_COLS = [
    "video_id", "channel_id", "channel_title", "title", "description",
    "published_at", "search_keyword", "search_query_full", "segment_seed",
    "search_period_start", "search_period_end", "search_order",
    "yt_category_id", "yt_category_name", "tags", "custom_category",
    "category_confidence", "view_count", "like_count", "comment_count",
    "duration", "duration_sec", "is_live_related", "has_live_actual_start"
]


class BadQueryError(Exception):
    def __init__(self, message: str, reason_type: str = "unknown"):
        super().__init__(message)
        self.reason_type = reason_type


def load_json_list(path: Path) -> set:
    obj = load_json(path, [])
    if isinstance(obj, list):
        return set(map(str, obj))
    return set()


def save_json_list(path: Path, values: set):
    save_json(path, sorted(list(map(str, values))))


def load_json_dict(path: Path) -> dict:
    obj = load_json(path, {})
    return obj if isinstance(obj, dict) else {}


def save_json_dict(path: Path, data: dict):
    save_json(path, data)


def get_kst_today_str():
    kst = timezone(timedelta(hours=9))
    return datetime.now(kst).strftime("%Y-%m-%d")


def build_week_ranges(start_date: str, end_date: str):
    start = pd.Timestamp(start_date)
    end = pd.Timestamp(end_date)
    ranges = []
    cursor = start
    while cursor <= end:
        week_end = min(cursor + timedelta(days=6), end)
        ranges.append((
            cursor.strftime("%Y-%m-%dT00:00:00Z"),
            week_end.strftime("%Y-%m-%dT23:59:59Z")
        ))
        cursor = week_end + timedelta(days=1)
    return ranges


def normalize_query_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    replacements = [
        ("라이브 라이브", "라이브"),
        ("live live", "live"),
        ("방송 방송", "방송"),
        ("실시간 라이브", "라이브"),
        ("라이브 실시간", "라이브"),
    ]
    for a, b in replacements:
        text = text.replace(a, b)
    return re.sub(r"\s+", " ", text).strip()


def is_bad_query_pattern(text: str) -> bool:
    bad_patterns = ["라이브 라이브", "live live", "방송 실시간", "실시간 방송"]
    return any(p in text for p in bad_patterns)


def get_keyword_source(mode: str):
    if mode == "new_only":
        return NEW_KEYWORDS
    elif mode == "legacy_only":
        return LEGACY_KEYWORDS
    else:
        merged = {}
        for seg in set(list(LEGACY_KEYWORDS.keys()) + list(NEW_KEYWORDS.keys())):
            merged[seg] = NEW_KEYWORDS.get(seg, []) + LEGACY_KEYWORDS.get(seg, [])
        return merged


def build_queries(active_segments: Optional[List[str]] = None, mode: str = "new_only") -> List[Dict]:
    queries = []
    seen = set()
    keyword_source = get_keyword_source(mode)

    for seg, kws in keyword_source.items():
        if active_segments is not None and seg not in active_segments:
            continue

        neg_terms = LIGHT_NEGATIVE_TERMS if seg in SCARCE_SEGMENTS else NEGATIVE_TERMS
        negative_clause = " ".join([f"-{term}" for term in neg_terms])

        for kw in kws:
            for mod in MODIFIERS:
                base_q = normalize_query_text(f"{kw} {mod}".strip())
                if is_bad_query_pattern(base_q):
                    continue

                q = normalize_query_text(f"{base_q} {negative_clause}".strip())

                for order in SEARCH_ORDERS:
                    key = (seg, q, order)
                    if key not in seen:
                        seen.add(key)
                        queries.append({
                            "segment_seed": seg,
                            "base_query": base_q,
                            "query": q,
                            "search_order": order,
                            "query_mode": mode,
                        })
    return queries


def prioritize_queries(search_queries: List[Dict], query_stats: Dict[str, dict]) -> List[Dict]:
    scored = []
    for item in search_queries:
        seg = item["segment_seed"]
        order_bonus = 2 if item["search_order"] == "relevance" else 1

        qkey = f"{seg}|||{item['search_order']}|||{item['query']}"
        stat = query_stats.get(qkey, {})
        historical_new_channels = int(stat.get("new_channels_total", 0))
        historical_calls = int(stat.get("search_calls_total", 0))
        historical_eff = historical_new_channels / historical_calls if historical_calls > 0 else 0
        untouched_bonus = 8 if historical_calls == 0 else 0

        priority_score = order_bonus * 3 + historical_eff * 15 + untouched_bonus + historical_new_channels * 0.1
        scored.append({**item, "priority_score": priority_score})
    return sorted(scored, key=lambda x: x["priority_score"], reverse=True)


def detect_live_related(title: str, desc: str) -> int:
    text = f"{title} {desc}".lower()
    live_keywords = ["live", "라이브", "생방", "생방송", "stream", "스트리밍", "방송", "실시간"]
    return int(any(k in text for k in live_keywords))


def get_video_categories(yt: YouTubeAPIClient, region_code: str = "KR") -> Dict[str, str]:
    cache = load_json_dict(VIDEO_CATEGORY_MAP_PATH)
    if cache:
        return cache

    url = "https://www.googleapis.com/youtube/v3/videoCategories"
    params = {"part": "snippet", "regionCode": region_code}
    data = yt.get_json(url, params, quota_cost=1)
    result = {}
    for item in data.get("items", []):
        cid = str(item.get("id"))
        result[cid] = item.get("snippet", {}).get("title")
    save_json_dict(VIDEO_CATEGORY_MAP_PATH, result)
    return result


def search_videos(
    yt: YouTubeAPIClient,
    query: str,
    published_after: str,
    published_before: str,
    order: str,
    page_token: Optional[str] = None,
) -> dict:
    url = "https://www.googleapis.com/youtube/v3/search"
    params = {
        "q": query,
        "part": "snippet",
        "type": "video",
        "maxResults": SEARCH_MAX_RESULTS,
        "order": order,
        "regionCode": REGION_CODE,
        "relevanceLanguage": RELEVANCE_LANGUAGE,
        "publishedAfter": published_after,
        "publishedBefore": published_before,
    }
    if page_token:
        params["pageToken"] = page_token

    try:
        return yt.get_json(url, params, quota_cost=100)
    except Exception as e:
        msg = str(e).lower()
        if "invalid" in msg or "parameter" in msg:
            raise BadQueryError(str(e), reason_type="invalid_query")
        raise


def update_target_csv(raw_path: Path, target_path: Path, data_origin: str):
    if not raw_path.exists():
        print(f"{raw_path.name}가 없어 갱신을 건너뜁니다.")
        return

    df_new = pd.read_csv(raw_path, encoding="utf-8-sig")

    if "segment_seed_raw" not in df_new.columns:
        df_new["segment_seed_raw"] = df_new["segment_seed"]
    if "data_origin" not in df_new.columns:
        df_new["data_origin"] = data_origin

    for col in FINAL_VIDEO_COLS:
        if col not in df_new.columns:
            df_new[col] = pd.NA

    df_new = df_new[FINAL_VIDEO_COLS].copy()

    if target_path.exists():
        df_old = pd.read_csv(target_path, encoding="utf-8-sig")
        for col in FINAL_VIDEO_COLS:
            if col not in df_old.columns:
                df_old[col] = pd.NA
        df_old = df_old[FINAL_VIDEO_COLS].copy()
    else:
        df_old = pd.DataFrame(columns=FINAL_VIDEO_COLS)

    df_merged = pd.concat([df_old, df_new], ignore_index=True)
    df_merged = df_merged.drop_duplicates(subset=["video_id"], keep="last").reset_index(drop=True)
    df_merged.to_csv(target_path, index=False, encoding="utf-8-sig")
    print(f"{target_path.name} 저장 완료 | rows={len(df_merged):,}")


video_rows_buffer_global = []


def save_progress(progress: dict, quota_used_total: int, active_keys: list, exhausted_keys: list):
    progress["last_saved_at"] = datetime.now().isoformat()
    progress["saved_date_kst"] = get_kst_today_str()
    progress["quota_used_total"] = quota_used_total
    progress["active_api_keys"] = active_keys
    progress["exhausted_api_keys"] = exhausted_keys
    save_json(DISCOVERY_PROGRESS_PATH, progress)


def load_current_progress() -> dict:
    progress = load_json(DISCOVERY_PROGRESS_PATH, {})
    if not progress:
        progress = {
            "done_pairs": [],
            "estimated_quota_used": 0,
            "quota_used_total": 0,
            "active_api_keys": API_KEYS.copy(),
            "exhausted_api_keys": [],
            "last_saved_at": None,
            "saved_date_kst": None,
        }
    return progress


def flush_and_finalize(
    raw_path: Path,
    target_path: Path,
    current_progress: dict,
    done_pairs: set,
    existing_video_ids: set,
    existing_channel_ids: set,
    bad_queries: set,
    query_stats: dict,
    query_error_counts: dict,
    yt: YouTubeAPIClient,
    data_origin: str,
):
    global video_rows_buffer_global

    if video_rows_buffer_global:
        df_to_save = pd.DataFrame(video_rows_buffer_global).reindex(columns=STANDARD_VIDEO_COLS)
        append_csv_safe(df_to_save, raw_path)
        video_rows_buffer_global.clear()

    current_progress["done_pairs"] = list(done_pairs)
    current_progress["estimated_quota_used"] = yt.quota_used_total
    save_progress(
        current_progress,
        quota_used_total=yt.quota_used_total,
        active_keys=yt.active_api_keys,
        exhausted_keys=yt.exhausted_api_keys,
    )

    save_json_list(USED_VIDEO_IDS_PATH, existing_video_ids)
    save_json_list(USED_CHANNELS_PATH, existing_channel_ids)
    save_json_list(DISCOVERY_BAD_QUERIES_PATH, bad_queries)
    save_json_dict(DISCOVERY_QUERY_STATS_PATH, query_stats)
    save_json_dict(DISCOVERY_QUERY_ERROR_COUNTS_PATH, query_error_counts)

    update_target_csv(raw_path=raw_path, target_path=target_path, data_origin=data_origin)


def run(start_date: Optional[str] = None, end_date: Optional[str] = None):
    """
    discovery 전용
    - 이미 본 channel_id는 원칙적으로 제외
    - 세그먼트별 주간 신규 채널 budget만큼만 탐색
    """
    global video_rows_buffer_global

    print_section("STEP2 - 일반 후보 Discovery 수집")

    if start_date is None or end_date is None:
        end_ts = pd.Timestamp.now(tz="Asia/Seoul").normalize()
        start_ts = end_ts - pd.Timedelta(days=27)
        start_date = start_ts.strftime("%Y-%m-%d")
        end_date = end_ts.strftime("%Y-%m-%d")

    week_ranges = build_week_ranges(start_date, end_date)
    yt = YouTubeAPIClient(api_keys=API_KEYS, request_sleep=REQUEST_SLEEP)

    current_progress = load_current_progress()
    done_pairs = set(current_progress.get("done_pairs", []))
    bad_queries = load_json_list(DISCOVERY_BAD_QUERIES_PATH)
    query_stats = load_json_dict(DISCOVERY_QUERY_STATS_PATH)
    query_error_counts = load_json_dict(DISCOVERY_QUERY_ERROR_COUNTS_PATH)

    existing_video_ids = load_json_list(USED_VIDEO_IDS_PATH)
    existing_channel_ids = load_json_list(USED_CHANNELS_PATH)

    yt_category_map = get_video_categories(yt, region_code=REGION_CODE or "KR")

    active_segments = [seg for seg in TARGET_SEGMENTS if DISCOVERY_WEEKLY_BUDGET.get(seg, 0) > 0]
    if FORCE_ACTIVE_SEGMENTS:
        active_segments = [seg for seg in active_segments if seg in FORCE_ACTIVE_SEGMENTS]

    search_queries = build_queries(active_segments=active_segments, mode=QUERY_MODE)
    search_queries = prioritize_queries(search_queries, query_stats)

    segment_new_channel_counts = {seg: 0 for seg in active_segments}

    print_kv("기간", f"{start_date} ~ {end_date}")
    print_kv("week range 수", len(week_ranges))
    print_kv("active_segments", active_segments)
    print_kv("query 수", len(search_queries))
    print_kv("used_video_ids", len(existing_video_ids))
    print_kv("used_channels", len(existing_channel_ids))

    zero_streak_by_query = {}
    pair_counter = 0
    total_pairs = len(search_queries) * len(week_ranges)
    processed_counter = 0
    data_origin = f"youtube_discovery_{start_date}_{end_date}_{QUERY_MODE}"

    for item in search_queries:
        segment_seed = item["segment_seed"]
        query = item["query"]
        search_order = item["search_order"]

        if segment_new_channel_counts.get(segment_seed, 0) >= DISCOVERY_WEEKLY_BUDGET.get(segment_seed, 0):
            print(f"[SKIP budget reached] {segment_seed}")
            continue

        query_key = f"{segment_seed}|||{search_order}|||{query}"
        query_zero_limit = QUERY_ZERO_STREAK_LIMIT.get(segment_seed, 8)
        current_max_pages = MAX_SEARCH_PAGES_BY_SEGMENT.get(segment_seed, MAX_SEARCH_PAGES)

        qstat = query_stats.get(query_key, {})
        hist_calls = int(qstat.get("search_calls_total", 0))
        hist_new = int(qstat.get("new_channels_total", 0))
        hist_eff = hist_new / hist_calls if hist_calls > 0 else None

        if QUERY_MODE == "new_only":
            if hist_calls >= 2 and hist_new == 0:
                print(f"[SKIP dead_query] {segment_seed} | {query[:60]}")
                continue
            if hist_calls >= 3 and hist_eff is not None and hist_eff < 0.2:
                print(f"[SKIP low_eff_query] {segment_seed} | eff={hist_eff:.3f} | {query[:60]}")
                continue

        if zero_streak_by_query.get(query_key, 0) >= query_zero_limit:
            print(f"[SKIP query] {segment_seed} | {search_order} | {query[:50]} | zero_streak={zero_streak_by_query.get(query_key, 0)}")
            continue

        for start_dt, end_dt in week_ranges:
            if segment_new_channel_counts.get(segment_seed, 0) >= DISCOVERY_WEEKLY_BUDGET.get(segment_seed, 0):
                break

            pair_counter += 1
            pair_key = f"{segment_seed}|||{query}|||{search_order}|||{start_dt}|||{end_dt}"

            if pair_key in done_pairs:
                continue

            print(
                f"[{pair_counter}/{total_pairs}] "
                f"{segment_seed} | order={search_order} | {start_dt[:10]}~{end_dt[:10]} | "
                f"new_channel_budget={DISCOVERY_WEEKLY_BUDGET.get(segment_seed, 0) - segment_new_channel_counts.get(segment_seed, 0)}"
            )

            page_token = None
            page_num = 0
            pair_new_rows = 0
            search_calls = 0
            fetched_cnt = 0
            new_video_id_cnt = 0
            new_channel_cnt = 0

            try:
                while True:
                    if segment_new_channel_counts.get(segment_seed, 0) >= DISCOVERY_WEEKLY_BUDGET.get(segment_seed, 0):
                        break

                    if page_num >= current_max_pages:
                        break

                    search_data = search_videos(
                        yt=yt,
                        query=query,
                        published_after=start_dt,
                        published_before=end_dt,
                        order=search_order,
                        page_token=page_token,
                    )
                    search_calls += 1

                    items = search_data.get("items", [])
                    if not items:
                        break

                    page_num += 1
                    fetched_cnt += len(items)

                    candidate_video_ids = []
                    candidate_video_channel_pairs = []

                    for s in items:
                        vid = s.get("id", {}).get("videoId")
                        snippet = s.get("snippet", {})
                        ch_id = snippet.get("channelId")

                        if not vid or not ch_id:
                            continue

                        # discovery 핵심: 이미 본 채널은 제외
                        if str(ch_id) in existing_channel_ids:
                            continue

                        if str(vid) in existing_video_ids:
                            continue

                        candidate_video_ids.append(str(vid))
                        candidate_video_channel_pairs.append((str(vid), str(ch_id)))

                    candidate_video_ids = list(dict.fromkeys(candidate_video_ids))
                    new_video_id_cnt += len(candidate_video_ids)

                    if not candidate_video_ids:
                        page_token = search_data.get("nextPageToken")
                        if not page_token:
                            break
                        continue

                    detail_resp = yt.get_video_details(candidate_video_ids)
                    new_channel_ids_in_pair = set()

                    for v in detail_resp.get("items", []):
                        snippet = v.get("snippet", {})
                        stats = v.get("statistics", {})
                        content = v.get("contentDetails", {})
                        live = v.get("liveStreamingDetails", {})

                        video_id = str(v.get("id"))
                        channel_id = str(snippet.get("channelId", ""))

                        # detail 단계에서도 discovery hard filter 유지
                        if channel_id in existing_channel_ids:
                            continue

                        if len(new_channel_ids_in_pair) >= DISCOVERY_MAX_NEW_CHANNELS_PER_QUERY:
                            continue

                        if pair_new_rows >= DISCOVERY_MAX_NEW_ROWS_PER_SEGMENT:
                            continue

                        channel_title = snippet.get("channelTitle")
                        title = snippet.get("title")
                        desc = snippet.get("description")
                        published_at = snippet.get("publishedAt")
                        yt_category_id = snippet.get("categoryId")
                        duration = content.get("duration")
                        duration_sec = parse_duration_to_sec(duration)

                        row = {
                            "video_id": video_id,
                            "channel_id": channel_id,
                            "channel_title": channel_title,
                            "title": title,
                            "description": desc,
                            "published_at": published_at,
                            "search_keyword": item["base_query"],
                            "search_query_full": query,
                            "segment_seed": segment_seed,
                            "search_period_start": start_dt,
                            "search_period_end": end_dt,
                            "search_order": search_order,
                            "yt_category_id": yt_category_id,
                            "yt_category_name": yt_category_map.get(str(yt_category_id)),
                            "tags": None,
                            "custom_category": None,
                            "category_confidence": None,
                            "view_count": safe_int(stats.get("viewCount")),
                            "like_count": safe_int(stats.get("likeCount")),
                            "comment_count": safe_int(stats.get("commentCount")),
                            "duration": duration,
                            "duration_sec": duration_sec,
                            "is_live_related": detect_live_related(title or "", desc or ""),
                            "has_live_actual_start": int("actualStartTime" in live),
                        }

                        video_rows_buffer_global.append(row)
                        existing_video_ids.add(video_id)

                        if channel_id and channel_id not in new_channel_ids_in_pair:
                            new_channel_ids_in_pair.add(channel_id)

                        pair_new_rows += 1

                    # 새 채널 discovery 확정
                    for ch_id in new_channel_ids_in_pair:
                        existing_channel_ids.add(ch_id)

                    new_channel_cnt += len(new_channel_ids_in_pair)
                    segment_new_channel_counts[segment_seed] += len(new_channel_ids_in_pair)

                    page_token = search_data.get("nextPageToken")
                    if not page_token:
                        break

                done_pairs.add(pair_key)
                processed_counter += 1

                dedup_rate = 1 - (new_video_id_cnt / fetched_cnt) if fetched_cnt > 0 else 0.0
                print(
                    f"[{segment_seed}] fetched={fetched_cnt} | new_video_ids={new_video_id_cnt} | "
                    f"new_channels={new_channel_cnt} | new_rows={pair_new_rows} | "
                    f"segment_progress={segment_new_channel_counts.get(segment_seed, 0)}/{DISCOVERY_WEEKLY_BUDGET.get(segment_seed, 0)} | "
                    f"dedup_rate={dedup_rate:.2%} | quota_total={yt.quota_used_total:,}"
                )

                query_stats.setdefault(query_key, {})
                query_stats[query_key]["new_channels_total"] = int(query_stats[query_key].get("new_channels_total", 0)) + new_channel_cnt
                query_stats[query_key]["new_rows_total"] = int(query_stats[query_key].get("new_rows_total", 0)) + pair_new_rows
                query_stats[query_key]["search_calls_total"] = int(query_stats[query_key].get("search_calls_total", 0)) + search_calls

                if new_channel_cnt == 0:
                    zero_streak_by_query[query_key] = zero_streak_by_query.get(query_key, 0) + 1
                else:
                    zero_streak_by_query[query_key] = 0

                if zero_streak_by_query.get(query_key, 0) >= query_zero_limit:
                    bad_queries.add(query)
                    print(f"[BAD_QUERY 등록] {segment_seed} | {search_order} | {query[:60]}")

                if processed_counter % CHECKPOINT_EVERY == 0:
                    flush_and_finalize(
                        raw_path=CANDIDATE_VIDEO_RAW_PATH,
                        target_path=CANDIDATE_VIDEO_KR_PATH,
                        current_progress=current_progress,
                        done_pairs=done_pairs,
                        existing_video_ids=existing_video_ids,
                        existing_channel_ids=existing_channel_ids,
                        bad_queries=bad_queries,
                        query_stats=query_stats,
                        query_error_counts=query_error_counts,
                        yt=yt,
                        data_origin=data_origin,
                    )
                    print(f"[중간저장 완료] quota_total={yt.quota_used_total:,}")

            except BadQueryError as e:
                print(f"[BadQueryError] query={query} | err={e}")

                query_error_counts.setdefault(query, {"count": 0, "reason_type": e.reason_type, "last_error": ""})
                query_error_counts[query]["count"] += 1
                query_error_counts[query]["reason_type"] = e.reason_type
                query_error_counts[query]["last_error"] = str(e)

                if e.reason_type == "invalid_query" and query_error_counts[query]["count"] >= 2:
                    bad_queries.add(query)
                    save_json_list(DISCOVERY_BAD_QUERIES_PATH, bad_queries)

                save_json_dict(DISCOVERY_QUERY_ERROR_COUNTS_PATH, query_error_counts)
                break

            except QuotaExhaustedError:
                print("모든 API KEY quota 소진으로 중단")
                flush_and_finalize(
                    raw_path=CANDIDATE_VIDEO_RAW_PATH,
                    target_path=CANDIDATE_VIDEO_KR_PATH,
                    current_progress=current_progress,
                    done_pairs=done_pairs,
                    existing_video_ids=existing_video_ids,
                    existing_channel_ids=existing_channel_ids,
                    bad_queries=bad_queries,
                    query_stats=query_stats,
                    query_error_counts=query_error_counts,
                    yt=yt,
                    data_origin=data_origin,
                )
                return

            except Exception as e:
                print(f"[pair fail] {pair_key} | err={e}")
                time.sleep(2)

            time.sleep(REQUEST_SLEEP)

    flush_and_finalize(
        raw_path=CANDIDATE_VIDEO_RAW_PATH,
        target_path=CANDIDATE_VIDEO_KR_PATH,
        current_progress=current_progress,
        done_pairs=done_pairs,
        existing_video_ids=existing_video_ids,
        existing_channel_ids=existing_channel_ids,
        bad_queries=bad_queries,
        query_stats=query_stats,
        query_error_counts=query_error_counts,
        yt=yt,
        data_origin=f"youtube_discovery_{start_date}_{end_date}_{QUERY_MODE}",
    )

    print("\n===== Discovery 수집 완료 =====")
    print("quota_total:", yt.quota_used_total)
    print("exhausted_api_keys:", yt.exhausted_api_keys)
    print("raw_path:", CANDIDATE_VIDEO_RAW_PATH)
    print("target_path:", CANDIDATE_VIDEO_KR_PATH)


if __name__ == "__main__":
    run()