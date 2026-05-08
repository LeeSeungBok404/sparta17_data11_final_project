from pathlib import Path
from pathlib import Path
import os
from dotenv import load_dotenv

# =========================================================
# 기본 경로
# =========================================================
# config.py가 07_code 안에 있어야함
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

INTERMEDIATE_AGG_DIR = INTERMEDIATE_DIR / "aggregate"
INTERMEDIATE_METADATA_DIR = INTERMEDIATE_DIR / "metadata"
INTERMEDIATE_EXPERIMENT_DIR = INTERMEDIATE_DIR / "experiments"
INTERMEDIATE_MANUAL_REVIEW_DIR = INTERMEDIATE_DIR / "manual_review"
INTERMEDIATE_RECLASSIFICATION_DIR = INTERMEDIATE_DIR / "reclassification_test"
INTERMEDIATE_REFERENCE_DIR = INTERMEDIATE_DIR / "reference"

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
    INTERMEDIATE_AGG_DIR,
    INTERMEDIATE_METADATA_DIR,
    INTERMEDIATE_EXPERIMENT_DIR,
    INTERMEDIATE_MANUAL_REVIEW_DIR,
    INTERMEDIATE_RECLASSIFICATION_DIR,
    INTERMEDIATE_REFERENCE_DIR,
    FINAL_CORE_REFERENCE_DIR,
    FINAL_CORE_CANDIDATE_DIR,
    FINAL_CORE_OUTPUT_DIR,
    DASHBOARD_ASSET_DIR,
    DASHBOARD_DATA_DIR,
]

for d in DIRS_TO_CREATE:
    d.mkdir(parents=True, exist_ok=True)

# =========================================================
# 입력 파일
# =========================================================
CIME_TOP30_MAPPING_PATH = FINAL_CORE_REFERENCE_DIR / "cime_top30_youtube_mapping_template.csv"
CIME_TOP30_SEED_PATH = FINAL_CORE_REFERENCE_DIR / "cime_top30_seed_list.csv"

CANDIDATE_AGG_INPUT_PATH = FINAL_CORE_CANDIDATE_DIR / "youtube_channel_agg_kr_한글버전.csv"
CANDIDATE_BASE_INPUT_PATH = FINAL_CORE_CANDIDATE_DIR / "cme_cr_one_df.csv"

# =========================================================
# STEP 1: CME 레퍼런스 수집 결과
# =========================================================
CIME_CHANNEL_INFO_RAW_PATH = RAW_CIME_REFERENCE_DIR / "cime_channel_info_raw.csv"
CIME_RECENT_VIDEO_RAW_PATH = RAW_CIME_REFERENCE_DIR / "cime_recent_video_raw.csv"
CIME_CHANNEL_INFO_PROCESSED_PATH = FINAL_CORE_CANDIDATE_DIR / "cme_channel_info_processed.csv"
CIME_TOP30_REFERENCE_PROFILE_PATH = FINAL_CORE_REFERENCE_DIR / "cime_top30_channel_reference_profile.csv"

# =========================================================
# STEP 3: 레퍼런스 프로필 결과
# =========================================================
CIME_REFERENCE_PROFILE_FILTERED_PATH = FINAL_CORE_REFERENCE_DIR / "cime_reference_profile_filtered.csv"
CIME_REFERENCE_PROFILE_SUMMARY_PATH = INTERMEDIATE_REFERENCE_DIR / "cime_reference_profile_summary.csv"
CIME_REFERENCE_PROFILE_DISTRIBUTION_PATH = INTERMEDIATE_REFERENCE_DIR / "cime_reference_profile_distribution_table.csv"

# =========================================================
# STEP 4: 유사도 계산 결과
# =========================================================
CIME_SIMILARITY_SCORED_PATH = FINAL_CORE_OUTPUT_DIR / "cime_similarity_scored_candidates.csv"
CIME_SIMILARITY_SEGMENT_SUMMARY_PATH = INTERMEDIATE_REFERENCE_DIR / "cime_similarity_segment_summary.csv"

# =========================================================
# STEP 5: shortlist 결과
# =========================================================
CIME_FINAL_SHORTLIST_PATH = FINAL_CORE_OUTPUT_DIR / "cime_final_shortlist.csv"
CIME_FINAL_SHORTLIST_BY_SEGMENT_PATH = FINAL_CORE_OUTPUT_DIR / "cime_final_shortlist_by_segment.csv"

# =========================================================
# STEP 6: 대시보드용 결과
# =========================================================
DASHBOARD_SUMMARY_PATH = DASHBOARD_DATA_DIR / "dashboard_summary.csv"
DASHBOARD_CANDIDATE_TABLE_PATH = DASHBOARD_DATA_DIR / "dashboard_candidate_table.csv"
DASHBOARD_SEGMENT_TABLE_PATH = DASHBOARD_DATA_DIR / "dashboard_segment_table.csv"
DASHBOARD_REFERENCE_TABLE_PATH = DASHBOARD_DATA_DIR / "dashboard_reference_table.csv"

# =========================================================
# 로그 / state
# =========================================================
PIPELINE_LOG_PATH = LOG_DIR / "pipeline.log"
STATE_PROGRESS_PATH = STATE_DIR / "pipeline_progress.json"

# =========================================================
# YouTube API 관련 파라미터
# =========================================================
from pathlib import Path
import os
from dotenv import load_dotenv

CODE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CODE_DIR.parent

