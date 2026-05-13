from pathlib import Path
import os
from dotenv import load_dotenv

# =========================================================
# 기본 경로
# =========================================================
# config.py는 07_code 안에 위치한다고 가정
CODE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CODE_DIR.parent

RAW_DIR = PROJECT_ROOT / "08_raw"
INTERMEDIATE_DIR = PROJECT_ROOT / "09_intermediate"
DASHBOARD_DIR = PROJECT_ROOT / "10_dashboard"
FINAL_DIR = PROJECT_ROOT / "11_final"
STATE_DIR = PROJECT_ROOT / "05_state"
LOG_DIR = PROJECT_ROOT / "06_logs"

# 세부 폴더
RAW_CIME_REFERENCE_DIR = RAW_DIR / "cime_reference_raw"
RAW_CANDIDATE_DIR = RAW_DIR / "candidate_raw"
RAW_REFERENCE_SOURCE_DIR = RAW_DIR / "reference_source"

INTERMEDIATE_AGG_DIR = INTERMEDIATE_DIR / "aggregate"
INTERMEDIATE_METADATA_DIR = INTERMEDIATE_DIR / "metadata"
INTERMEDIATE_EXPERIMENT_DIR = INTERMEDIATE_DIR / "experiments"
INTERMEDIATE_MANUAL_REVIEW_DIR = INTERMEDIATE_DIR / "manual_review"
INTERMEDIATE_RECLASSIFICATION_DIR = INTERMEDIATE_DIR / "reclassification_test"
INTERMEDIATE_REFERENCE_DIR = INTERMEDIATE_DIR / "reference"
INTERMEDIATE_SNAPSHOT_DIR = INTERMEDIATE_DIR / "snapshots"

FINAL_CORE_REFERENCE_DIR = FINAL_DIR / "core_reference"
FINAL_CORE_CANDIDATE_DIR = FINAL_DIR / "core_candidate"
FINAL_CORE_OUTPUT_DIR = FINAL_DIR / "core_output"

DASHBOARD_ASSET_DIR = DASHBOARD_DIR / "assets"
DASHBOARD_DATA_DIR = DASHBOARD_DIR / "data"

# =========================================================
# 디렉토리 생성
# =========================================================
DIRS_TO_CREATE = [
    RAW_DIR,
    INTERMEDIATE_DIR,
    DASHBOARD_DIR,
    FINAL_DIR,
    STATE_DIR,
    LOG_DIR,
    RAW_CIME_REFERENCE_DIR,
    RAW_CANDIDATE_DIR,
    RAW_REFERENCE_SOURCE_DIR,
    INTERMEDIATE_AGG_DIR,
    INTERMEDIATE_METADATA_DIR,
    INTERMEDIATE_EXPERIMENT_DIR,
    INTERMEDIATE_MANUAL_REVIEW_DIR,
    INTERMEDIATE_RECLASSIFICATION_DIR,
    INTERMEDIATE_REFERENCE_DIR,
    INTERMEDIATE_SNAPSHOT_DIR,
    FINAL_CORE_REFERENCE_DIR,
    FINAL_CORE_CANDIDATE_DIR,
    FINAL_CORE_OUTPUT_DIR,
    DASHBOARD_ASSET_DIR,
    DASHBOARD_DATA_DIR,
]

for d in DIRS_TO_CREATE:
    d.mkdir(parents=True, exist_ok=True)

# =========================================================
# CURRENT PIPELINE - MAIN FILES
# =========================================================
# STEP 1 discovery
CANDIDATE_DISCOVERY_RAW_PATH = RAW_CANDIDATE_DIR / "youtube_video_row.csv"
CANDIDATE_DISCOVERY_MERGED_PATH = RAW_CANDIDATE_DIR / "youtube_video_kr.csv"

# STEP 2 prepared
CANDIDATE_AGG_INPUT_PATH = FINAL_CORE_CANDIDATE_DIR / "youtube_channel_agg_kr_한글버전.csv"
CANDIDATE_BASE_INPUT_PATH = FINAL_CORE_CANDIDATE_DIR / "cme_cr_one_df.csv"
CANDIDATE_PREPARED_PATH = FINAL_CORE_CANDIDATE_DIR / "candidate_channel_prepared.csv"
CANDIDATE_PREPARED_BACKUP_PATH = FINAL_CORE_CANDIDATE_DIR / "candidate_channel_prepared_before_refresh.csv"

