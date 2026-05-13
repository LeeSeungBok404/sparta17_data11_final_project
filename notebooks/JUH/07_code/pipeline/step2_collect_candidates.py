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
    CANDIDATE_DISCOVERY_RAW_PATH,
    CANDIDATE_DISCOVERY_MERGED_PATH,
    USED_VIDEO_IDS_PATH,
    USED_CHANNELS_PATH,
    VIDEO_CATEGORY_MAP_PATH,
    DISCOVERY_PROGRESS_PATH,
    DISCOVERY_BAD_QUERIES_PATH,
    DISCOVERY_QUERY_STATS_PATH,
    DISCOVERY_QUERY_ERROR_COUNTS_PATH,
    MODIFIERS,
    DISCOVERY_MAX_NEW_CHANNELS_PER_QUERY,
    DISCOVERY_MAX_NEW_ROWS_PER_SEGMENT,
    DISCOVERY_SEARCH_KEYWORDS_BY_LOWER,
    LOWER_TO_UPPER_SEGMENT,
    DISCOVERY_WEEKLY_BUDGET_BY_UPPER,
    DISCOVERY_LOWER_WEIGHT,
    DISCOVERY_TOTAL_TARGET_CHANNELS,
    DISCOVERY_MAX_PAGES_PER_KEYWORD,
    DISCOVERY_MAX_VIDEOS_PER_KEYWORD,
    DISCOVERY_MIN_VIEW_COUNT,
    DISCOVERY_ONLY_NEW_CHANNELS,
    ALLOW_REDISCOVERY_EXISTING_CHANNELS,
    REDISCOVERY_STALE_DAYS,
    MIN_NEW_PER_SEARCH_THRESHOLD,
    MAX_DEDUP_RATE_THRESHOLD,
    ENABLE_SEGMENT_FALLBACK_SEARCH,
    FALLBACK_EXTRA_PAGES,
    DISCOVERY_SORT_STRATEGY,
    SEGMENT_CHANNEL_CAPS,
    SEGMENT_PAGE_LIMITS,
    SEGMENT_KEYWORD_LIMITS,
    SEGMENT_SORT_STRATEGY,
    ENABLE_DISCOVERY_DATE_SLICING,
    ENABLE_WEEKLY_DISCOVERY_SLICING,
    DISCOVERY_WEEKLY_SLICES,
    PRINT_DISCOVERY_DEBUG_LOG,
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
# new_only    : 아래 NEW_KEYWORDS에 있는 신규 키워드만 사용
# legacy_only : config.py의 DISCOVERY_SEARCH_KEYWORDS_BY_LOWER만 사용
# mixed       : 신규 키워드 + 기존 config 키워드 모두 사용
#
# 특정 세그먼트만 반복 수집되는 편향을 줄이기 위해 mixed 권장
QUERY_MODE = "mixed"


# -----------------------------------------------------
# Balanced Discovery 운영 옵션
# -----------------------------------------------------
# True  : 하위 세그먼트별 동일 목표량에 가깝게 수집
# False : 기존 config.py의 upper budget / lower weight 구조 사용
BALANCED_DISCOVERY_MODE = True

# True이면 상위세그먼트별 budget 제한을 적용하지 않음
# 예: 음악·보이스형이 먼저 budget을 채워 다른 하위 세그먼트가 막히는 문제 방지
IGNORE_UPPER_SEGMENT_BUDGET = True

# True이면 SEGMENT_CHANNEL_CAPS 제한을 적용하지 않음
# 예: 특정 상위세그먼트 cap 때문에 신규 수집이 막히는 문제 방지
IGNORE_SEGMENT_CAP = True

# query별 최대 페이지 수
# YouTube search.list는 page마다 quota 100이므로 3페이지를 상한으로 둠
HARD_MAX_PAGES_PER_QUERY = 3

# 세그먼트별 균등 목표량
# None이면 DISCOVERY_TOTAL_TARGET_CHANNELS / active_lower_segments 수로 자동 계산
BALANCED_TARGET_PER_LOWER_SEGMENT = None

# query 하나가 최대 페이지까지 돌았는데 신규 채널이 0이면 dead query로 등록
MARK_DEAD_QUERY_WHEN_ZERO_AFTER_MAX_PAGES = True


