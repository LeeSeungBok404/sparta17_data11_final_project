import pandas as pd
import numpy as np
from config import (
    CIME_REFERENCE_PROFILE_FILTERED_PATH,
    FINAL_CORE_CANDIDATE_DIR,
    CIME_SIMILARITY_SCORED_PATH,
    CIME_SIMILARITY_SEGMENT_SUMMARY_PATH,
)

PREPARED_CANDIDATE_PATH = FINAL_CORE_CANDIDATE_DIR / "candidate_channel_prepared.csv"


def similarity_from_reference(x, median, q1, q3, iqr):
    if pd.isna(x) or pd.isna(median):
        return np.nan

    if pd.isna(iqr) or iqr == 0:
        denom = abs(median) if abs(median) > 1e-9 else 1.0
        rel_gap = abs(x - median) / denom
        return max(0.0, 1.0 - rel_gap)

    if q1 <= x <= q3:
        return 1.0

    gap = abs(x - median)
    return max(0.0, 1.0 - gap / (2.5 * iqr))


def weighted_mean_ignore_nan(row, cols, weights):
    vals = []
    ws = []
    for c, w in zip(cols, weights):
        v = row[c]
        if pd.notna(v):
            vals.append(v)
            ws.append(w)
    if len(vals) == 0:
        return np.nan
    return np.average(vals, weights=ws)


def run():
    print("[STEP4] CME 유사도 계산 시작")

    if not CIME_REFERENCE_PROFILE_FILTERED_PATH.exists():
        raise FileNotFoundError(f"레퍼런스 파일 없음: {CIME_REFERENCE_PROFILE_FILTERED_PATH}")
    if not PREPARED_CANDIDATE_PATH.exists():
        raise FileNotFoundError(f"후보 파일 없음: {PREPARED_CANDIDATE_PATH}")

    ref_df = pd.read_csv(CIME_REFERENCE_PROFILE_FILTERED_PATH, encoding="utf-8-sig")
    cand_df = pd.read_csv(PREPARED_CANDIDATE_PATH, encoding="utf-8-sig")

    # 숫자형 보정
    ref_compare_map = {
        "채널구독자수_API": ("채널구독자수", 0.15),
        "채널총영상수_API": ("채널총영상수", 0.10),
        "최근영상조회수평균": ("최근영상조회수평균", 0.20),
        "최근영상좋아요수평균": ("최근영상좋아요평균", 0.10),
        "최근영상댓글수평균": ("최근영상댓글수평균", 0.10),
        "최근영상참여율평균": ("최근영상참여율평균", 0.20),
        "최근영상실제라이브시작비율": ("최근영상실제라이브시작비율", 0.10),
        "최근영상길이초평균": ("최근영상길이초평균", 0.05),
    }

    ref_profile = {}
    for ref_col, (cand_col, weight) in ref_compare_map.items():
        if ref_col not in ref_df.columns:
            continue
        s = pd.to_numeric(ref_df[ref_col], errors="coerce").dropna()
        if len(s) == 0:
            continue
        ref_profile[cand_col] = {
            "median": s.median(),
            "q1": s.quantile(0.25),
            "q3": s.quantile(0.75),
            "iqr": s.quantile(0.75) - s.quantile(0.25),
            "weight": weight,
        }

    score_cols = []
    score_weights = []

    for cand_col, params in ref_profile.items():
        if cand_col not in cand_df.columns:
            continue

        cand_df[cand_col] = pd.to_numeric(cand_df[cand_col], errors="coerce")
        score_col = f"{cand_col}_씨미유사도"
        cand_df[score_col] = cand_df[cand_col].apply(
            lambda x: similarity_from_reference(
                x, params["median"], params["q1"], params["q3"], params["iqr"]
            )
        )
        score_cols.append(score_col)
        score_weights.append(params["weight"])

    cand_df["씨미유사도점수"] = cand_df.apply(
        lambda r: weighted_mean_ignore_nan(r, score_cols, score_weights),
        axis=1
    )

    if "최근영상실제라이브시작비율" in cand_df.columns:
        cand_df["라이브신호존재여부"] = np.where(
            pd.to_numeric(cand_df["최근영상실제라이브시작비율"], errors="coerce").fillna(0) > 0,
            1, 0
        )
    else:
        cand_df["라이브신호존재여부"] = 0

    def grade(x):
        if pd.isna(x):
            return "미산출"
        if x >= 0.80:
            return "매우높음"
        elif x >= 0.65:
            return "높음"
        elif x >= 0.50:
            return "보통"
        else:
            return "낮음"

    cand_df["씨미유사도등급"] = cand_df["씨미유사도점수"].apply(grade)

    cand_df = cand_df.sort_values(
        ["씨미유사도점수"],
        ascending=[False]
    ).reset_index(drop=True)

    cand_df.to_csv(CIME_SIMILARITY_SCORED_PATH, index=False, encoding="utf-8-sig")

    if "대표세그먼트" in cand_df.columns:
        seg_summary = (
            cand_df.groupby("대표세그먼트", dropna=False)
            .agg(
                채널수=("씨미유사도점수", "count"),
                씨미유사도평균=("씨미유사도점수", "mean"),
                씨미유사도중앙값=("씨미유사도점수", "median"),
                라이브신호채널수=("라이브신호존재여부", "sum"),
            )
            .reset_index()
            .sort_values("씨미유사도평균", ascending=False)
        )
        seg_summary.to_csv(CIME_SIMILARITY_SEGMENT_SUMMARY_PATH, index=False, encoding="utf-8-sig")

    print("저장 완료:")
    print(" - scored :", CIME_SIMILARITY_SCORED_PATH)
    print(" - segment:", CIME_SIMILARITY_SEGMENT_SUMMARY_PATH)