# STEP 3 refresh
CANDIDATE_REFRESH_VIDEO_RAW_PATH = RAW_CANDIDATE_DIR / "candidate_refresh_video_raw.csv"
CANDIDATE_REFRESH_VIDEO_MASTER_PATH = RAW_CANDIDATE_DIR / "candidate_refresh_video_raw_master.csv"
CANDIDATE_REFRESH_CHANNEL_META_PATH = INTERMEDIATE_AGG_DIR / "candidate_refresh_channel_meta.csv"
CANDIDATE_REFRESH_AGG_PATH = INTERMEDIATE_AGG_DIR / "candidate_refresh_agg.csv"

# STEP 5~8 current outputs
CANDIDATE_GROWTH_PROXY_PATH = FINAL_CORE_OUTPUT_DIR / "candidate_growth_proxy_from_master.csv"
CANDIDATE_FEATURE_TABLE_PATH = FINAL_CORE_OUTPUT_DIR / "candidate_feature_table.csv"
CANDIDATE_SCORED_FINAL_PATH = FINAL_CORE_OUTPUT_DIR / "candidate_scored_final.csv"

# =========================================================
# CURRENT PIPELINE - SNAPSHOTS
# =========================================================
CANDIDATE_PREPARED_SNAPSHOT_PATH = INTERMEDIATE_SNAPSHOT_DIR / "candidate_prepared_snapshot.csv"
CANDIDATE_GROWTH_PROXY_SNAPSHOT_PATH = INTERMEDIATE_SNAPSHOT_DIR / "candidate_growth_proxy_snapshot.csv"
CANDIDATE_FEATURE_SNAPSHOT_PATH = INTERMEDIATE_SNAPSHOT_DIR / "candidate_feature_snapshot.csv"
CANDIDATE_SCORED_SNAPSHOT_PATH = INTERMEDIATE_SNAPSHOT_DIR / "candidate_scored_snapshot.csv"

# =========================================================
# LEGACY / REFERENCE PIPELINE FILES
# =========================================================
LEGACY_CIME_TOP30_MAPPING_PATH = FINAL_CORE_REFERENCE_DIR / "cime_top30_youtube_mapping_template.csv"
LEGACY_CIME_TOP30_SEED_PATH = FINAL_CORE_REFERENCE_DIR / "cime_top30_seed_list.csv"

LEGACY_CIME_CHANNEL_INFO_RAW_PATH = RAW_CIME_REFERENCE_DIR / "cime_channel_info_raw.csv"
LEGACY_CIME_RECENT_VIDEO_RAW_PATH = RAW_CIME_REFERENCE_DIR / "cime_recent_video_raw.csv"
LEGACY_CIME_CHANNEL_INFO_PROCESSED_PATH = FINAL_CORE_CANDIDATE_DIR / "cme_channel_info_processed.csv"
LEGACY_CIME_TOP30_REFERENCE_PROFILE_PATH = FINAL_CORE_REFERENCE_DIR / "cime_top30_channel_reference_profile.csv"

LEGACY_CIME_REFERENCE_PROFILE_FILTERED_PATH = FINAL_CORE_REFERENCE_DIR / "cime_reference_profile_filtered.csv"
LEGACY_CIME_REFERENCE_PROFILE_SUMMARY_PATH = INTERMEDIATE_REFERENCE_DIR / "cime_reference_profile_summary.csv"
LEGACY_CIME_REFERENCE_PROFILE_DISTRIBUTION_PATH = INTERMEDIATE_REFERENCE_DIR / "cime_reference_profile_distribution_table.csv"

LEGACY_CIME_SIMILARITY_SCORED_PATH = FINAL_CORE_OUTPUT_DIR / "cime_similarity_scored_candidates.csv"
LEGACY_CIME_SIMILARITY_SEGMENT_SUMMARY_PATH = INTERMEDIATE_REFERENCE_DIR / "cime_similarity_segment_summary.csv"

LEGACY_CIME_FINAL_SHORTLIST_PATH = FINAL_CORE_OUTPUT_DIR / "cime_final_shortlist.csv"
LEGACY_CIME_FINAL_SHORTLIST_BY_SEGMENT_PATH = FINAL_CORE_OUTPUT_DIR / "cime_final_shortlist_by_segment.csv"

