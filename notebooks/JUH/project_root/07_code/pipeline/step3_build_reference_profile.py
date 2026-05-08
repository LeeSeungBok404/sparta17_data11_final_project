import pandas as pd
import numpy as np
from config import (
    CIME_TOP30_REFERENCE_PROFILE_PATH,
    CIME_REFERENCE_PROFILE_FILTERED_PATH,
    CIME_REFERENCE_PROFILE_SUMMARY_PATH,
    CIME_REFERENCE_PROFILE_DISTRIBUTION_PATH,
    USE_REFERENCE_STRICT_FIRST,
)

def _make_summary(series, metric_name):
    s = pd.to_numeric(series, errors="coerce").dropna()
    if len(s) == 0:
        return {
            "지표명": metric_name,
            "표본수": 0,
            "평균": np.nan,
            "중앙값": np.nan,
            "표준편차": np.nan,
            "최소값": np.nan,
            "Q1": np.nan,
            "Q3": np.nan,
            "최대값": np.nan,
            "IQR": np.nan,
        }
    return {
        "지표명": metric_name,
        "표본수": len(s),
        "평균": s.mean(),
        "중앙값": s.median(),
        "표준편차": s.std(),
        "최소값": s.min(),
        "Q1": s.quantile(0.25),
        "Q3": s.quantile(0.75),
        "최대값": s.max(),
        "IQR": s.quantile(0.75) - s.quantile(0.25),
    }


def run():
    print("[STEP3] CME 레퍼런스 프로필 생성 시작")

    if not CIME_TOP30_REFERENCE_PROFILE_PATH.exists():
        raise FileNotFoundError(f"입력 파일 없음: {CIME_TOP30_REFERENCE_PROFILE_PATH}")

    df = pd.read_csv(CIME_TOP30_REFERENCE_PROFILE_PATH, encoding="utf-8-sig")
    print("원본 rows:", len(df))

    for col in df.columns:
        if df[col].dtype == "object":
            df[col] = df[col].astype(str).str.strip()
            df.loc[df[col].isin(["", "nan", "None", "NaN"]), col] = pd.NA

    # 엄격 기준 우선
    if USE_REFERENCE_STRICT_FIRST and "레퍼런스자동추천_엄격" in df.columns and df["레퍼런스자동추천_엄격"].eq("Y").sum() > 0:
        ref_df = df[df["레퍼런스자동추천_엄격"] == "Y"].copy()
        ref_type = "엄격"
    elif "레퍼런스자동추천" in df.columns and df["레퍼런스자동추천"].eq("Y").sum() > 0:
        ref_df = df[df["레퍼런스자동추천"] == "Y"].copy()
        ref_type = "기본"
    else:
        ref_df = df.copy()
        ref_type = "전체"

    if "본채널여부" in ref_df.columns:
        ref_df = ref_df[ref_df["본채널여부"].fillna("").eq("Y")].copy()

    print("선택 기준:", ref_type)
    print("레퍼런스 rows:", len(ref_df))

    metrics = {
        "채널구독자수_API": "채널구독자수",
        "채널총조회수_API": "채널총조회수",
        "채널총영상수_API": "채널총영상수",
        "최근수집영상수": "최근수집영상수",
        "최근영상조회수평균": "최근영상조회수평균",
        "최근영상좋아요수평균": "최근영상좋아요수평균",
        "최근영상댓글수평균": "최근영상댓글수평균",
        "최근영상참여율평균": "최근영상참여율평균",
        "최근영상실제라이브시작비율": "최근영상실제라이브시작비율",
        "최근영상길이초평균": "최근영상길이초평균",
    }

    summary_rows = []
    for col, label in metrics.items():
        if col in ref_df.columns:
            summary_rows.append(_make_summary(ref_df[col], label))

    summary_df = pd.DataFrame(summary_rows)
    summary_df.to_csv(CIME_REFERENCE_PROFILE_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    ref_df.to_csv(CIME_REFERENCE_PROFILE_FILTERED_PATH, index=False, encoding="utf-8-sig")

    # 간단 분포표
    dist_rows = []
    for col in ["본채널여부", "레퍼런스자동추천", "레퍼런스자동추천_엄격"]:
        if col in ref_df.columns:
            vc = ref_df[col].value_counts(dropna=False)
            for k, v in vc.items():
                dist_rows.append({
                    "구분": col,
                    "값": k,
                    "채널수": v,
                    "비율": v / len(ref_df) if len(ref_df) > 0 else np.nan
                })

    dist_df = pd.DataFrame(dist_rows)
    dist_df.to_csv(CIME_REFERENCE_PROFILE_DISTRIBUTION_PATH, index=False, encoding="utf-8-sig")

    print("저장 완료:")
    print(" - filtered:", CIME_REFERENCE_PROFILE_FILTERED_PATH)
    print(" - summary :", CIME_REFERENCE_PROFILE_SUMMARY_PATH)
    print(" - dist    :", CIME_REFERENCE_PROFILE_DISTRIBUTION_PATH)