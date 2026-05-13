import re
import pandas as pd
import numpy as np

from config import (
    CANDIDATE_FEATURE_TABLE_PATH,
    CANDIDATE_SCORED_FINAL_PATH,
)


# =========================================================
# STEP4 - 운영형 후보 스코어링
# Hard Gate 강화 버전
#
# 목적:
# - 단순 최종점수 TOP 후보가 아닌, 실제 영입 검토 가능한 shortlist 생성
# - 대학/기관/뉴스/AI/리믹스/쇼츠/플레이리스트/상업 판매성 채널이
#   점수만으로 상위권에 올라오는 문제 방지
# - 후보를 점수화하기 전에 운영제외/검증필요 Gate를 먼저 적용
# =========================================================


# ---------------------------------------------------------
# 0. 기본 유틸
# ---------------------------------------------------------
def weighted_mean_ignore_nan(values, weights):
    vals = []
    ws = []
    for k, v in values.items():
        if pd.notna(v):
            vals.append(v)
            ws.append(weights[k])
    if not vals:
        return np.nan
    return np.average(vals, weights=ws)


def clip01(x):
    return np.clip(x, 0, 1)


def first_existing(df: pd.DataFrame, candidates):
    for c in candidates:
        if c in df.columns:
            return c
    return None


def safe_numeric(df: pd.DataFrame, cols):
    for c in cols:
        if c is not None and c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")


def normalize_text(x):
    if pd.isna(x):
        return ""
    return str(x).strip().lower()


def join_text_fields(row, cols):
    vals = []
    for c in cols:
        if c in row.index and pd.notna(row[c]):
            vals.append(str(row[c]))
    return " ".join(vals).lower()


def contains_regex(text: str, patterns) -> bool:
    text = normalize_text(text)
    for p in patterns:
        if re.search(p, text, flags=re.IGNORECASE):
            return True
    return False


def risk_score_from_patterns(text: str, patterns, score: float) -> float:
    return score if contains_regex(text, patterns) else 0.0


def pct_rank_high_is_good(series):
    """
    높은 값일수록 높은 분위 점수를 부여한다.

    pandas rank(pct=True, ascending=False)는 큰 값에 낮은 분위값을 줄 수 있으므로
    최종점수/성장성/팬밀도처럼 '높을수록 좋은 지표'는 ascending=True를 사용한다.

    예:
    - 최종점수 높은 후보 -> 0.90 이상
    - 최종점수 낮은 후보 -> 0.10 근처
    """
    s = pd.to_numeric(series, errors="coerce")
    return s.rank(method="average", pct=True, ascending=True)


def bool_from_any(x) -> bool:
    if pd.isna(x):
        return False
    if isinstance(x, bool):
        return x
    return str(x).strip().lower() in ["true", "1", "yes", "y", "t"]


# ---------------------------------------------------------
# 1. Hard Gate 키워드 룰
# ---------------------------------------------------------
# 기관/단체/공식/방송/뉴스성
ORG_PATTERNS = [
    r"대학교", r"\b대학\b", r"부산대", r"서울대", r"연세대", r"고려대", r"한양대",
    r"동아리", r"학회", r"협회", r"센터", r"연구소", r"공단", r"재단",
    r"공식", r"official", r"오피셜", r"방송국", r"방송사", r"\btv\b",
    r"\bobs\b", r"\bkbs\b", r"\bmbc\b", r"\bsbs\b", r"뉴스", r"news",
    r"신문", r"일보", r"기자", r"취재", r"press", r"media", r"network",
    r"기관", r"공공", r"정부", r"시청", r"구청", r"도청", r"교육청",
]

# AI 자동생성/뉴스성/비인격 채널
AI_NEWS_PATTERNS = [
    r"\bai\b", r"인공지능", r"자동생성", r"automated", r"generated",
    r"live ai", r"ai live", r"world news", r"global news",
    r"breaking news", r"실시간 뉴스", r"뉴스 라이브",
]