LEGACY_CANDIDATE_EXECUTABILITY_SCORED_PATH = FINAL_CORE_OUTPUT_DIR / "cime_executability_scored_candidates.csv"
LEGACY_CANDIDATE_FINAL_RANKED_PATH = FINAL_CORE_OUTPUT_DIR / "cime_final_ranked_candidates.csv"
LEGACY_CANDIDATE_ACTION_TABLE_PATH = FINAL_CORE_OUTPUT_DIR / "cime_action_table.csv"

# legacy snapshot
LEGACY_SHORTLIST_SNAPSHOT_PATH = INTERMEDIATE_SNAPSHOT_DIR / "shortlist_snapshot.csv"
LEGACY_EXECUTABILITY_SNAPSHOT_PATH = INTERMEDIATE_SNAPSHOT_DIR / "executability_score_snapshot.csv"
LEGACY_FINAL_RANKED_SNAPSHOT_PATH = INTERMEDIATE_SNAPSHOT_DIR / "final_ranked_snapshot.csv"
LEGACY_ACTION_TABLE_SNAPSHOT_PATH = INTERMEDIATE_SNAPSHOT_DIR / "action_table_snapshot.csv"

# =========================================================
# DASHBOARD OUTPUTS
# =========================================================
DASHBOARD_SUMMARY_PATH = DASHBOARD_DATA_DIR / "dashboard_summary.csv"
DASHBOARD_CANDIDATE_TABLE_PATH = DASHBOARD_DATA_DIR / "dashboard_candidate_table.csv"
DASHBOARD_SEGMENT_TABLE_PATH = DASHBOARD_DATA_DIR / "dashboard_segment_table.csv"
DASHBOARD_REFERENCE_TABLE_PATH = DASHBOARD_DATA_DIR / "dashboard_reference_table.csv"

# =========================================================
# SOURCE / REFERENCE RAW
# =========================================================
SOFTCON_RANKING_SOURCE_PATH = RAW_REFERENCE_SOURCE_DIR / "소프트콘_랭킹_20260426_140721.csv"

LEGACY_CIME_CATEGORY_RANKING_SOURCE_PATH = RAW_REFERENCE_SOURCE_DIR / "카테고리_랭킹_cime.csv"
SOOP_CATEGORY_RANKING_SOURCE_PATH = RAW_REFERENCE_SOURCE_DIR / "카테고리_랭킹_soop.csv"
CHZZK_CATEGORY_RANKING_SOURCE_PATH = RAW_REFERENCE_SOURCE_DIR / "카테고리_랭킹_chzzk.csv"

PLATFORM_CATEGORY_SOURCE_PATHS = {
    "씨미": LEGACY_CIME_CATEGORY_RANKING_SOURCE_PATH,
    "SOOP": SOOP_CATEGORY_RANKING_SOURCE_PATH,
    "치지직": CHZZK_CATEGORY_RANKING_SOURCE_PATH,
}

PLATFORM_CATEGORY_META_RAW_PATH = INTERMEDIATE_REFERENCE_DIR / "platform_category_meta_raw.csv"
PLATFORM_CATEGORY_META_PROFILE_PATH = INTERMEDIATE_REFERENCE_DIR / "platform_category_meta_profile.csv"
PLATFORM_CATEGORY_META_SEGMENT_SCORE_PATH = INTERMEDIATE_REFERENCE_DIR / "platform_category_meta_segment_score.csv"

# =========================================================
# LOG / STATE
# =========================================================
PIPELINE_LOG_PATH = LOG_DIR / "pipeline.log"
STATE_PROGRESS_PATH = STATE_DIR / "pipeline_progress.json"

USED_VIDEO_IDS_PATH = STATE_DIR / "used_video_ids.json"
USED_CHANNELS_PATH = STATE_DIR / "used_channels.json"
VIDEO_CATEGORY_MAP_PATH = STATE_DIR / "video_category_map_kr.json"

BAD_QUERIES_ARCHIVE_PATH = STATE_DIR / "archive_bad_queries.json"
QUERY_STATS_ARCHIVE_PATH = STATE_DIR / "archive_query_stats.json"
QUERY_ERROR_COUNTS_ARCHIVE_PATH = STATE_DIR / "archive_query_error_counts.json"

CANDIDATE_COLLECT_PROGRESS_PATH = STATE_DIR / "candidate_collect_progress.json"
REFERENCE_COLLECT_PROGRESS_PATH = STATE_DIR / "reference_collect_progress.json"

DISCOVERY_PROGRESS_PATH = STATE_DIR / "candidate_discovery_progress.json"
REFRESH_PROGRESS_PATH = STATE_DIR / "candidate_refresh_progress.json"