# -----------------------------------------------------
# 이번 프로젝트에서 실제로 탐색할 하위 세그먼트
# -----------------------------------------------------
# 비워두면 config.py에 있는 전체 세그먼트를 사용한다.
# 단, 너무 넓어지면 quota 소모가 커지므로 프로젝트 타깃 세그먼트만 명시하는 것을 권장.
FORCE_ACTIVE_LOWER_SEGMENTS = [
    # 버츄얼/음악/보이스
    "버튜버",
    "JPOP커버",
    "애니송커버",
    "ASMR",
    "성우",
    "성우더빙",
    "일렉기타연주",
    "드럼연주",

    # 창작/비주얼
    "코스프레",
    "일러스트리깅",
    "일러스트",
    "리깅",
    "그림",

    # 게임/서브컬처 게임
    "로블록스",
    "마인크래프트",
    "발로란트",
    "원신",
    "젠레스존제로",
    "블루아카이브",
    "붕괴스타레일",
    "명조",
    "명일방주",
    "니케",

    # 토크/팬덤
    "저스트채팅",
    "저스트 채팅",
    "토크",
    "덕질토크",
    "애니게임토크",
]


QUERY_ZERO_STREAK_LIMIT = {
    "버튜버": 8,

    "JPOP커버": 8,
    "애니송커버": 10,
    "ASMR": 10,
    "성우": 6,
    "성우더빙": 4,
    "일렉기타연주": 10,
    "드럼연주": 10,

    "코스프레": 4,
    "일러스트리깅": 6,
    "일러스트": 6,
    "리깅": 6,
    "그림": 6,

    "로블록스": 8,
    "마인크래프트": 8,
    "발로란트": 8,
    "원신": 10,
    "젠레스존제로": 10,
    "블루아카이브": 10,
    "붕괴스타레일": 10,
    "명조": 10,
    "명일방주": 10,
    "니케": 10,

    "저스트채팅": 6,
    "저스트 채팅": 6,
    "토크": 6,
    "덕질토크": 6,
    "애니게임토크": 6,
}


# 세그먼트별 page limit.
# get_page_limit()에서 최종적으로 HARD_MAX_PAGES_PER_QUERY로 한 번 더 제한한다.
MAX_SEARCH_PAGES_BY_LOWER_SEGMENT = {
    "버튜버": 3,

    "JPOP커버": 3,
    "애니송커버": 3,
    "ASMR": 3,
    "성우": 3,
    "성우더빙": 3,
    "일렉기타연주": 3,
    "드럼연주": 3,

    "코스프레": 3,
    "일러스트리깅": 3,
    "일러스트": 3,
    "리깅": 3,
    "그림": 3,

    "로블록스": 3,
    "마인크래프트": 3,
    "발로란트": 3,
    "원신": 3,
    "젠레스존제로": 3,
    "블루아카이브": 3,
    "붕괴스타레일": 3,
    "명조": 3,
    "명일방주": 3,
    "니케": 3,

    "저스트채팅": 3,
    "저스트 채팅": 3,
    "토크": 3,
    "덕질토크": 3,
    "애니게임토크": 3,
}

LEGACY_KEYWORDS = {k: v[:] for k, v in DISCOVERY_SEARCH_KEYWORDS_BY_LOWER.items()}

