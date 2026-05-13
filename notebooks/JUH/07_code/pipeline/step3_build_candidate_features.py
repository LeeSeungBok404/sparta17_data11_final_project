import re
import pandas as pd
import numpy as np

from config import (
    CANDIDATE_PREPARED_PATH,
    CANDIDATE_GROWTH_PROXY_PATH,
    CANDIDATE_FEATURE_TABLE_PATH,
)


def first_existing(df, candidates):
    for c in candidates:
        if c in df.columns:
            return c
    return None


def pct_rank_high_is_good(series):
    """
    값이 클수록 좋은 지표를 0~1 분위 점수로 변환한다.

    주의:
    pandas rank(pct=True, ascending=False)는 큰 값일수록 낮은 pct를 부여한다.
    후보 스코어링에서는 조회수/구독자수/참여율/성장률처럼 큰 값이 좋은 지표가
    높은 점수를 받아야 하므로 ascending=True를 사용한다.

    예: 후보가 100개일 때 가장 큰 값은 1.00에 가까운 점수,
        가장 작은 값은 0.01에 가까운 점수를 받는다.
    """
    s = pd.to_numeric(series, errors="coerce")
    return s.rank(method="average", pct=True, ascending=True)


def pct_rank_desc(series):
    """
    기존 함수명 호환용 alias.
    실제 동작은 '높을수록 좋은 점수' 기준이다.
    """
    return pct_rank_high_is_good(series)


def normalize_text(x):
    if pd.isna(x):
        return ""
    return str(x).strip().lower()


def contains_any(text, keywords):
    text = normalize_text(text)
    return any(k.lower() in text for k in keywords)


def matched_keywords(text, keywords):
    """
    text 안에 포함된 키워드를 리스트로 반환한다.
    수기 제외 사유 기록용으로 사용한다.
    """
    text = normalize_text(text)
    return [k for k in keywords if k.lower() in text]


def safe_numeric(df, cols):
    for c in cols:
        if c is not None and c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")



def print_rank_sanity_check(df, value_col, score_col, label):
    """
    분위 점수 방향성 점검용 로그.
    value_col 값이 큰 행의 score_col도 높아야 정상이다.
    """
    if value_col is None or score_col not in df.columns or value_col not in df.columns:
        return

    tmp = df[[value_col, score_col]].copy()
    tmp[value_col] = pd.to_numeric(tmp[value_col], errors="coerce")
    tmp[score_col] = pd.to_numeric(tmp[score_col], errors="coerce")
    tmp = tmp.dropna()

    if tmp.empty:
        return

    high_row = tmp.sort_values(value_col, ascending=False).head(1).iloc[0]
    low_row = tmp.sort_values(value_col, ascending=True).head(1).iloc[0]

    print(
        f"[rank sanity] {label} | "
        f"max_value={high_row[value_col]:,.3f}, max_score={high_row[score_col]:.4f} | "
        f"min_value={low_row[value_col]:,.3f}, min_score={low_row[score_col]:.4f}"
    )