DISCOVERY_BAD_QUERIES_PATH = STATE_DIR / "discovery_bad_queries.json"
DISCOVERY_QUERY_STATS_PATH = STATE_DIR / "discovery_query_stats.json"
DISCOVERY_QUERY_ERROR_COUNTS_PATH = STATE_DIR / "discovery_query_error_counts.json"

# =========================================================
# YouTube API 설정
# =========================================================
load_dotenv(PROJECT_ROOT / ".env")

_api_keys_raw = os.getenv("YOUTUBE_API_KEYS", "").strip()
API_KEYS = [x.strip() for x in _api_keys_raw.split(",") if x.strip()]

REQUEST_SLEEP = 0.12
CHECKPOINT_EVERY = 5
RECENT_VIDEO_TARGET = 10
MIN_DURATION_SEC = 60
MAX_PLAYLIST_PAGES = 10

# =========================================================
# 후보 필터링 기준
# =========================================================
MIN_SUBSCRIBERS_FOR_CANDIDATE = 1000
MIN_VIDEO_SAMPLE_FOR_CANDIDATE = 2

# =========================================================
# LEGACY REFERENCE FILTER 기준
# =========================================================
REF_MIN_SUBSCRIBERS = 100
REF_MIN_TOTAL_VIDEOS = 3
REF_MIN_RECENT_VIDEOS = 3

REF_STRICT_MIN_SUBSCRIBERS = 500
REF_STRICT_MIN_TOTAL_VIDEOS = 5
REF_STRICT_MIN_RECENT_VIDEOS = 5

# =========================================================
# LEGACY shortlist 기본 파라미터
# =========================================================
SHORTLIST_TOP_N = 30
SIMILARITY_TOP_QUANTILE = 0.75
VIEW_QUANTILE = 0.50
ENGAGEMENT_QUANTILE = 0.50

# =========================================================
# 실행 옵션
# =========================================================
USE_ONLY_MAIN_CHANNELS = True
USE_REFERENCE_STRICT_FIRST = True

# =========================================================
# 검색 기본 파라미터
# =========================================================
SEARCH_MAX_RESULTS = 50
MAX_SEARCH_PAGES = 1
REGION_CODE = "KR"
RELEVANCE_LANGUAGE = "ko"
SEARCH_ORDERS = ["date", "relevance"]

NEGATIVE_TERMS = [
    "브이로그", "vlog", "playlist", "플레이리스트", "radio", "라디오",
    "bgm", "힐링음악", "트로트", "7080", "8090", "뉴스",
    "공식", "official", "시청", "구청", "공단"
]

LIGHT_NEGATIVE_TERMS = [
    "브이로그", "vlog", "playlist", "플레이리스트",
    "official", "공식",
]

MODIFIERS = [""]

FINAL_VIDEO_COLS = [
    "video_id",
    "channel_id",
    "channel_title",
    "title",
    "description",
    "published_at",
    "search_keyword",
    "upper_segment",
    "lower_segment",
    "segment_seed",
    "search_period_start",
    "search_period_end",
    "search_order",
    "yt_category_id",
    "yt_category_name",
    "view_count",
    "like_count",
    "comment_count",
    "duration",
    "duration_sec",
    "is_live_related",
    "has_live_actual_start",
    "data_origin",
]

# =========================================================
# 상위/하위 세그먼트 구조
# =========================================================
SEGMENT_HIERARCHY = {
    "버츄얼 퍼포먼스형": [
        "버튜버",
        "버추얼",
        "버추얼토크",
    ],
    "음악·보이스형": [
        "JPOP커버",
        "애니송커버",
        "ASMR",
        "성우더빙",
        "보컬로이드JPOP커버",
        "ASMR보이스",
        "성우",
        "커버",
        "노래",
        "음악",
        "일렉기타연주",
        "드럼연주",
    ],
    "게임 실황형": [
        "원신",
        "젠레스존제로",
        "블루아카이브",
        "붕괴스타레일",
        "명조",
        "명일방주",
        "니케",
        "로블록스",
        "마인크래프트",
        "발로란트",
        "롤",
        "종합게임",
        "이터널리턴",
        "붉은사막",
        "오버워치",
        "스타크래프트",
        "리그오브레전드",
    ],
    "창작·비주얼형": [
        "코스프레",
        "일러스트리깅",
        "일러스트",
        "리깅",
        "그림",
    ],
    "서브컬쳐 토크·팬덤형": [
        "저스트채팅",
        "저스트 채팅",
        "토크",
        "talk",
        "토크캠방",
        "덕질토크",
        "애니게임토크",
    ],
}