# 리믹스/쇼츠/플레이리스트/재업로드/가사/루프성
REUPLOAD_PATTERNS = [
    r"remix", r"리믹스", r"shorts", r"\bshort\b", r"쇼츠",
    r"playlist", r"플레이리스트", r"compilation", r"모음", r"모아보기",
    r"lyrics", r"가사", r"loop", r"반복재생", r"1hour", r"1 hour", r"1시간",
    r"bgm", r"브금", r"ost 모음", r"노래모음", r"mix", r"nightcore",
    r"sped up", r"slowed", r"edit audio", r"audio edit",
    r"재업", r"재업로드", r"클립 모음", r"하이라이트 모음",
]

# 팬/클립/아카이브
FAN_CLIP_ARCHIVE_PATTERNS = [
    r"팬채널", r"fan channel", r"\bfan\b", r"팬계정",
    r"클립", r"clip", r"clips", r"하이라이트", r"highlight",
    r"아카이브", r"archive", r"저장소", r"다시보기", r"replay",
]

# 상업/판매/브랜드/상품 채널
COMMERCE_PATTERNS = [
    r"스토어", r"store", r"shop", r"샵", r"mall", r"마켓",
    r"판매", r"구매", r"할인", r"세일", r"광고", r"협찬",
    r"wig", r"위그", r"가발", r"렌즈", r"의상대여", r"렌탈",
    r"브랜드", r"brand", r"official store",
]

# 외국어/해외성 강한 채널명/설명 신호
# 주의: 외국채널 판정은 반드시 채널 자체 텍스트(채널명/설명/URL)만 사용한다.
# 대표세그먼트 컬럼은 한국어 라벨이므로 외국채널 판정에 넣으면 오판이 발생한다.
GLOBAL_NON_KR_PATTERNS = [
    r"world news", r"global", r"international", r"voyages", r"travel",
    r"foreign", r"usa", r"india", r"philippines", r"indonesia",
    r"japanese", r"japan", r"english", r"thai", r"vietnam", r"russia",
    r"asmr\s*jp", r"jp\s*asmr", r"vtuber\s*jp", r"jp\s*vtuber",
    r"bilibili", r"weibo", r"douyin",
]

# 일본어/중국어/해외권 문자 및 표현 신호
# - 히라가나/가타카나는 외국채널 리스크를 강하게 본다.
# - 한자 범위는 한국어 채널명에도 일부 포함될 수 있으므로 단독 제외가 아니라 즉시검토 금지용 리스크로만 활용한다.
JP_CN_FOREIGN_PATTERNS = [
    r"[ぁ-んァ-ヶ]",            # 일본어 히라가나/가타카나
    r"[一-龥]{2,}",             # 한자 2자 이상 연속
    r"日本", r"歌ってみた", r"踊ってみた", r"弾いてみた",
    r"の館", r"ちゃんねる", r"チャンネル", r"ボイス", r"音声",
    r"中文", r"中国", r"漢語", r"汉语", r"国语", r"國語",
    r"台湾", r"臺灣", r"香港",
]

# 한국어 신호
KOREAN_CHAR_PATTERN = re.compile(r"[가-힣]")


# ---------------------------------------------------------
# 2. 리스크/게이트 계산
# ---------------------------------------------------------
def _make_channel_text_blob(row):
    """
    외국채널/한국어 신호 판정용 텍스트.
    대표상위세그먼트/대표하위세그먼트는 한국어 라벨이므로 여기에는 넣지 않는다.
    """
    text_cols = [
        "채널명",
        "채널설명",
        "채널설명_API",
        "채널커스텀URL_API",
    ]
    return join_text_fields(row, text_cols)


def _make_full_text_blob(row):
    """
    일반 리스크 판정용 텍스트.
    기관/리믹스/판매성 등은 세그먼트 라벨까지 같이 보는 것이 보조적으로 유효하다.
    """
    text_cols = [
        "채널명",
        "채널설명",
        "채널설명_API",
        "채널커스텀URL_API",
        "대표상위세그먼트",
        "대표하위세그먼트",
        "대표세그먼트",
    ]
    return join_text_fields(row, text_cols)


def _has_korean_signal(row):
    channel_text = _make_channel_text_blob(row)
    return bool(KOREAN_CHAR_PATTERN.search(channel_text))


