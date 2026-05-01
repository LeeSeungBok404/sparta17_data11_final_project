import pandas as pd
from datetime import datetime
from config import (
    CIME_REFERENCE_PROFILE_SUMMARY_PATH,
    CIME_REFERENCE_PROFILE_FILTERED_PATH,
    CIME_SIMILARITY_SCORED_PATH,
    CIME_FINAL_SHORTLIST_PATH,
    CIME_FINAL_SHORTLIST_BY_SEGMENT_PATH,
    DASHBOARD_SUMMARY_PATH,
    DASHBOARD_CANDIDATE_TABLE_PATH,
    DASHBOARD_SEGMENT_TABLE_PATH,
    DASHBOARD_REFERENCE_TABLE_PATH,
)


def run():
    print("[STEP6] 대시보드용 데이터 저장 시작")

    ref_summary = pd.read_csv(CIME_REFERENCE_PROFILE_SUMMARY_PATH, encoding="utf-8-sig") if CIME_REFERENCE_PROFILE_SUMMARY_PATH.exists() else pd.DataFrame()
    ref_filtered = pd.read_csv(CIME_REFERENCE_PROFILE_FILTERED_PATH, encoding="utf-8-sig") if CIME_REFERENCE_PROFILE_FILTERED_PATH.exists() else pd.DataFrame()
    scored = pd.read_csv(CIME_SIMILARITY_SCORED_PATH, encoding="utf-8-sig") if CIME_SIMILARITY_SCORED_PATH.exists() else pd.DataFrame()
    shortlist = pd.read_csv(CIME_FINAL_SHORTLIST_PATH, encoding="utf-8-sig") if CIME_FINAL_SHORTLIST_PATH.exists() else pd.DataFrame()
    shortlist_seg = pd.read_csv(CIME_FINAL_SHORTLIST_BY_SEGMENT_PATH, encoding="utf-8-sig") if CIME_FINAL_SHORTLIST_BY_SEGMENT_PATH.exists() else pd.DataFrame()

    summary_row = {
        "기준시각": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "레퍼런스채널수": len(ref_filtered),
        "유사도산출후보수": len(scored),
        "최종shortlist수": len(shortlist),
        "라이브신호후보수": int(scored["라이브신호존재여부"].sum()) if "라이브신호존재여부" in scored.columns and len(scored) > 0 else 0,
        "평균씨미유사도": scored["씨미유사도점수"].mean() if "씨미유사도점수" in scored.columns and len(scored) > 0 else None,
    }
    dashboard_summary = pd.DataFrame([summary_row])

    # 후보 테이블
    candidate_cols = [
        "채널ID",
        "채널명",
        "대표세그먼트",
        "채널규모구간",
        "채널구독자수",
        "최근영상조회수평균",
        "최근영상참여율평균",
        "최근영상실제라이브시작비율",
        "씨미유사도점수",
        "씨미유사도등급",
        "라이브신호존재여부",
    ]
    candidate_cols = [c for c in candidate_cols if c in scored.columns]
    dashboard_candidate = scored[candidate_cols].copy() if len(candidate_cols) > 0 else pd.DataFrame()

    # 세그먼트 테이블
    if len(shortlist_seg) > 0 and "대표세그먼트" in shortlist_seg.columns:
        seg_table = (
            shortlist_seg.groupby("대표세그먼트", dropna=False)
            .agg(
                shortlist채널수=("대표세그먼트", "count"),
                평균씨미유사도=("씨미유사도점수", "mean") if "씨미유사도점수" in shortlist_seg.columns else ("대표세그먼트", "count"),
            )
            .reset_index()
        )
    else:
        seg_table = pd.DataFrame()

    # 레퍼런스 테이블
    dashboard_reference = ref_summary.copy()

    dashboard_summary.to_csv(DASHBOARD_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    dashboard_candidate.to_csv(DASHBOARD_CANDIDATE_TABLE_PATH, index=False, encoding="utf-8-sig")
    seg_table.to_csv(DASHBOARD_SEGMENT_TABLE_PATH, index=False, encoding="utf-8-sig")
    dashboard_reference.to_csv(DASHBOARD_REFERENCE_TABLE_PATH, index=False, encoding="utf-8-sig")

    print("저장 완료:")
    print(" - dashboard summary   :", DASHBOARD_SUMMARY_PATH)
    print(" - dashboard candidate :", DASHBOARD_CANDIDATE_TABLE_PATH)
    print(" - dashboard segment   :", DASHBOARD_SEGMENT_TABLE_PATH)
    print(" - dashboard reference :", DASHBOARD_REFERENCE_TABLE_PATH)