LOWER_TO_UPPER_SEGMENT = {
    lower: upper
    for upper, lowers in SEGMENT_HIERARCHY.items()
    for lower in lowers
}

# =========================================================
# 하위세그먼트별 검색 키워드
# =========================================================
DISCOVERY_SEARCH_KEYWORDS_BY_LOWER = {
    "버튜버": [
        "버튜버 방송", "버츄얼 방송", "버튜버 라이브", "버츄얼 라이브",
        "버튜버 노래방송", "버튜버 게임방송",
    ],
    "로블록스": [
        "로블록스 방송", "로블록스 라이브", "로블록스 스트리머",
        "roblox live korean", "로블록스 버튜버", "로블록스 합방",
    ],
    "마인크래프트": [
        "마인크래프트 방송", "마인크래프트 라이브", "minecraft live korean",
        "마크 방송", "마크 버튜버",
    ],
    "발로란트": [
        "발로란트 방송", "발로란트 라이브", "발로란트 스트리머",
        "valorant live korean", "발로란트 버튜버", "발로란트 합방",
    ],
    "JPOP커버": [
        "jpop cover live", "jpop 커버 라이브", "일본노래 커버 방송",
        "jpop 노래방송", "버튜버 jpop cover",
    ],
    "애니송커버": [
        "애니송 커버 라이브", "anime song cover live", "애니노래 커버 방송",
        "버튜버 애니송 커버", "애니송 노래방송",
    ],
    "성우더빙": [
        "성우 방송", "더빙 방송", "성우 라이브",
        "버츄얼 더빙", "성우 연기 방송", "보이스 연기 라이브",
    ],
    "ASMR": [
        "asmr 방송", "asmr live korean", "버튜버 asmr", "roleplay asmr live",
    ],
    "코스프레": [
        "코스프레 방송", "코스프레 라이브", "cosplay live korean",
        "코스어 방송", "버튜버 코스프레",
    ],
    "원신": [
        "원신 방송", "genshin live korean", "원신 스트리머",
        "원신 버튜버", "원신 합방",
    ],
    "젠레스존제로": [
        "젠레스존제로 방송", "zzz live korean", "젠레스 방송",
        "젠레스 버튜버", "젠레스 스트리머",
    ],
    "블루아카이브": [
        "블루아카이브 방송", "블루아카 라이브", "blue archive stream",
    ],
    "붕괴스타레일": [
        "붕괴스타레일 방송", "붕스 방송", "star rail stream",
    ],
    "명조": [
        "명조 방송", "wuthering waves stream",
    ],
    "명일방주": [
        "명일방주 방송", "arknights stream",
    ],
    "니케": [
        "니케 방송", "승리의 여신 니케 방송", "nikke stream",
    ],
}

DISCOVERY_SEARCH_KEYWORDS_BY_LOWER.update({
    "롤": [
        "리그오브레전드 방송", "롤 방송", "롤 라이브",
        "league of legends live korean", "lol streamer korea",
        "롤 버튜버", "롤 합방",
    ],
    "성우": [
        "성우 방송", "성우 라이브", "보이스 연기 방송",
        "성우 토크", "voice acting live korean",
    ],
    "커버": [
        "노래 커버 방송", "cover live korean", "버튜버 노래 커버",
        "보컬 커버 방송",
    ],
    "보컬로이드JPOP커버": [
        "보컬로이드 커버 라이브", "vocaloid cover korean",
        "우타이테 커버 방송", "보카로 커버 방송",
    ],
    "ASMR보이스": [
        "보이스 asmr", "상황극 asmr", "roleplay asmr live",
        "한국어 보이스 asmr",
    ],
    "일러스트리깅": [
        "일러스트 방송", "그림 방송", "리깅 방송",
        "버튜버 리깅", "drawing live korean", "rigging live korean",
    ],
    "저스트채팅": [
        "저스트 채팅", "잡담 방송", "토크 방송", "talk live korean",
        "버튜버 잡담", "서브컬처 토크 방송",
    ],
    "일렉기타연주": [
        "일렉기타 연주 방송",
        "일렉기타 라이브",
        "기타 연주 방송",
        "guitar cover live korean",
        "electric guitar live korean",
        "일렉기타 커버 방송",
        "애니송 기타 커버",
        "jpop 기타 커버 방송",
        "버튜버 기타 연주",
        "기타 연주 스트리머",
    ],
    "드럼연주": [
        "드럼 연주 방송",
        "드럼 라이브",
        "drum cover live korean",
        "드럼 커버 방송",
        "애니송 드럼 커버",
        "jpop 드럼 커버 방송",
        "버튜버 드럼 연주",
        "드럼 연주 스트리머",
        "drummer live korean",
        "실시간 드럼 연주",
    ],
})