# 신규 보강 키워드.
# QUERY_MODE="mixed"이면 config.py의 기존 키워드와 이 키워드가 함께 사용된다.
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
    "일렉기타연주": [
        "일렉기타 연주 방송", "일렉기타 라이브", "기타 연주 방송",
        "guitar cover live korean", "electric guitar live korean",
        "일렉기타 커버 방송", "애니송 기타 커버", "jpop 기타 커버 방송",
        "버튜버 기타 연주", "기타 연주 스트리머",
    ],
    "드럼연주": [
        "드럼 연주 방송", "드럼 라이브", "drum cover live korean",
        "드럼 커버 방송", "애니송 드럼 커버", "jpop 드럼 커버 방송",
        "버튜버 드럼 연주", "드럼 연주 스트리머",
        "drummer live korean", "실시간 드럼 연주",
    ],
}
STANDARD_VIDEO_COLS = [
    "video_id", "channel_id", "channel_title", "title", "description",
    "published_at", "search_keyword", "search_query_full",
    "upper_segment", "lower_segment", "segment_seed",
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


def get_upper_segment(lower_seg: str) -> Optional[str]:
    return LOWER_TO_UPPER_SEGMENT.get(lower_seg)


def get_segment_cap(lower_seg: str) -> int:
    upper = get_upper_segment(lower_seg)
    if upper is None:
        return DISCOVERY_MAX_NEW_ROWS_PER_SEGMENT
    return SEGMENT_CHANNEL_CAPS.get(upper, DISCOVERY_MAX_NEW_ROWS_PER_SEGMENT)


def get_lower_budget_map(active_lower_segments: Optional[List[str]] = None) -> Dict[str, int]:
    """
    하위 세그먼트별 수집 목표량 생성.

    BALANCED_DISCOVERY_MODE=True:
        active lower segment별 동일 목표량을 부여한다.
        특정 세그먼트만 과수집되는 편향을 완화한다.

    BALANCED_DISCOVERY_MODE=False:
        기존 config.py의 DISCOVERY_WEEKLY_BUDGET_BY_UPPER * DISCOVERY_LOWER_WEIGHT 구조를 사용한다.
    """
    if active_lower_segments is None:
        active_lower_segments = [
            lower
            for lower in LOWER_TO_UPPER_SEGMENT.keys()
            if lower in DISCOVERY_SEARCH_KEYWORDS_BY_LOWER
        ]

    active_lower_segments = list(dict.fromkeys(active_lower_segments))

    if BALANCED_DISCOVERY_MODE:
        if not active_lower_segments:
            return {}

        if BALANCED_TARGET_PER_LOWER_SEGMENT is None:
            target_per_lower = max(
                1,
                int(round(DISCOVERY_TOTAL_TARGET_CHANNELS / len(active_lower_segments)))
            )
        else:
            target_per_lower = int(BALANCED_TARGET_PER_LOWER_SEGMENT)

        return {
            lower_seg: target_per_lower
            for lower_seg in active_lower_segments
        }

    lower_budget_map = {}
    for lower_seg, upper_seg in LOWER_TO_UPPER_SEGMENT.items():
        if active_lower_segments is not None and lower_seg not in active_lower_segments:
            continue

        upper_budget = DISCOVERY_WEEKLY_BUDGET_BY_UPPER.get(upper_seg, 0)
        lower_weight = DISCOVERY_LOWER_WEIGHT.get(lower_seg, 0)

        lower_budget = int(round(upper_budget * lower_weight))
        if upper_budget > 0 and lower_weight > 0:
            lower_budget = max(lower_budget, 1)

        lower_budget_map[lower_seg] = lower_budget

    return lower_budget_map


def get_page_limit(lower_seg: str) -> int:
    """
    세그먼트별 page limit을 가져오되, 최종적으로 HARD_MAX_PAGES_PER_QUERY를 넘지 않도록 제한한다.
    search.list는 page마다 quota 100이므로 무제한 페이지 확장은 위험하다.
    """
    upper = get_upper_segment(lower_seg)

    if lower_seg in MAX_SEARCH_PAGES_BY_LOWER_SEGMENT:
        page_limit = MAX_SEARCH_PAGES_BY_LOWER_SEGMENT[lower_seg]
    elif upper in SEGMENT_PAGE_LIMITS:
        page_limit = SEGMENT_PAGE_LIMITS[upper]
    else:
        page_limit = DISCOVERY_MAX_PAGES_PER_KEYWORD

    return min(int(page_limit), int(HARD_MAX_PAGES_PER_QUERY))


def get_sort_orders(lower_seg: str) -> List[str]:
    upper = get_upper_segment(lower_seg)
    if upper in SEGMENT_SORT_STRATEGY:
        return SEGMENT_SORT_STRATEGY[upper]
    return DISCOVERY_SORT_STRATEGY


def get_keyword_limit(lower_seg: str) -> int:
    upper = get_upper_segment(lower_seg)
    if upper in SEGMENT_KEYWORD_LIMITS:
        return SEGMENT_KEYWORD_LIMITS[upper]
    return 9999


def build_queries(active_lower_segments: Optional[List[str]] = None, mode: str = "new_only") -> List[Dict]:
    queries = []
    seen = set()
    keyword_source = get_keyword_source(mode)

    for lower_seg, kws in keyword_source.items():
        if active_lower_segments is not None and lower_seg not in active_lower_segments:
            continue

        upper_seg = get_upper_segment(lower_seg)
        if upper_seg is None:
            continue

        neg_terms = LIGHT_NEGATIVE_TERMS if lower_seg in SCARCE_SEGMENTS else NEGATIVE_TERMS
        negative_clause = " ".join([f"-{term}" for term in neg_terms])

        selected_keywords = kws[:get_keyword_limit(lower_seg)]
        sort_orders = get_sort_orders(lower_seg)

        for kw in selected_keywords:
            for mod in MODIFIERS:
                base_q = normalize_query_text(f"{kw} {mod}".strip())
                if is_bad_query_pattern(base_q):
                    continue

                q = normalize_query_text(f"{base_q} {negative_clause}".strip())

                for order in sort_orders:
                    key = (upper_seg, lower_seg, q, order)
                    if key not in seen:
                        seen.add(key)
                        queries.append({
                            "upper_segment": upper_seg,
                            "lower_segment": lower_seg,
                            "segment_seed": lower_seg,
                            "base_query": base_q,
                            "query": q,
                            "search_order": order,
                            "query_mode": mode,
                        })
    return queries


def prioritize_queries(search_queries: List[Dict], query_stats: Dict[str, dict]) -> List[Dict]:
    scored = []
    for item in search_queries:
        lower_seg = item["lower_segment"]
        upper_seg = item["upper_segment"]
        order_bonus = 2 if item["search_order"] == "relevance" else 1

        qkey = f"{lower_seg}|||{item['search_order']}|||{item['query']}"
        stat = query_stats.get(qkey, {})
        historical_new_channels = int(stat.get("new_channels_total", 0))
        historical_calls = int(stat.get("search_calls_total", 0))
        historical_eff = historical_new_channels / historical_calls if historical_calls > 0 else 0
        untouched_bonus = 8 if historical_calls == 0 else 0

        seg_cap = SEGMENT_CHANNEL_CAPS.get(upper_seg, 0)
        seg_bonus = seg_cap / 100.0

        priority_score = order_bonus * 3 + historical_eff * 15 + untouched_bonus + historical_new_channels * 0.1 + seg_bonus
        scored.append({**item, "priority_score": priority_score})
    return sorted(scored, key=lambda x: x["priority_score"], reverse=True)


def round_robin_queries_by_lower_segment(search_queries: List[Dict]) -> List[Dict]:
    """
    하위 세그먼트별 query를 round-robin 방식으로 재배열한다.

    기존 priority sort만 쓰면 과거 효율이 좋은 세그먼트가 앞쪽에 몰릴 수 있다.
    이 함수는 lower_segment별로 query를 번갈아 배치해서 quota 편향을 줄인다.
    """
    buckets: Dict[str, List[Dict]] = {}

    for item in search_queries:
        lower_seg = item.get("lower_segment")
        buckets.setdefault(lower_seg, []).append(item)

    ordered_lower_segments = sorted(buckets.keys())
    result = []

    max_len = max((len(v) for v in buckets.values()), default=0)

    for i in range(max_len):
        for lower_seg in ordered_lower_segments:
            items = buckets.get(lower_seg, [])
            if i < len(items):
                result.append(items[i])

    return result


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
    published_after: Optional[str],
    published_before: Optional[str],
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
    }
    if published_after:
        params["publishedAfter"] = published_after
    if published_before:
        params["publishedBefore"] = published_before
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

    if "segment_seed_raw" not in df_new.columns and "segment_seed" in df_new.columns:
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


