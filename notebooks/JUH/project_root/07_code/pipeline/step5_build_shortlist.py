import pandas as pd
import numpy as np
from config import (
    CIME_SIMILARITY_SCORED_PATH,
    CIME_FINAL_SHORTLIST_PATH,
    CIME_FINAL_SHORTLIST_BY_SEGMENT_PATH,
    SHORTLIST_TOP_N,
    SIMILARITY_TOP_QUANTILE,
    VIEW_QUANTILE,
    ENGAGEMENT_QUANTILE,
)


def size_bucket(subs):
    if pd.isna(subs):
        return "미상"
    if subs < 1000:
        return "극소형"
    elif subs <= 30000:
        return "소형"
    elif subs <= 100000:
        return "중형"
    elif subs <= 300000:
        return "준대형"
    else:
        return "대형"


def run():
    print("[STEP5] shortlist 생성 시작")

    if not CIME_SIMILARITY_SCORED_PATH.exists():
        raise FileNotFoundError(f"입력 파일 없음: {CIME_SIMILARITY_SCORED_PATH}")

    df = pd.read_csv(CIME_SIMILARITY_SCORED_PATH, encoding="utf-8-sig")

    for col in ["채널구독자수", "최근영상조회수평균", "최근영상참여율평균", "씨미유사도점수", "라이브신호존재여부"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df[df["씨미유사도점수"].notna()].copy()

    if "라이브신호존재여부" in df.columns:
        df = df[df["라이브신호존재여부"] == 1].copy()

    if "채널구독자수" in df.columns:
        df["채널규모구간"] = df["채널구독자수"].apply(size_bucket)
    else:
        df["채널규모구간"] = "미상"

    sim_cut = df["씨미유사도점수"].quantile(SIMILARITY_TOP_QUANTILE) if len(df) > 0 else np.nan
    eng_cut = df["최근영상참여율평균"].quantile(ENGAGEMENT_QUANTILE) if "최근영상참여율평균" in df.columns and len(df) > 0 else np.nan
    view_cut = df["최근영상조회수평균"].quantile(VIEW_QUANTILE) if "최근영상조회수평균" in df.columns and len(df) > 0 else np.nan

    df["shortlist_1차"] = np.where(df["씨미유사도점수"] >= sim_cut, 1, 0)

    if "최근영상참여율평균" in df.columns and "최근영상조회수평균" in df.columns:
        df["shortlist_2차"] = np.where(
            (df["씨미유사도점수"] >= sim_cut) &
            (
                (df["최근영상참여율평균"] >= eng_cut) |
                (df["최근영상조회수평균"] >= view_cut)
            ),
            1, 0
        )
    else:
        df["shortlist_2차"] = df["shortlist_1차"]

    if "최근영상조회수평균" in df.columns:
        df["로그최근조회수"] = np.log1p(df["최근영상조회수평균"].fillna(0))
        max_log_view = df["로그최근조회수"].max()
    else:
        df["로그최근조회수"] = 0
        max_log_view = 0

    normalized_log_view = (df["로그최근조회수"] / max_log_view) if max_log_view and max_log_view > 0 else 0

    df["최종shortlist점수"] = (
        0.6 * df["씨미유사도점수"].fillna(0) +
        0.2 * df["최근영상참여율평균"].fillna(0) +
        0.2 * normalized_log_view
    )

    shortlist_df = df[df["shortlist_2차"] == 1].copy()
    if len(shortlist_df) < 10:
        shortlist_df = df[df["shortlist_1차"] == 1].copy()

    shortlist_df = shortlist_df.sort_values(
        ["최종shortlist점수", "씨미유사도점수"],
        ascending=[False, False]
    ).reset_index(drop=True)

    shortlist_top = shortlist_df.head(SHORTLIST_TOP_N).copy()
    shortlist_top.to_csv(CIME_FINAL_SHORTLIST_PATH, index=False, encoding="utf-8-sig")

    if "대표세그먼트" in shortlist_df.columns:
        seg_shortlist = (
            shortlist_df.sort_values(
                ["대표세그먼트", "최종shortlist점수"],
                ascending=[True, False]
            )
            .groupby("대표세그먼트", as_index=False)
            .head(5)
            .reset_index(drop=True)
        )
        seg_shortlist.to_csv(CIME_FINAL_SHORTLIST_BY_SEGMENT_PATH, index=False, encoding="utf-8-sig")
    else:
        pd.DataFrame().to_csv(CIME_FINAL_SHORTLIST_BY_SEGMENT_PATH, index=False, encoding="utf-8-sig")

    print("저장 완료:")
    print(" - shortlist      :", CIME_FINAL_SHORTLIST_PATH)
    print(" - shortlist seg  :", CIME_FINAL_SHORTLIST_BY_SEGMENT_PATH)