def run():
    print("[STEP3] candidate feature 생성 시작")

    if not CANDIDATE_PREPARED_PATH.exists():
        raise FileNotFoundError(f"prepared 입력 파일 없음: {CANDIDATE_PREPARED_PATH}")
    if not CANDIDATE_GROWTH_PROXY_PATH.exists():
        raise FileNotFoundError(f"growth proxy 입력 파일 없음: {CANDIDATE_GROWTH_PROXY_PATH}")

    df_prepared = pd.read_csv(CANDIDATE_PREPARED_PATH, encoding="utf-8-sig")
    df_growth = pd.read_csv(CANDIDATE_GROWTH_PROXY_PATH, encoding="utf-8-sig")

    print("prepared rows:", len(df_prepared))
    print("growth proxy rows:", len(df_growth))

    # -----------------------------------------------------
    # 1. key 컬럼 확인
    # -----------------------------------------------------
    prepared_key = first_existing(df_prepared, ["채널ID"])
    growth_key = first_existing(df_growth, ["채널ID"])

    if prepared_key is None:
        raise ValueError("prepared 파일에서 '채널ID' 컬럼을 찾지 못했습니다.")
    if growth_key is None:
        raise ValueError("growth proxy 파일에서 '채널ID' 컬럼을 찾지 못했습니다.")

    df_prepared[prepared_key] = df_prepared[prepared_key].astype(str).str.strip()
    df_growth[growth_key] = df_growth[growth_key].astype(str).str.strip()

    # -----------------------------------------------------
    # 2. growth proxy 쪽 필요한 컬럼만 선택
    # -----------------------------------------------------
    growth_keep_cols = [
        growth_key,
        "최근2주_업로드수",
        "이전2주_업로드수",
        "최근2주_평균조회수",
        "이전2주_평균조회수",
        "최근2주_평균참여율",
        "이전2주_평균참여율",
        "최근2주_라이브비율",
        "이전2주_라이브비율",
        "최근2주_조회수성장률",
        "최근2주_참여율성장률",
        "최근2주_업로드성장률",
        "최근2주_라이브비율차이",
        "성장성_조회수pct",
        "성장성_참여율pct",
        "성장성_업로드pct",
        "성장성_라이브pct",
        "성장성점수_proxy_raw",
        "성장성수집영상수_4주",
        "성장성신뢰도",
        "성장성신뢰도등급",
        "성장성점수_proxy",
    ]
    growth_keep_cols = [c for c in growth_keep_cols if c in df_growth.columns]

    df_growth_small = df_growth[growth_keep_cols].copy()
    df_growth_small = df_growth_small.drop_duplicates(subset=[growth_key], keep="last")

    # -----------------------------------------------------
    # 3. merge
    # -----------------------------------------------------
    if prepared_key != growth_key:
        df_growth_small = df_growth_small.rename(columns={growth_key: prepared_key})

    df = df_prepared.merge(df_growth_small, on=prepared_key, how="left")
    print("merge 후 rows:", len(df))

    # -----------------------------------------------------
    # 4. 기본 컬럼 탐색
    # -----------------------------------------------------
    channel_id_col = first_existing(df, ["채널ID"])
    channel_name_col = first_existing(df, ["채널명"])
    upper_col = first_existing(df, ["대표상위세그먼트"])
    lower_col = first_existing(df, ["대표하위세그먼트"])

    subs_col = first_existing(df, ["채널구독자수", "구독자수"])
    kr_flag_col = first_existing(df, ["한국채널추정여부"])

    view_col = first_existing(df, ["최근영상조회수평균", "최근평균조회수"])
    eng_col = first_existing(df, ["최근영상참여율평균", "최근평균참여율"])
    live_col = first_existing(df, ["최근영상실제라이브시작비율", "최근라이브비율"])

    # 활동성은 prepared 쪽 수집영상수 우선, 없으면 성장성수집영상수_4주 보조 사용
    activity_col = first_existing(df, ["수집영상수", "최근수집영상수", "성장성수집영상수_4주"])

    # growth proxy 기준 컬럼
    growth_score_col = first_existing(df, ["성장성점수_proxy"])
    growth_conf_col = first_existing(df, ["성장성신뢰도"])
    growth_conf_grade_col = first_existing(df, ["성장성신뢰도등급"])

    g_view_col = first_existing(df, ["최근2주_조회수성장률"])
    g_eng_col = first_existing(df, ["최근2주_참여율성장률"])
    g_upload_col = first_existing(df, ["최근2주_업로드성장률"])
    g_live_col = first_existing(df, ["최근2주_라이브비율차이"])

    desc_col = first_existing(df, ["채널설명", "채널설명_API"])
    custom_url_col = first_existing(df, ["채널커스텀URL_API"])

    safe_numeric(df, [
        subs_col, kr_flag_col,
        view_col, eng_col, live_col, activity_col,
        growth_score_col, growth_conf_col,
        g_view_col, g_eng_col, g_upload_col, g_live_col,
    ])

    # -----------------------------------------------------
    # 5. 텍스트 결합
    # -----------------------------------------------------
    text_cols = [c for c in [channel_name_col, desc_col, upper_col, lower_col, custom_url_col] if c is not None]
    df["__text__"] = ""
    for c in text_cols:
        df["__text__"] = df["__text__"] + " " + df[c].fillna("").astype(str).str.lower()

    invest_keywords = [
        "주식", "재테크", "투자", "코인", "비트코인", "경제", "시황", "종목", "증권",
        "etf", "nasdaq", "bitcoin", "crypto", "finance", "stock", "invest", "trading",
        "부동산", "세금", "연금", "채권", "금리",
    ]
    info_keywords = [
        "뉴스", "시사", "브리핑", "해설", "강의", "학원", "공부", "수업", "lecture",
        "역사", "과학", "법률", "세무", "의학", "병원", "신문", "리포트","마켓","종교","예수님","부처님"
    ]
    org_keywords = [
        "official", "공식", "tv", "뉴스", "신문", "연구소", "센터", "협회", "기관",
        "academy", "school", "clinic", "lab", "corp", "company", "아카데미",
    ]
    fan_keywords = ["fan", "팬계정", "응원계정", "덕질", "archive fan"]
    clip_keywords = ["클립", "clip", "하이라이트", "shorts clip", "모음집", "편집본"]
    archive_keywords = ["archive", "아카이브", "저장소", "백업"]

    # -----------------------------------------------------
    # 수기 제외 채널 키워드
    # - 특정 채널명을 직접 제외하고 싶을 때 이 리스트에 추가한다.
    # - 채널명/설명/세그먼트/커스텀URL을 합친 __text__ 기준으로 탐지한다.
    # -----------------------------------------------------
    manual_exclude_channel_keywords = [
        "6시 내고향",
        "여섯시 내고향",
        "kbs 6시 내고향",
        "경제적자유민족",
        "경제적 자유민족",

        # 추가 수기 제외 채널
        "하바로셀",
        "프나가나라다",
        "코코잡덕집사",
        "주디타임 Judy Time",
        "하냥",
        "유이 yui",
        "로플릭스",
        "플사모:플덕플덕 plave fangirl",
        "선순환시대 인문학 힐링타운 방송",
        "리덕자 Duckja",
        "앤셔리빈티지",
        "현서라이브",
        "딸기마켓픽DAY",
        "Awesome World 어썸월드",
        "주이녹은 이렇게 털었다.",
        "순진한 콩순이",
        "최고다버린이",
        "정새로나🍒토닥토닥🍒예수님이 좋다",
        "원신감성 Genshin Feeling",
        "영웅강토",
        "박봉팔 Sue2",
        "엔써입니닷",
        "키득가득",
        "소유타로",
        "급식왕",
        "종목상담 MTNW투자자문",
        "묘진",
        "아오쿠모 린 AOKUMO RIN",
    ]

    df["자동제외_투자형"] = df["__text__"].apply(lambda x: contains_any(x, invest_keywords))
    df["자동제외_정보형"] = df["__text__"].apply(lambda x: contains_any(x, info_keywords))
    df["기관채널리스크"] = df["__text__"].apply(lambda x: int(contains_any(x, org_keywords)))
    df["팬채널리스크"] = df["__text__"].apply(lambda x: int(contains_any(x, fan_keywords)))
    df["클립채널리스크"] = df["__text__"].apply(lambda x: int(contains_any(x, clip_keywords)))
    df["아카이브리스크"] = df["__text__"].apply(lambda x: int(contains_any(x, archive_keywords)))

    # 수기 제외 플래그 및 사유
    df["수기제외매칭키워드"] = df["__text__"].apply(
        lambda x: ", ".join(matched_keywords(x, manual_exclude_channel_keywords))
    )
    df["수기제외채널"] = (
        df["수기제외매칭키워드"].fillna("").astype(str).str.len() > 0
    ).astype(int)
    df["수기제외사유"] = np.where(
        df["수기제외채널"] == 1,
        "수기 제외 채널명 매칭: " + df["수기제외매칭키워드"].fillna("").astype(str),
        pd.NA,
    )

    # -----------------------------------------------------
    # 6. 채널력 관련 pct
    # -----------------------------------------------------
    if view_col is not None:
        df["채널력_조회수pct"] = pct_rank_desc(df[view_col])
    else:
        df["채널력_조회수pct"] = np.nan

    if activity_col is not None:
        df["채널력_활동성pct"] = pct_rank_desc(df[activity_col])
    else:
        df["채널력_활동성pct"] = np.nan

    if subs_col is not None:
        df["채널력_구독자pct"] = pct_rank_desc(df[subs_col])
    else:
        df["채널력_구독자pct"] = np.nan

    # -----------------------------------------------------
    # 7. 성장성 fallback용 재계산 pct
    # -----------------------------------------------------
    if g_view_col is not None:
        df["성장성_조회수pct_recalc"] = pct_rank_desc(df[g_view_col])
    else:
        df["성장성_조회수pct_recalc"] = np.nan

    if g_eng_col is not None:
        df["성장성_참여율pct_recalc"] = pct_rank_desc(df[g_eng_col])
    else:
        df["성장성_참여율pct_recalc"] = np.nan

    if g_upload_col is not None:
        df["성장성_업로드pct_recalc"] = pct_rank_desc(df[g_upload_col])
    else:
        df["성장성_업로드pct_recalc"] = np.nan

    if g_live_col is not None:
        df["성장성_라이브pct_recalc"] = pct_rank_desc(df[g_live_col])
    else:
        df["성장성_라이브pct_recalc"] = np.nan

    # -----------------------------------------------------
    # 8. 팬밀도 / 라이브친화
    # -----------------------------------------------------
    if eng_col is not None:
        df["팬밀도_기본참여율pct"] = pct_rank_desc(df[eng_col])
    else:
        df["팬밀도_기본참여율pct"] = np.nan

    if live_col is not None:
        df["라이브친화_기본pct"] = pct_rank_desc(df[live_col])
    else:
        df["라이브친화_기본pct"] = np.nan

    if g_live_col is not None:
        df["라이브친화_성장변화pct"] = pct_rank_desc(df[g_live_col])
    else:
        df["라이브친화_성장변화pct"] = np.nan

    # -----------------------------------------------------
    # 9. 대형채널 패널티
    # -----------------------------------------------------
    if subs_col is not None:
        df["실전성_대형채널패널티"] = np.where(
            pd.to_numeric(df[subs_col], errors="coerce").fillna(0) >= 300000,
            1,
            0
        )
    else:
        df["실전성_대형채널패널티"] = 0

    # -----------------------------------------------------
    # 9-1. 분위 점수 방향성 sanity check
    # -----------------------------------------------------
    print_rank_sanity_check(df, view_col, "채널력_조회수pct", "조회수")
    print_rank_sanity_check(df, activity_col, "채널력_활동성pct", "활동성")
    print_rank_sanity_check(df, subs_col, "채널력_구독자pct", "구독자")
    print_rank_sanity_check(df, eng_col, "팬밀도_기본참여율pct", "참여율")

    # -----------------------------------------------------
    # 10. 기본 정리
    # -----------------------------------------------------
    if growth_conf_grade_col is None:
        df["성장성신뢰도등급"] = pd.NA

    if growth_score_col is None:
        df["성장성점수_proxy"] = np.nan

    output_order_front = [
        c for c in [
            channel_id_col,
            channel_name_col,
            upper_col,
            lower_col,
            subs_col,
            view_col,
            eng_col,
            live_col,
            activity_col,
            "성장성점수_proxy",
            "성장성신뢰도",
            "성장성신뢰도등급",
            "채널력_조회수pct",
            "채널력_활동성pct",
            "채널력_구독자pct",
            "성장성_조회수pct_recalc",
            "성장성_참여율pct_recalc",
            "성장성_업로드pct_recalc",
            "성장성_라이브pct_recalc",
            "팬밀도_기본참여율pct",
            "라이브친화_기본pct",
            "라이브친화_성장변화pct",
            "팬채널리스크",
            "클립채널리스크",
            "기관채널리스크",
            "아카이브리스크",
            "실전성_대형채널패널티",
            "자동제외_투자형",
            "자동제외_정보형",
            "수기제외채널",
            "수기제외매칭키워드",
            "수기제외사유",
        ] if c is not None and c in df.columns
    ]

    rest_cols = [c for c in df.columns if c not in output_order_front]
    df = df[output_order_front + rest_cols].copy()

    df.to_csv(CANDIDATE_FEATURE_TABLE_PATH, index=False, encoding="utf-8-sig")
    print("saved:", CANDIDATE_FEATURE_TABLE_PATH)
    print("[STEP3] candidate feature 생성 완료")


if __name__ == "__main__":
    run()