def _calc_keyword_risks(row):
    channel_text = _make_channel_text_blob(row)
    full_text = _make_full_text_blob(row)

    org_risk = risk_score_from_patterns(full_text, ORG_PATTERNS, 1.0)
    ai_news_risk = risk_score_from_patterns(full_text, AI_NEWS_PATTERNS, 1.0)
    reupload_risk = risk_score_from_patterns(full_text, REUPLOAD_PATTERNS, 1.0)
    fan_clip_archive_risk = risk_score_from_patterns(full_text, FAN_CLIP_ARCHIVE_PATTERNS, 1.0)
    commerce_risk = risk_score_from_patterns(full_text, COMMERCE_PATTERNS, 1.0)

    global_non_kr_risk = risk_score_from_patterns(channel_text, GLOBAL_NON_KR_PATTERNS, 0.8)
    has_korean = bool(KOREAN_CHAR_PATTERN.search(channel_text))

    # 일본어/중국어/해외권 문자 신호가 있으면 외국채널 리스크 강화
    if contains_regex(channel_text, JP_CN_FOREIGN_PATTERNS):
        global_non_kr_risk = max(global_non_kr_risk, 0.85)

    # 채널 자체 텍스트에 한국어가 없으면 외국채널 가능성을 높게 본다.
    # 단, 채널 텍스트가 비어 있는 경우에는 data quality risk에서 처리한다.
    if not has_korean and len(channel_text.strip()) > 0:
        global_non_kr_risk = max(global_non_kr_risk, 0.75)

    return pd.Series({
        "기관단체리스크_gate": org_risk,
        "AI뉴스리스크_gate": ai_news_risk,
        "리믹스쇼츠재업로드리스크_gate": reupload_risk,
        "팬클립아카이브리스크_gate": fan_clip_archive_risk,
        "상업판매리스크_gate": commerce_risk,
        "외국채널리스크_gate": global_non_kr_risk,
        "한국어신호여부_gate": int(has_korean),
    })


def _calc_data_quality_risks(df):
    out = pd.DataFrame(index=df.index)

    sample_col = first_existing(df, ["수집영상수", "최근수집영상수", "성장성수집영상수_4주"])
    growth_conf_col = first_existing(df, ["성장성신뢰도"])
    upper_col = first_existing(df, ["대표상위세그먼트", "대표세그먼트"])
    lower_col = first_existing(df, ["대표하위세그먼트"])
    kr_flag_col = first_existing(df, ["한국채널추정여부"])

    if sample_col is not None:
        sample = pd.to_numeric(df[sample_col], errors="coerce")
        out["수집영상부족리스크_gate"] = np.select(
            [
                sample.isna(),
                sample < 2,
                sample < 5,
            ],
            [
                0.7,
                0.8,
                0.4,
            ],
            default=0.0,
        )
    else:
        out["수집영상부족리스크_gate"] = 0.7

    if growth_conf_col is not None:
        conf = pd.to_numeric(df[growth_conf_col], errors="coerce")
        out["성장성신뢰도부족리스크_gate"] = np.select(
            [
                conf.isna(),
                conf < 0.30,
                conf < 0.50,
            ],
            [
                0.6,
                0.7,
                0.4,
            ],
            default=0.0,
        )
    else:
        out["성장성신뢰도부족리스크_gate"] = 0.5

    if upper_col is not None:
        out["상위세그먼트불명리스크_gate"] = df[upper_col].isna().astype(float) * 0.7
    else:
        out["상위세그먼트불명리스크_gate"] = 0.7

    if lower_col is not None:
        out["하위세그먼트불명리스크_gate"] = df[lower_col].isna().astype(float) * 0.5
    else:
        out["하위세그먼트불명리스크_gate"] = 0.5

    if kr_flag_col is not None:
        kr = pd.to_numeric(df[kr_flag_col], errors="coerce")
        # 0으로 명시되어 있으면 강한 리스크, NaN이면 중간 리스크
        out["한국채널추정불가리스크_gate"] = np.select(
            [
                kr == 0,
                kr.isna(),
            ],
            [
                0.8,
                0.3,
            ],
            default=0.0,
        )
    else:
        out["한국채널추정불가리스크_gate"] = 0.2

    return out