def build_time_windows(start_date: str, end_date: str):
    if ENABLE_DISCOVERY_DATE_SLICING and ENABLE_WEEKLY_DISCOVERY_SLICING:
        return build_week_ranges(start_date, end_date)
    return [(None, None)]


def run(start_date: Optional[str] = None, end_date: Optional[str] = None):
    global video_rows_buffer_global

    print_section("STEP2 - 일반 후보 Discovery 수집")

    if start_date is None or end_date is None:
        end_ts = pd.Timestamp.now(tz="Asia/Seoul").normalize()
        if ENABLE_DISCOVERY_DATE_SLICING and ENABLE_WEEKLY_DISCOVERY_SLICING:
            start_ts = end_ts - pd.Timedelta(days=(DISCOVERY_WEEKLY_SLICES * 7 - 1))
        else:
            start_ts = end_ts - pd.Timedelta(days=27)
        start_date = start_ts.strftime("%Y-%m-%d")
        end_date = end_ts.strftime("%Y-%m-%d")

    week_ranges = build_time_windows(start_date, end_date)
    yt = YouTubeAPIClient(api_keys=API_KEYS, request_sleep=REQUEST_SLEEP)

    current_progress = load_current_progress()
    done_pairs = set(current_progress.get("done_pairs", []))
    bad_queries = load_json_list(DISCOVERY_BAD_QUERIES_PATH)
    query_stats = load_json_dict(DISCOVERY_QUERY_STATS_PATH)
    query_error_counts = load_json_dict(DISCOVERY_QUERY_ERROR_COUNTS_PATH)

    existing_video_ids = load_json_list(USED_VIDEO_IDS_PATH)
    existing_channel_ids = load_json_list(USED_CHANNELS_PATH)

    yt_category_map = get_video_categories(yt, region_code=REGION_CODE or "KR")

    active_lower_segments = [
        seg for seg, kws in DISCOVERY_SEARCH_KEYWORDS_BY_LOWER.items()
        if len(kws) > 0 and seg in LOWER_TO_UPPER_SEGMENT
    ]
    if FORCE_ACTIVE_LOWER_SEGMENTS:
        active_lower_segments = [seg for seg in active_lower_segments if seg in FORCE_ACTIVE_LOWER_SEGMENTS]

    lower_budget_map = get_lower_budget_map(active_lower_segments)

    active_upper_segments = sorted({
        LOWER_TO_UPPER_SEGMENT[lower_seg]
        for lower_seg in active_lower_segments
        if lower_seg in LOWER_TO_UPPER_SEGMENT
    })

    search_queries = build_queries(active_lower_segments=active_lower_segments, mode=QUERY_MODE)

    # 1차: query 효율 기반 우선순위 계산
    search_queries = prioritize_queries(search_queries, query_stats)

    # 2차: 세그먼트별 round-robin 재배열
    # 특정 세그먼트 query가 앞쪽에 몰리는 것을 방지
    if BALANCED_DISCOVERY_MODE:
        search_queries = round_robin_queries_by_lower_segment(search_queries)

    upper_segment_new_channel_counts = {seg: 0 for seg in active_upper_segments}
    lower_segment_new_channel_counts = {seg: 0 for seg in active_lower_segments}
    current_run_new_channels = set()

    print_kv("기간", f"{start_date} ~ {end_date}")
    print_kv("week range 수", len(week_ranges))
    print_kv("active_upper_segments", active_upper_segments)
    print_kv("active_lower_segments", active_lower_segments)
    print_kv("upper budget", DISCOVERY_WEEKLY_BUDGET_BY_UPPER)
    print_kv("lower budget", lower_budget_map)
    print_kv("query 수", len(search_queries))
    print_kv("balanced_discovery_mode", BALANCED_DISCOVERY_MODE)
    print_kv("ignore_upper_segment_budget", IGNORE_UPPER_SEGMENT_BUDGET)
    print_kv("ignore_segment_cap", IGNORE_SEGMENT_CAP)
    print_kv("hard_max_pages_per_query", HARD_MAX_PAGES_PER_QUERY)
    print_kv("used_video_ids", len(existing_video_ids))
    print_kv("used_channels", len(existing_channel_ids))
    print_kv("discovery_total_target_channels", DISCOVERY_TOTAL_TARGET_CHANNELS)

    zero_streak_by_query = {}
    pair_counter = 0
    total_pairs = len(search_queries) * len(week_ranges)
    processed_counter = 0
    data_origin = f"youtube_discovery_{start_date}_{end_date}_{QUERY_MODE}"

    for item in search_queries:
        if len(current_run_new_channels) >= DISCOVERY_TOTAL_TARGET_CHANNELS:
            print("[STOP] DISCOVERY_TOTAL_TARGET_CHANNELS 도달")
            break

        upper_segment = item["upper_segment"]
        lower_segment = item["lower_segment"]
        segment_seed = item["segment_seed"]
        query = item["query"]
        search_order = item["search_order"]

        if IGNORE_UPPER_SEGMENT_BUDGET:
            upper_budget = DISCOVERY_TOTAL_TARGET_CHANNELS
        else:
            upper_budget = DISCOVERY_WEEKLY_BUDGET_BY_UPPER.get(upper_segment, 0)

        lower_budget = lower_budget_map.get(lower_segment, 0)

        if IGNORE_SEGMENT_CAP:
            segment_cap = DISCOVERY_TOTAL_TARGET_CHANNELS
        else:
            segment_cap = get_segment_cap(lower_segment)

        if upper_segment_new_channel_counts.get(upper_segment, 0) >= upper_budget:
            print(f"[SKIP upper budget reached] {upper_segment}")
            continue

        if lower_segment_new_channel_counts.get(lower_segment, 0) >= lower_budget:
            print(f"[SKIP lower budget reached] {lower_segment}")
            continue

        if lower_segment_new_channel_counts.get(lower_segment, 0) >= segment_cap:
            print(f"[SKIP segment cap reached] {lower_segment}")
            continue

        query_key = f"{lower_segment}|||{search_order}|||{query}"
        query_zero_limit = QUERY_ZERO_STREAK_LIMIT.get(lower_segment, 8)
        current_max_pages = get_page_limit(lower_segment)

        qstat = query_stats.get(query_key, {})
        hist_calls = int(qstat.get("search_calls_total", 0))
        hist_new = int(qstat.get("new_channels_total", 0))
        hist_eff = hist_new / hist_calls if hist_calls > 0 else None

        if QUERY_MODE == "new_only":
            if hist_calls >= 2 and hist_new == 0:
                print(f"[SKIP dead_query] {lower_segment} | {query[:60]}")
                continue
            if hist_calls >= 3 and hist_eff is not None and hist_eff < 0.2:
                print(f"[SKIP low_eff_query] {lower_segment} | eff={hist_eff:.3f} | {query[:60]}")
                continue

        if zero_streak_by_query.get(query_key, 0) >= query_zero_limit:
            print(
                f"[SKIP query] {lower_segment} | {search_order} | {query[:50]} | "
                f"zero_streak={zero_streak_by_query.get(query_key, 0)}"
            )
            continue

        for start_dt, end_dt in week_ranges:
            if len(current_run_new_channels) >= DISCOVERY_TOTAL_TARGET_CHANNELS:
                break

            if upper_segment_new_channel_counts.get(upper_segment, 0) >= upper_budget:
                break
            if lower_segment_new_channel_counts.get(lower_segment, 0) >= lower_budget:
                break
            if lower_segment_new_channel_counts.get(lower_segment, 0) >= segment_cap:
                break

            pair_counter += 1
            pair_key = f"{upper_segment}|||{lower_segment}|||{query}|||{search_order}|||{start_dt}|||{end_dt}"

            if pair_key in done_pairs:
                continue

            print(
                f"[{pair_counter}/{total_pairs}] "
                f"{upper_segment} > {lower_segment} | order={search_order} | "
                f"{(start_dt[:10] if start_dt else 'ALL')}~{(end_dt[:10] if end_dt else 'ALL')} | "
                f"upper_budget_left={upper_budget - upper_segment_new_channel_counts.get(upper_segment, 0)} | "
                f"lower_budget_left={lower_budget - lower_segment_new_channel_counts.get(lower_segment, 0)} | "
                f"segment_cap_left={segment_cap - lower_segment_new_channel_counts.get(lower_segment, 0)}"
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
                    if len(current_run_new_channels) >= DISCOVERY_TOTAL_TARGET_CHANNELS:
                        break
                    if upper_segment_new_channel_counts.get(upper_segment, 0) >= upper_budget:
                        break
                    if lower_segment_new_channel_counts.get(lower_segment, 0) >= lower_budget:
                        break
                    if lower_segment_new_channel_counts.get(lower_segment, 0) >= segment_cap:
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
                    for s in items:
                        vid = s.get("id", {}).get("videoId")
                        snippet = s.get("snippet", {})
                        ch_id = snippet.get("channelId")

                        if not vid or not ch_id:
                            continue

                        if str(vid) in existing_video_ids:
                            continue

                        if DISCOVERY_ONLY_NEW_CHANNELS and not ALLOW_REDISCOVERY_EXISTING_CHANNELS:
                            if str(ch_id) in existing_channel_ids:
                                continue

                        candidate_video_ids.append(str(vid))

                    candidate_video_ids = list(dict.fromkeys(candidate_video_ids))
                    new_video_id_cnt += len(candidate_video_ids)

                    if not candidate_video_ids:
                        page_token = search_data.get("nextPageToken")
                        if not page_token:
                            break
                        continue

                    detail_resp = yt.get_video_details(candidate_video_ids)
                    new_channel_ids_in_pair = set()

                    detail_rows = []

                    for v in detail_resp.get("items", []):
                        snippet = v.get("snippet", {})
                        stats = v.get("statistics", {})
                        content = v.get("contentDetails", {})
                        live = v.get("liveStreamingDetails", {})

                        video_id = str(v.get("id"))
                        channel_id = str(snippet.get("channelId", ""))

                        if not channel_id:
                            continue

                        if DISCOVERY_ONLY_NEW_CHANNELS and not ALLOW_REDISCOVERY_EXISTING_CHANNELS:
                            if channel_id in existing_channel_ids:
                                continue

                        if len(new_channel_ids_in_pair) >= DISCOVERY_MAX_NEW_CHANNELS_PER_QUERY:
                            continue

                        if pair_new_rows >= DISCOVERY_MAX_NEW_ROWS_PER_SEGMENT:
                            continue

                        if len(current_run_new_channels) + len(new_channel_ids_in_pair) >= DISCOVERY_TOTAL_TARGET_CHANNELS:
                            continue

                        if upper_segment_new_channel_counts.get(upper_segment, 0) + len(new_channel_ids_in_pair) >= upper_budget:
                            continue
                        if lower_segment_new_channel_counts.get(lower_segment, 0) + len(new_channel_ids_in_pair) >= lower_budget:
                            continue
                        if lower_segment_new_channel_counts.get(lower_segment, 0) + len(new_channel_ids_in_pair) >= segment_cap:
                            continue

                        channel_title = snippet.get("channelTitle")
                        title = snippet.get("title")
                        desc = snippet.get("description")
                        published_at = snippet.get("publishedAt")
                        yt_category_id = snippet.get("categoryId")
                        duration = content.get("duration")
                        duration_sec = parse_duration_to_sec(duration)

                        if duration_sec is not None and duration_sec < 60:
                            continue

                        view_count = safe_int(stats.get("viewCount"))
                        if view_count < DISCOVERY_MIN_VIEW_COUNT:
                            continue

                        row = {
                            "video_id": video_id,
                            "channel_id": channel_id,
                            "channel_title": channel_title,
                            "title": title,
                            "description": desc,
                            "published_at": published_at,
                            "search_keyword": item["base_query"],
                            "search_query_full": query,
                            "upper_segment": upper_segment,
                            "lower_segment": lower_segment,
                            "segment_seed": segment_seed,
                            "search_period_start": start_dt,
                            "search_period_end": end_dt,
                            "search_order": search_order,
                            "yt_category_id": yt_category_id,
                            "yt_category_name": yt_category_map.get(str(yt_category_id)),
                            "tags": None,
                            "custom_category": None,
                            "category_confidence": None,
                            "view_count": view_count,
                            "like_count": safe_int(stats.get("likeCount")),
                            "comment_count": safe_int(stats.get("commentCount")),
                            "duration": duration,
                            "duration_sec": duration_sec,
                            "is_live_related": detect_live_related(title or "", desc or ""),
                            "has_live_actual_start": int("actualStartTime" in live),
                        }
                        detail_rows.append(row)

                    if detail_rows:
                        tmp = pd.DataFrame(detail_rows)
                        tmp["published_at"] = pd.to_datetime(tmp["published_at"], errors="coerce", utc=True)
                        tmp = tmp.sort_values("published_at", ascending=False).head(DISCOVERY_MAX_VIDEOS_PER_KEYWORD).copy()

                        for _, row in tmp.iterrows():
                            video_id = str(row["video_id"])
                            channel_id = str(row["channel_id"])

                            if DISCOVERY_ONLY_NEW_CHANNELS and not ALLOW_REDISCOVERY_EXISTING_CHANNELS:
                                if channel_id in existing_channel_ids:
                                    continue

                            video_rows_buffer_global.append(row.to_dict())
                            existing_video_ids.add(video_id)

                            if channel_id and channel_id not in new_channel_ids_in_pair:
                                new_channel_ids_in_pair.add(channel_id)

                            pair_new_rows += 1

                    for ch_id in new_channel_ids_in_pair:
                        existing_channel_ids.add(ch_id)
                        current_run_new_channels.add(ch_id)

                    new_channel_cnt += len(new_channel_ids_in_pair)
                    upper_segment_new_channel_counts[upper_segment] += len(new_channel_ids_in_pair)
                    lower_segment_new_channel_counts[lower_segment] += len(new_channel_ids_in_pair)

                    page_token = search_data.get("nextPageToken")
                    if not page_token:
                        break

                done_pairs.add(pair_key)
                processed_counter += 1

                dedup_rate = 1 - (new_video_id_cnt / fetched_cnt) if fetched_cnt > 0 else 0.0

                if PRINT_DISCOVERY_DEBUG_LOG:
                    print(
                        f"[{upper_segment}>{lower_segment}] fetched={fetched_cnt} | "
                        f"new_video_ids={new_video_id_cnt} | new_channels={new_channel_cnt} | "
                        f"new_rows={pair_new_rows} | "
                        f"upper_progress={upper_segment_new_channel_counts.get(upper_segment, 0)}/{upper_budget} | "
                        f"lower_progress={lower_segment_new_channel_counts.get(lower_segment, 0)}/{lower_budget} | "
                        f"segment_cap={segment_cap} | dedup_rate={dedup_rate:.2%} | "
                        f"quota_total={yt.quota_used_total:,}"
                    )

                query_stats.setdefault(query_key, {})
                query_stats[query_key]["new_channels_total"] = int(query_stats[query_key].get("new_channels_total", 0)) + new_channel_cnt
                query_stats[query_key]["new_rows_total"] = int(query_stats[query_key].get("new_rows_total", 0)) + pair_new_rows
                query_stats[query_key]["search_calls_total"] = int(query_stats[query_key].get("search_calls_total", 0)) + search_calls
                query_stats[query_key]["last_dedup_rate"] = dedup_rate
                query_stats[query_key]["last_new_per_search"] = new_channel_cnt / max(search_calls, 1)

                if new_channel_cnt == 0:
                    zero_streak_by_query[query_key] = zero_streak_by_query.get(query_key, 0) + 1
                else:
                    zero_streak_by_query[query_key] = 0

                # 최대 페이지까지 탐색했는데 신규 채널이 0이면 dead query로 간주
                # 단, page_num이 current_max_pages까지 도달한 경우에만 강하게 등록
                if (
                    MARK_DEAD_QUERY_WHEN_ZERO_AFTER_MAX_PAGES
                    and new_channel_cnt == 0
                    and page_num >= current_max_pages
                ):
                    bad_queries.add(query)
                    query_stats.setdefault(query_key, {})
                    query_stats[query_key]["dead_query_reason"] = "zero_new_channel_after_max_pages"
                    query_stats[query_key]["dead_query_page_num"] = int(page_num)
                    query_stats[query_key]["dead_query_max_pages"] = int(current_max_pages)

                    print(
                        f"[DEAD_QUERY 등록] {lower_segment} | {search_order} | "
                        f"pages={page_num}/{current_max_pages} | new_channels=0 | {query[:60]}"
                    )

                if ENABLE_SEGMENT_FALLBACK_SEARCH:
                    if (
                        query_stats[query_key]["last_new_per_search"] < MIN_NEW_PER_SEARCH_THRESHOLD
                        and dedup_rate > MAX_DEDUP_RATE_THRESHOLD
                    ):
                        query_stats[query_key]["fallback_triggered"] = True

                if zero_streak_by_query.get(query_key, 0) >= query_zero_limit:
                    bad_queries.add(query)
                    print(f"[BAD_QUERY 등록] {lower_segment} | {search_order} | {query[:60]}")

                if processed_counter % CHECKPOINT_EVERY == 0:
                    flush_and_finalize(
                        raw_path=CANDIDATE_DISCOVERY_RAW_PATH,
                        target_path=CANDIDATE_DISCOVERY_MERGED_PATH,
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
                    raw_path=CANDIDATE_DISCOVERY_RAW_PATH,
                    target_path=CANDIDATE_DISCOVERY_MERGED_PATH,
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
        raw_path=CANDIDATE_DISCOVERY_RAW_PATH,
        target_path=CANDIDATE_DISCOVERY_MERGED_PATH,
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
    print("raw_path:", CANDIDATE_DISCOVERY_RAW_PATH)
    print("target_path:", CANDIDATE_DISCOVERY_MERGED_PATH)
    print("new_channels_this_run:", len(current_run_new_channels))


if __name__ == "__main__":
    run()