# =========================================================
# 상위세그먼트 기준 주간 budget
# =========================================================
DISCOVERY_WEEKLY_BUDGET_BY_UPPER = {
    "버츄얼 퍼포먼스형": 28,
    "음악·보이스형": 34,
    "게임 실황형": 28,
    "창작·비주얼형": 18,
    "서브컬쳐 토크·팬덤형": 20,
}

# =========================================================
# 하위세그먼트별 상위 budget 내 분산 비율
# =========================================================
DISCOVERY_LOWER_WEIGHT = {
    "버튜버": 1.0,

    "JPOP커버": 0.22,
    "애니송커버": 0.18,
    "ASMR": 0.18,
    "성우더빙": 0.12,
    "보컬로이드JPOP커버": 0.06,
    "ASMR보이스": 0.06,
    "성우": 0.06,
    "커버": 0.06,
    "노래": 0.04,
    "음악": 0.04,
    "일렉기타연주": 0.20,
    "드럼연주": 0.18,

    "원신": 0.12,
    "젠레스존제로": 0.10,
    "블루아카이브": 0.10,
    "붕괴스타레일": 0.10,
    "명조": 0.09,
    "명일방주": 0.09,
    "니케": 0.09,
    "로블록스": 0.11,
    "마인크래프트": 0.10,
    "발로란트": 0.10,
    "롤": 0.10,
    "종합게임": 0.08,
    "이터널리턴": 0.06,
    "붉은사막": 0.04,
    "오버워치": 0.08,
    "스타크래프트": 0.06,
    "리그오브레전드": 0.06,

    "코스프레": 0.35,
    "일러스트리깅": 0.30,
    "일러스트": 0.15,
    "리깅": 0.10,
    "그림": 0.10,

    "저스트채팅": 0.20,
    "저스트 채팅": 0.20,
    "토크": 0.15,
    "talk": 0.10,
    "토크캠방": 0.10,
    "덕질토크": 0.15,
    "애니게임토크": 0.10,
}

# =========================================================
# 호환용 기존 세그먼트 변수
# =========================================================
TARGET_SEGMENTS = list(DISCOVERY_SEARCH_KEYWORDS_BY_LOWER.keys())
BASE_KEYWORDS = DISCOVERY_SEARCH_KEYWORDS_BY_LOWER.copy()

DISCOVERY_WEEKLY_BUDGET = {
    lower: max(
        1,
        int(round(
            DISCOVERY_WEEKLY_BUDGET_BY_UPPER.get(LOWER_TO_UPPER_SEGMENT.get(lower, ""), 0)
            * DISCOVERY_LOWER_WEIGHT.get(lower, 0)
        ))
    )
    for lower in TARGET_SEGMENTS
}

DISCOVERY_MAX_NEW_CHANNELS_PER_QUERY = 5
DISCOVERY_MAX_NEW_ROWS_PER_SEGMENT = 200

# =========================================================
# 신규 채널 탐색 / 후보 Discovery 운영 파라미터
# =========================================================
DISCOVERY_TOTAL_TARGET_CHANNELS = 2000
DISCOVERY_MAX_PAGES_PER_KEYWORD = 3
DISCOVERY_MAX_VIDEOS_PER_KEYWORD = 150
DISCOVERY_MIN_VIEW_COUNT = 100

DISCOVERY_ONLY_NEW_CHANNELS = True
ALLOW_REDISCOVERY_EXISTING_CHANNELS = False
REDISCOVERY_STALE_DAYS = 30

MIN_NEW_PER_SEARCH_THRESHOLD = 0.15
MAX_DEDUP_RATE_THRESHOLD = 0.85

ENABLE_SEGMENT_FALLBACK_SEARCH = True
FALLBACK_EXTRA_PAGES = 2

DISCOVERY_SORT_STRATEGY = ["relevance", "date"]