def _make_risk_reason(row):
    reasons = []

    risk_map = [
        ("수기제외채널", "수기 제외 채널명 매칭"),
        ("기관단체리스크_gate", "기관/대학/방송사/공식 채널 의심"),
        ("AI뉴스리스크_gate", "AI/뉴스/자동생성성 채널 의심"),
        ("리믹스쇼츠재업로드리스크_gate", "리믹스/쇼츠/플레이리스트/재업로드성 채널 의심"),
        ("팬클립아카이브리스크_gate", "팬/클립/아카이브 채널 의심"),
        ("상업판매리스크_gate", "상업/판매/브랜드 채널 의심"),
        ("외국채널리스크_gate", "한국 타깃 적합성 낮음"),
        ("한국채널추정불가리스크_gate", "한국채널 추정 근거 부족"),
        ("상위세그먼트불명리스크_gate", "상위 세그먼트 불명확"),
        ("하위세그먼트불명리스크_gate", "하위 세그먼트 불명확"),
        ("수집영상부족리스크_gate", "수집 영상 수 부족"),
        ("성장성신뢰도부족리스크_gate", "성장성 신뢰도 낮음"),
    ]

    for col, msg in risk_map:
        val = row.get(col, 0)
        if pd.notna(val) and float(val) >= 0.5:
            reasons.append(msg)

    return " / ".join(reasons) if reasons else "주요 자동 리스크 낮음"


def _make_recommend_reason(row):
    reasons = []

    if row.get("최종점수분위", 0) >= 0.90:
        reasons.append("최종점수 상위 10%")
    elif row.get("최종점수분위", 0) >= 0.80:
        reasons.append("최종점수 상위 20%")

    if row.get("성장성점수분위", 0) >= 0.80:
        reasons.append("성장성 상위권")
    if row.get("팬밀도점수분위", 0) >= 0.80:
        reasons.append("팬밀도 상위권")
    if row.get("라이브친화점수분위", 0) >= 0.80:
        reasons.append("라이브친화도 상위권")
    if row.get("실전성점수분위", 0) >= 0.80:
        reasons.append("실전성 리스크 낮음")

    if row.get("성장성신뢰도", np.nan) is not np.nan:
        conf = row.get("성장성신뢰도")
        if pd.notna(conf) and conf >= 0.70:
            reasons.append("성장성 신뢰도 양호")

    if not reasons:
        return "뚜렷한 강점 신호 부족"

    return " / ".join(reasons)


def _make_auto_basis(row):
    return (
        f"최종={row.get('최종점수', np.nan):.3f}, "
        f"채널력={row.get('채널력점수', np.nan):.3f}, "
        f"성장성={row.get('성장성점수', np.nan):.3f}, "
        f"팬밀도={row.get('팬밀도점수', np.nan):.3f}, "
        f"라이브={row.get('라이브친화점수', np.nan):.3f}, "
        f"실전성={row.get('실전성점수', np.nan):.3f}, "
        f"운영제외리스크={row.get('운영제외리스크', np.nan):.3f}, "
        f"검증필요리스크={row.get('검증필요리스크', np.nan):.3f}, "
        f"수기제외={row.get('수기제외채널', 0)}"
    )