load_dotenv(PROJECT_ROOT / ".env")

_api_keys_raw = os.getenv("YOUTUBE_API_KEYS", "").strip()

API_KEYS = [
    x.strip()
    for x in _api_keys_raw.split(",")
    if x.strip()
]

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
# 레퍼런스 자동 추천 기준
# =========================================================
REF_MIN_SUBSCRIBERS = 100
REF_MIN_TOTAL_VIDEOS = 3
REF_MIN_RECENT_VIDEOS = 3

REF_STRICT_MIN_SUBSCRIBERS = 500
REF_STRICT_MIN_TOTAL_VIDEOS = 5
REF_STRICT_MIN_RECENT_VIDEOS = 5

# =========================================================
# shortlist 기본 파라미터
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
# STEP 2: 후보 수집 관련 경로 / 상태 파일
# =========================================================
RAW_REFERENCE_SOURCE_DIR = RAW_DIR / "reference_source"
RAW_REFERENCE_SOURCE_DIR.mkdir(parents=True, exist_ok=True)

CANDIDATE_VIDEO_RAW_PATH = RAW_CANDIDATE_DIR / "youtube_video_row.csv"
CANDIDATE_VIDEO_KR_PATH = RAW_CANDIDATE_DIR / "youtube_video_kr.csv"
SOFTCON_RANKING_SOURCE_PATH = RAW_REFERENCE_SOURCE_DIR / "소프트콘_랭킹_20260426_140721.csv"

USED_VIDEO_IDS_PATH = STATE_DIR / "used_video_ids.json"
USED_CHANNELS_PATH = STATE_DIR / "used_channels.json"
VIDEO_CATEGORY_MAP_PATH = STATE_DIR / "video_category_map_kr.json"

BAD_QUERIES_ARCHIVE_PATH = STATE_DIR / "archive_bad_queries.json"
QUERY_STATS_ARCHIVE_PATH = STATE_DIR / "archive_query_stats.json"
QUERY_ERROR_COUNTS_ARCHIVE_PATH = STATE_DIR / "archive_query_error_counts.json"

CANDIDATE_COLLECT_PROGRESS_PATH = STATE_DIR / "candidate_collect_progress.json"
REFERENCE_COLLECT_PROGRESS_PATH = STATE_DIR / "reference_collect_progress.json"

# =========================================================
# 후보 수집 파라미터
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

TARGET_SEGMENTS = [
    "버튜버",
    "로블록스",
    "발로란트",
    "JPOP커버",
    "애니송커버",
    "성우더빙",
    "ASMR",
    "코스프레",
    "원신",
    "젠레스존제로",
]

BASE_KEYWORDS = {
    "버튜버": [
        "버튜버 방송", "버츄얼 방송", "버튜버 라이브", "버츄얼 라이브",
        "버튜버 노래방송", "버튜버 게임방송",
    ],
    "로블록스": [
        "로블록스 방송", "로블록스 라이브", "로블록스 스트리머",
        "roblox live korean", "로블록스 버튜버", "로블록스 합방",
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
}

MODIFIERS = [""]

FINAL_VIDEO_COLS = [
    "video_id",
    "channel_id",
    "channel_title",
    "title",
    "description",
    "published_at",
    "search_keyword",
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
# Discovery / Refresh 추가 경로
# =========================================================
CANDIDATE_REFRESH_VIDEO_RAW_PATH = RAW_CANDIDATE_DIR / "candidate_refresh_video_raw.csv"
CANDIDATE_REFRESH_CHANNEL_META_PATH = INTERMEDIATE_AGG_DIR / "candidate_refresh_channel_meta.csv"
CANDIDATE_REFRESH_AGG_PATH = INTERMEDIATE_AGG_DIR / "candidate_refresh_agg.csv"

DISCOVERY_PROGRESS_PATH = STATE_DIR / "candidate_discovery_progress.json"
REFRESH_PROGRESS_PATH = STATE_DIR / "candidate_refresh_progress.json"

DISCOVERY_BAD_QUERIES_PATH = STATE_DIR / "discovery_bad_queries.json"
DISCOVERY_QUERY_STATS_PATH = STATE_DIR / "discovery_query_stats.json"
DISCOVERY_QUERY_ERROR_COUNTS_PATH = STATE_DIR / "discovery_query_error_counts.json"

# =========================================================
# Discovery 주간 예산
# =========================================================
DISCOVERY_WEEKLY_BUDGET = {
    "버튜버": 20,
    "로블록스": 15,
    "마인크래프트": 15,
    "발로란트": 15,
    "JPOP커버": 15,
    "애니송커버": 15,
    "ASMR": 15,
    "원신": 12,
    "젠레스존제로": 12,
    "블루아카이브": 12,
    "붕괴스타레일": 12,
    "명조": 10,
    "명일방주": 10,
    "니케": 10,
}

DISCOVERY_MAX_NEW_CHANNELS_PER_QUERY = 5
DISCOVERY_MAX_NEW_ROWS_PER_SEGMENT = 200

REFRESH_RECENT_VIDEO_TARGET = 10
REFRESH_MAX_CHANNELS = 300

LIGHT_NEGATIVE_TERMS = [
    "브이로그", "vlog", "playlist", "플레이리스트",
    "official", "공식",
]

SCARCE_SEGMENTS = {
    "원신", "젠레스존제로", "애니송커버", "블루아카이브", "붕괴스타레일",
    "명조", "명일방주", "니케", "ASMR"
}