SEGMENT_CHANNEL_CAPS = {
    "버츄얼 퍼포먼스형": 300,
    "음악·보이스형": 500,
    "게임 실황형": 400,
    "창작·비주얼형": 450,
    "서브컬쳐 토크·팬덤형": 250,
}

SEGMENT_PAGE_LIMITS = {
    "버츄얼 퍼포먼스형": 3,
    "음악·보이스형": 5,
    "게임 실황형": 3,
    "창작·비주얼형": 4,
    "서브컬쳐 토크·팬덤형": 3,
}

SEGMENT_KEYWORD_LIMITS = {
    "버츄얼 퍼포먼스형": 15,
    "음악·보이스형": 35,
    "게임 실황형": 20,
    "창작·비주얼형": 20,
    "서브컬쳐 토크·팬덤형": 12,
}

SEGMENT_SORT_STRATEGY = {
    "버츄얼 퍼포먼스형": ["relevance", "date"],
    "음악·보이스형": ["date", "relevance"],
    "게임 실황형": ["relevance", "date"],
    "창작·비주얼형": ["relevance", "date"],
    "서브컬쳐 토크·팬덤형": ["relevance", "date"],
}

ENABLE_DISCOVERY_DATE_SLICING = True
ENABLE_WEEKLY_DISCOVERY_SLICING = True
DISCOVERY_WEEKLY_SLICES = 4

PRINT_DISCOVERY_DEBUG_LOG = True
SAVE_DISCOVERY_SEGMENT_LOG = True

# =========================================================
# 게임 하위세그먼트 해석용 재분류
# =========================================================
GAME_SUBSEGMENT_GROUP_MAP = {
    "롤": "대중형 게임",
    "리그오브레전드": "대중형 게임",
    "발로란트": "대중형 게임",
    "오버워치": "대중형 게임",
    "배그": "대중형 게임",
    "배틀그라운드": "대중형 게임",
    "스타크래프트": "대중형 게임",
    "이터널리턴": "대중형 게임",

    "원신": "서브컬처형 게임",
    "젠레스존제로": "서브컬처형 게임",
    "블루아카이브": "서브컬처형 게임",
    "붕괴스타레일": "서브컬처형 게임",
    "명조": "서브컬처형 게임",
    "명일방주": "서브컬처형 게임",
    "니케": "서브컬처형 게임",

    "로블록스": "종합게임형",
    "마인크래프트": "종합게임형",
    "종합게임": "종합게임형",
    "붉은사막": "종합게임형",
}

GAME_GROUP_ORDER = [
    "대중형 게임",
    "서브컬처형 게임",
    "종합게임형",
]

def map_game_group(lower_segment: str) -> str:
    return GAME_SUBSEGMENT_GROUP_MAP.get(lower_segment, "기타 게임")

REFRESH_RECENT_VIDEO_TARGET = 10
REFRESH_MAX_CHANNELS = 300

SCARCE_SEGMENTS = {
    "원신", "젠레스존제로", "애니송커버", "블루아카이브", "붕괴스타레일",
    "명조", "명일방주", "니케", "ASMR"
}

# =========================================================
# 성장성 점수 계산 파라미터
# =========================================================
GROWTH_TOP_N = 800
GROWTH_MAX_PLAYLIST_PAGES = 20
GROWTH_RECENT_VIDEO_CAP = 400
GROWTH_LOOKBACK_DAYS = 90

GROWTH_MIN_TOTAL_VIDEOS = 2
GROWTH_MIN_CUR30_VIDEOS = 1
GROWTH_MIN_PREV30_VIDEOS = 1
GROWTH_MIN_CUR7_VIDEOS = 1
GROWTH_MIN_PREV7_VIDEOS = 1

# =========================================================
# executability 관련
# =========================================================
EXEC_RECENT_UPLOAD_GOOD = 8
EXEC_RECENT_UPLOAD_MID = 4
EXEC_RECENT_UPLOAD_LOW = 1

# =========================================================
# action bucket 분위수 기준
# =========================================================
ACTION_IMMEDIATE_TOP_PCT = 0.10
ACTION_GROWTH_TOP_PCT = 0.20
ACTION_EXEC_LOW_PCT = 0.15
ACTION_FIT_HIGH_PCT = 0.25
ACTION_EXEC_HIGH_PCT = 0.40