def _assign_action_bucket(row):
    score_pct = row.get("최종점수분위", np.nan)
    growth_pct = row.get("성장성점수분위", np.nan)
    fan_pct = row.get("팬밀도점수분위", np.nan)
    live_pct = row.get("라이브친화점수분위", np.nan)

    exec_score = row.get("실전성점수", np.nan)
    exclude_risk = row.get("운영제외리스크", 0)
    review_risk = row.get("검증필요리스크", 0)
    foreign_risk = row.get("외국채널리스크_gate", 0)

    growth_conf = row.get("성장성신뢰도", np.nan)
    growth_conf_low = pd.isna(growth_conf) or growth_conf < 0.40
    growth_conf_ok = pd.notna(growth_conf) and growth_conf >= 0.40

    # -----------------------------------------------------
    # Manual Hard Gate
    # - 수기 제외 채널은 점수와 관계없이 제외
    # -----------------------------------------------------
    manual_exclude = row.get("수기제외채널", 0)
    try:
        manual_exclude = float(manual_exclude)
    except Exception:
        manual_exclude = 1.0 if bool_from_any(manual_exclude) else 0.0

    if manual_exclude >= 1:
        return "제외"

    if pd.isna(score_pct):
        return "미분류"

    # Hard Gate: 외국채널 가능성이 높으면 즉시검토 금지
    # 점수/성장/팬밀도 신호가 매우 강하면 검증필요로 남기고, 아니면 제외한다.
    if pd.notna(foreign_risk) and foreign_risk >= 0.70:
        if score_pct >= 0.85 or growth_pct >= 0.85 or fan_pct >= 0.85 or live_pct >= 0.85:
            return "검증필요"
        return "제외"

    # Hard Gate: 실전 영입 대상이 아닐 가능성이 큰 후보는 점수와 상관없이 제외
    if pd.notna(exclude_risk) and exclude_risk >= 0.70:
        return "제외"

    # 실전성 자체가 낮으면 제외
    if pd.notna(exec_score) and exec_score < 0.50:
        return "제외"

    # 성장성 신뢰도가 낮은 후보는 '즉시검토' 금지.
    # 단, 최종점수/성장성/팬밀도/라이브친화 중 강점이 있으면 관찰 또는 검증 대상으로 남긴다.
    if growth_conf_low:
        if pd.notna(review_risk) and review_risk >= 0.60:
            if score_pct >= 0.80 or growth_pct >= 0.85 or fan_pct >= 0.85 or live_pct >= 0.85:
                return "검증필요"
            return "보류"

        if score_pct >= 0.80 or growth_pct >= 0.80 or fan_pct >= 0.85 or live_pct >= 0.85:
            return "성장관찰"

        return "보류"

    # 데이터/분류/신뢰도 리스크가 높으면 즉시검토 금지
    if pd.notna(review_risk) and review_risk >= 0.60:
        if score_pct >= 0.80 or growth_pct >= 0.85 or fan_pct >= 0.85 or live_pct >= 0.85:
            return "검증필요"
        return "보류"

    # 즉시검토: 리스크 통과 + 성장성 신뢰도 보통 이상 + 종합 상위권
    # 성장성/팬밀도/라이브 중 하나 이상의 강점이 있어야 함
    if (
        score_pct >= 0.90
        and growth_conf_ok
        and pd.notna(exec_score)
        and exec_score >= 0.70
        and max(
            growth_pct if pd.notna(growth_pct) else 0,
            fan_pct if pd.notna(fan_pct) else 0,
            live_pct if pd.notna(live_pct) else 0,
        ) >= 0.70
    ):
        return "즉시검토"

    # 성장관찰: 종합점수보다 성장성 신호가 우수한 후보
    if growth_pct >= 0.85 and score_pct >= 0.60:
        return "성장관찰"

    # 검증필요: 점수는 괜찮지만 강점/리스크 확인 필요
    if score_pct >= 0.75:
        return "검증필요"

    return "보류"

def _assign_shortlist_type(row):
    bucket = row.get("액션버킷")

    if bucket == "즉시검토":
        return "즉시검토형"

    if bucket == "성장관찰":
        return "성장관찰형"

    if bucket == "검증필요":
        if row.get("운영제외리스크", 0) >= 0.50:
            return "리스크검증형"
        if row.get("검증필요리스크", 0) >= 0.50:
            return "데이터검증형"
        return "점수상위검증형"

    return pd.NA


def _calc_operation_priority(df):
    """
    shortlist 후보를 먼저, 그 안에서는 액션버킷과 최종점수 기준으로 운영 우선순위 부여.
    """
    bucket_order = {
        "즉시검토": 1,
        "성장관찰": 2,
        "검증필요": 3,
        "보류": 4,
        "제외": 5,
        "미분류": 6,
    }

    df["__bucket_order__"] = df["액션버킷"].map(bucket_order).fillna(6)

    df = df.sort_values(
        ["__bucket_order__", "최종점수", "성장성점수", "팬밀도점수"],
        ascending=[True, False, False, False],
        na_position="last",
    ).reset_index(drop=True)

    df["운영우선순위"] = np.arange(1, len(df) + 1)
    df = df.drop(columns=["__bucket_order__"], errors="ignore")

    return df


# ---------------------------------------------------------
# 3. 메인 실행
# ---------------------------------------------------------
def run():
    print("[STEP4] candidate scoring 시작 - Hard Gate 강화 버전")

    if not CANDIDATE_FEATURE_TABLE_PATH.exists():
        raise FileNotFoundError(f"입력 파일 없음: {CANDIDATE_FEATURE_TABLE_PATH}")

    df = pd.read_csv(CANDIDATE_FEATURE_TABLE_PATH, encoding="utf-8-sig")
    print("입력 rows:", len(df))

    # -----------------------------------------------------
    # 0. 숫자형 보정
    # -----------------------------------------------------
    numeric_cols = [
        "채널력_조회수pct", "채널력_활동성pct", "채널력_구독자pct",
        "성장성점수_proxy", "성장성신뢰도",
        "성장성_조회수pct_recalc", "성장성_참여율pct_recalc",
        "성장성_업로드pct_recalc", "성장성_라이브pct_recalc",
        "팬밀도_기본참여율pct",
        "라이브친화_기본pct", "라이브친화_성장변화pct",
        "팬채널리스크", "클립채널리스크", "기관채널리스크",
        "아카이브리스크", "실전성_대형채널패널티",
        "수기제외채널",
        "한국채널추정여부",
        "수집영상수", "최근수집영상수", "성장성수집영상수_4주",
        "채널구독자수", "최근영상조회수평균", "최근영상참여율평균",
    ]
    safe_numeric(df, numeric_cols)

    # 원본 risk 컬럼이 없으면 0으로 보정
    for c in [
        "팬채널리스크",
        "클립채널리스크",
        "기관채널리스크",
        "아카이브리스크",
        "실전성_대형채널패널티",
        "수기제외채널",
    ]:
        if c not in df.columns:
            df[c] = 0.0
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)

    # -----------------------------------------------------
    # 1. 채널력점수
    # -----------------------------------------------------
    df["채널력점수"] = df.apply(
        lambda row: weighted_mean_ignore_nan(
            {
                "조회수": row["채널력_조회수pct"] if "채널력_조회수pct" in df.columns else np.nan,
                "활동성": row["채널력_활동성pct"] if "채널력_활동성pct" in df.columns else np.nan,
                "구독자": row["채널력_구독자pct"] if "채널력_구독자pct" in df.columns else np.nan,
            },
            {
                "조회수": 0.45,
                "활동성": 0.35,
                "구독자": 0.20,
            }
        ),
        axis=1
    )

    # -----------------------------------------------------
    # 2. 성장성점수
    # - raw proxy 우선
    # - 없으면 재계산 percentile fallback
    # - 성장성신뢰도로 보정
    # -----------------------------------------------------
    if "성장성점수_proxy" in df.columns:
        df["성장성점수_raw"] = pd.to_numeric(df["성장성점수_proxy"], errors="coerce")
    else:
        df["성장성점수_raw"] = np.nan

    fallback_mask = df["성장성점수_raw"].isna()

    if fallback_mask.any():
        df.loc[fallback_mask, "성장성점수_raw"] = df.loc[fallback_mask].apply(
            lambda row: weighted_mean_ignore_nan(
                {
                    "조회수": row["성장성_조회수pct_recalc"] if "성장성_조회수pct_recalc" in df.columns else np.nan,
                    "참여율": row["성장성_참여율pct_recalc"] if "성장성_참여율pct_recalc" in df.columns else np.nan,
                    "업로드": row["성장성_업로드pct_recalc"] if "성장성_업로드pct_recalc" in df.columns else np.nan,
                    "라이브": row["성장성_라이브pct_recalc"] if "성장성_라이브pct_recalc" in df.columns else np.nan,
                },
                {
                    "조회수": 0.35,
                    "참여율": 0.30,
                    "업로드": 0.20,
                    "라이브": 0.15,
                }
            ),
            axis=1
        )

    df["성장성점수_raw"] = df["성장성점수_raw"].fillna(0.5)

    if "성장성신뢰도" in df.columns:
        conf = pd.to_numeric(df["성장성신뢰도"], errors="coerce").clip(0, 1).fillna(0.35)
    else:
        conf = pd.Series(0.35, index=df.index)

    df["성장성점수"] = df["성장성점수_raw"] * conf + 0.5 * (1 - conf)

    # -----------------------------------------------------
    # 3. 팬밀도점수
    # -----------------------------------------------------
    if "팬밀도_기본참여율pct" in df.columns:
        df["팬밀도점수"] = pd.to_numeric(df["팬밀도_기본참여율pct"], errors="coerce")
    else:
        df["팬밀도점수"] = np.nan
    df["팬밀도점수"] = df["팬밀도점수"].fillna(0.5)

    # -----------------------------------------------------
    # 4. 라이브친화점수
    # -----------------------------------------------------
    df["라이브친화점수"] = df.apply(
        lambda row: weighted_mean_ignore_nan(
            {
                "기본": row["라이브친화_기본pct"] if "라이브친화_기본pct" in df.columns else np.nan,
                "변화": row["라이브친화_성장변화pct"] if "라이브친화_성장변화pct" in df.columns else np.nan,
            },
            {
                "기본": 0.75,
                "변화": 0.25,
            }
        ),
        axis=1
    )
    df["라이브친화점수"] = df["라이브친화점수"].fillna(0.5)

    # -----------------------------------------------------
    # 5. Hard Gate 리스크 계산
    # -----------------------------------------------------
    keyword_risks = df.apply(_calc_keyword_risks, axis=1)
    data_quality_risks = _calc_data_quality_risks(df)

    df = pd.concat([df, keyword_risks, data_quality_risks], axis=1)

    # 기존 feature 리스크와 신규 gate 리스크를 통합
    df["운영제외리스크"] = clip01(
        1.00 * df["수기제외채널"].fillna(0)
        + 0.22 * df["기관단체리스크_gate"].fillna(0)
        + 0.20 * df["AI뉴스리스크_gate"].fillna(0)
        + 0.22 * df["리믹스쇼츠재업로드리스크_gate"].fillna(0)
        + 0.14 * df["팬클립아카이브리스크_gate"].fillna(0)
        + 0.12 * df["상업판매리스크_gate"].fillna(0)
        + 0.16 * df["외국채널리스크_gate"].fillna(0)
        + 0.10 * df["기관채널리스크"].fillna(0)
        + 0.08 * df["클립채널리스크"].fillna(0)
        + 0.08 * df["아카이브리스크"].fillna(0)
    )

    df["검증필요리스크"] = clip01(
        0.28 * df["수집영상부족리스크_gate"].fillna(0)
        + 0.28 * df["성장성신뢰도부족리스크_gate"].fillna(0)
        + 0.18 * df["한국채널추정불가리스크_gate"].fillna(0)
        + 0.13 * df["상위세그먼트불명리스크_gate"].fillna(0)
        + 0.08 * df["하위세그먼트불명리스크_gate"].fillna(0)
        + 0.12 * df["외국채널리스크_gate"].fillna(0)
    )

    # -----------------------------------------------------
    # 6. 실전성점수
    # - 기존 리스크 + Hard Gate 리스크 반영
    # -----------------------------------------------------
    df["실전성_리스크합"] = clip01(
        1.00 * df["수기제외채널"].fillna(0)
        + 0.20 * df["팬채널리스크"].fillna(0)
        + 0.18 * df["클립채널리스크"].fillna(0)
        + 0.16 * df["기관채널리스크"].fillna(0)
        + 0.08 * df["아카이브리스크"].fillna(0)
        + 0.10 * df["실전성_대형채널패널티"].fillna(0)
        + 0.20 * df["운영제외리스크"].fillna(0)
        + 0.08 * df["검증필요리스크"].fillna(0)
    )
    df["실전성점수"] = clip01(1 - df["실전성_리스크합"])

    # -----------------------------------------------------
    # 7. 최종점수
    # - 최종점수 자체에도 리스크를 약하게 반영
    # - 단, Hard Gate는 액션버킷에서 더 강하게 적용
    # -----------------------------------------------------
    df["최종점수_raw"] = df.apply(
        lambda row: weighted_mean_ignore_nan(
            {
                "채널력": row["채널력점수"],
                "성장성": row["성장성점수"],
                "팬밀도": row["팬밀도점수"],
                "라이브친화": row["라이브친화점수"],
                "실전성": row["실전성점수"],
            },
            {
                "채널력": 0.22,
                "성장성": 0.28,
                "팬밀도": 0.22,
                "라이브친화": 0.15,
                "실전성": 0.13,
            }
        ),
        axis=1
    )

    df["최종점수"] = clip01(
        df["최종점수_raw"]
        - 1.00 * df["수기제외채널"].fillna(0)
        - 0.18 * df["운영제외리스크"].fillna(0)
        - 0.08 * df["검증필요리스크"].fillna(0)
    )

    # -----------------------------------------------------
    # 8. 분위수 계산
    # -----------------------------------------------------
    score_cols = [
        "최종점수",
        "채널력점수",
        "성장성점수",
        "팬밀도점수",
        "라이브친화점수",
        "실전성점수",
    ]

    for c in score_cols:
        df[f"{c}분위"] = pct_rank_high_is_good(df[c])

    # -----------------------------------------------------
    # 9. 액션버킷 / shortlist / 근거 생성
    # -----------------------------------------------------
    df["액션버킷"] = df.apply(_assign_action_bucket, axis=1)

    df["shortlist_선정여부"] = df["액션버킷"].isin(["즉시검토", "성장관찰", "검증필요"])
    df["shortlist_유형"] = df.apply(_assign_shortlist_type, axis=1)

    df["주의사유"] = df.apply(_make_risk_reason, axis=1)
    df["추천사유"] = df.apply(_make_recommend_reason, axis=1)
    df["자동판정근거"] = df.apply(_make_auto_basis, axis=1)

    # -----------------------------------------------------
    # 10. 최종순위 / 운영우선순위
    # -----------------------------------------------------
    df = df.sort_values("최종점수", ascending=False).reset_index(drop=True)
    df["최종순위"] = np.arange(1, len(df) + 1)

    df = _calc_operation_priority(df)

    # 다시 최종순위는 최종점수 기준으로 유지
    df = df.sort_values("최종점수", ascending=False).reset_index(drop=True)
    df["최종순위"] = np.arange(1, len(df) + 1)

    # 운영우선순위는 이미 계산된 값 유지

    # -----------------------------------------------------
    # 11. 저장
    # -----------------------------------------------------
    df.to_csv(CANDIDATE_SCORED_FINAL_PATH, index=False, encoding="utf-8-sig")

    print("saved:", CANDIDATE_SCORED_FINAL_PATH)
    print("[최종점수 요약]")
    print(df["최종점수"].describe())

    print("\n[액션버킷 분포]")
    print(df["액션버킷"].value_counts(dropna=False))

    print("\n[운영제외리스크 요약]")
    print(df["운영제외리스크"].describe())

    print("\n[검증필요리스크 요약]")
    print(df["검증필요리스크"].describe())

    risk_cols = [
        "수기제외채널",
        "기관단체리스크_gate",
        "AI뉴스리스크_gate",
        "리믹스쇼츠재업로드리스크_gate",
        "팬클립아카이브리스크_gate",
        "상업판매리스크_gate",
        "외국채널리스크_gate",
        "수집영상부족리스크_gate",
        "성장성신뢰도부족리스크_gate",
    ]
    print("\n[주요 리스크 감지 건수]")
    for c in risk_cols:
        if c in df.columns:
            print(c, ":", int((pd.to_numeric(df[c], errors="coerce").fillna(0) >= 0.5).sum()))

    print("[STEP4] candidate scoring 완료 - Hard Gate 강화 버전")


if __name__ == "__main__":
    run()