# =========================================================
# 플랫폼 카테고리 전략 점수 가중치
# =========================================================
PLATFORM_META_CURRENT_FIT_WEIGHT = 0.55
PLATFORM_META_EXPANSION_WEIGHT = 0.45

# =========================================================
# 최종 점수 가중치
# =========================================================
FINAL_WEIGHT_BASE = 0.40
FINAL_WEIGHT_GROWTH = 0.20
FINAL_WEIGHT_EXEC = 0.15
FINAL_WEIGHT_PLATFORM_META = 0.20
FINAL_WEIGHT_RECENT_VIEW = 0.025
FINAL_WEIGHT_RECENT_ENG = 0.025

# =========================================================
# BACKWARD COMPATIBILITY ALIASES
# 기존 코드가 아직 old 변수명을 참조할 수 있으므로 alias 유지
# =========================================================

# current aliases
CANDIDATE_VIDEO_RAW_PATH = CANDIDATE_DISCOVERY_RAW_PATH
CANDIDATE_VIDEO_KR_PATH = CANDIDATE_DISCOVERY_MERGED_PATH
CANDIDATE_SCORING_BASE_PATH = CANDIDATE_FEATURE_TABLE_PATH
CANDIDATE_SCORING_BASE_SNAPSHOT_PATH = CANDIDATE_FEATURE_SNAPSHOT_PATH

# legacy aliases
CIME_TOP30_MAPPING_PATH = LEGACY_CIME_TOP30_MAPPING_PATH
CIME_TOP30_SEED_PATH = LEGACY_CIME_TOP30_SEED_PATH

CIME_CHANNEL_INFO_RAW_PATH = LEGACY_CIME_CHANNEL_INFO_RAW_PATH
CIME_RECENT_VIDEO_RAW_PATH = LEGACY_CIME_RECENT_VIDEO_RAW_PATH
CIME_CHANNEL_INFO_PROCESSED_PATH = LEGACY_CIME_CHANNEL_INFO_PROCESSED_PATH
CIME_TOP30_REFERENCE_PROFILE_PATH = LEGACY_CIME_TOP30_REFERENCE_PROFILE_PATH

CIME_REFERENCE_PROFILE_FILTERED_PATH = LEGACY_CIME_REFERENCE_PROFILE_FILTERED_PATH
CIME_REFERENCE_PROFILE_SUMMARY_PATH = LEGACY_CIME_REFERENCE_PROFILE_SUMMARY_PATH
CIME_REFERENCE_PROFILE_DISTRIBUTION_PATH = LEGACY_CIME_REFERENCE_PROFILE_DISTRIBUTION_PATH

CIME_SIMILARITY_SCORED_PATH = LEGACY_CIME_SIMILARITY_SCORED_PATH
CIME_SIMILARITY_SEGMENT_SUMMARY_PATH = LEGACY_CIME_SIMILARITY_SEGMENT_SUMMARY_PATH

CIME_FINAL_SHORTLIST_PATH = LEGACY_CIME_FINAL_SHORTLIST_PATH
CIME_FINAL_SHORTLIST_BY_SEGMENT_PATH = LEGACY_CIME_FINAL_SHORTLIST_BY_SEGMENT_PATH

CANDIDATE_EXECUTABILITY_SCORED_PATH = LEGACY_CANDIDATE_EXECUTABILITY_SCORED_PATH
CANDIDATE_FINAL_RANKED_PATH = LEGACY_CANDIDATE_FINAL_RANKED_PATH
CANDIDATE_ACTION_TABLE_PATH = LEGACY_CANDIDATE_ACTION_TABLE_PATH

SIMILARITY_SCORED_SNAPSHOT_PATH = CANDIDATE_SCORED_SNAPSHOT_PATH
SHORTLIST_SNAPSHOT_PATH = LEGACY_SHORTLIST_SNAPSHOT_PATH
GROWTH_SNAPSHOT_PATH = CANDIDATE_GROWTH_PROXY_SNAPSHOT_PATH
EXECUTABILITY_SNAPSHOT_PATH = LEGACY_EXECUTABILITY_SNAPSHOT_PATH
FINAL_RANKED_SNAPSHOT_PATH = LEGACY_FINAL_RANKED_SNAPSHOT_PATH
ACTION_TABLE_SNAPSHOT_PATH = LEGACY_ACTION_TABLE_SNAPSHOT_PATH

CIME_CATEGORY_RANKING_SOURCE_PATH = LEGACY_CIME_CATEGORY_RANKING_SOURCE_PATH