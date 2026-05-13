import pandas as pd
import numpy as np
from datetime import datetime

from config import (
    CANDIDATE_SCORED_FINAL_PATH,
    DASHBOARD_SUMMARY_PATH,
    DASHBOARD_CANDIDATE_TABLE_PATH,
    DASHBOARD_SEGMENT_TABLE_PATH,
    DASHBOARD_REFERENCE_TABLE_PATH,
    FINAL_CORE_OUTPUT_DIR,
)


# step5_build_shortlist_tracking.py에서 생성하는 파일
CANDIDATE_SHORTLIST_TRACKING_PATH = FINAL_CORE_OUTPUT_DIR / "candidate_shortlist_tracking.csv"


ACTION_BUCKETS = ["즉시검토", "검증필요", "성장관찰", "보류", "제외", "미분류"]


TRACKING_COL_CANDIDATES = [
    "채널ID",
    "전회차순위",
    "순위변동",
    "운영우선순위변동",
    "최종점수변동",
    "성장성점수변동",
    "팬밀도점수변동",
    "실전성점수변동",
    "신규진입여부",
    "액션버킷변동여부",
    "shortlist_신규선정여부",
    "shortlist_유지여부",
    "shortlist_이탈여부",
    "변동방향",
    "변화요약",
]


# step4 운영형 scoring 수정본에서 생성되는 컬럼들
OPERATIONAL_COL_CANDIDATES = [
    "성장성점수_raw",
    "최종점수분위",
    "채널력점수분위",
    "성장성점수분위",
    "팬밀도점수분위",
    "라이브친화점수분위",
    "실전성점수분위",
    "shortlist_선정여부",
    "shortlist_유형",
    "운영우선순위",
    "추천사유",
    "주의사유",
    "자동판정근거",
]


def _read_csv_if_exists(path):
    return pd.read_csv(path, encoding="utf-8-sig") if path.exists() else pd.DataFrame()


def _first_existing(df: pd.DataFrame, candidates):
    for c in candidates:
        if c in df.columns:
            return c
    return None


def _safe_numeric(df: pd.DataFrame, cols):
    for c in cols:
        if c is not None and c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")


def _pct(x, total):
    if total == 0:
        return 0.0
    return x / total


def _normalize_channel_id(df: pd.DataFrame, channel_id_col: str = "채널ID") -> pd.DataFrame:
    if channel_id_col in df.columns:
        df[channel_id_col] = df[channel_id_col].astype(str).str.strip()
    return df


def _merge_tracking(scored: pd.DataFrame, channel_id_col: str | None) -> pd.DataFrame:
    """
    step5_build_shortlist_tracking.py 결과를 scored에 left merge한다.
    tracking 파일이 없으면 기존 scored를 그대로 반환한다.
    """
    if channel_id_col is None:
        print("[tracking skip] scored에 채널ID 컬럼이 없어 변화량 merge 생략")
        return scored

    tracking = _read_csv_if_exists(CANDIDATE_SHORTLIST_TRACKING_PATH)
    if tracking.empty:
        print(f"[tracking skip] tracking 파일 없음 또는 비어있음: {CANDIDATE_SHORTLIST_TRACKING_PATH}")
        return scored

    if "채널ID" not in tracking.columns:
        print("[tracking skip] tracking 파일에 채널ID 컬럼 없음")
        return scored

    tracking = _normalize_channel_id(tracking, "채널ID")

    use_cols = [c for c in TRACKING_COL_CANDIDATES if c in tracking.columns]
    if "채널ID" not in use_cols:
        use_cols = ["채널ID"] + use_cols

    tracking_small = tracking[use_cols].drop_duplicates(subset=["채널ID"], keep="last").copy()

    # scored의 채널ID 컬럼명이 다를 수 있는 상황에 대비
    if channel_id_col != "채널ID":
        tracking_small = tracking_small.rename(columns={"채널ID": channel_id_col})

    # 이미 같은 변화량 컬럼이 scored에 있으면 tracking 값을 우선 사용하기 위해 제거 후 merge
    overlap_cols = [c for c in tracking_small.columns if c != channel_id_col and c in scored.columns]
    if overlap_cols:
        scored = scored.drop(columns=overlap_cols)

    out = scored.merge(tracking_small, on=channel_id_col, how="left")
    print(f"[tracking merge] rows={len(out):,} | tracking_cols={len(use_cols)} | path={CANDIDATE_SHORTLIST_TRACKING_PATH}")
    return out


def _count_bool_like(series: pd.Series) -> int:
    """True/1/Y/yes/선정 등 다양한 표현을 True로 집계한다."""
    if series is None:
        return 0
    s = series.fillna(False)
    if s.dtype == bool:
        return int(s.sum())
    s = s.astype(str).str.strip().str.lower()
    return int(s.isin(["true", "1", "y", "yes", "선정", "신규", "유지"]).sum())


def run():
    print("[STEP6] 대시보드용 데이터 저장 시작")

    scored = _read_csv_if_exists(CANDIDATE_SCORED_FINAL_PATH)
    if scored.empty:
        raise FileNotFoundError(
            f"candidate_scored_final.csv 없음 또는 비어있음: {CANDIDATE_SCORED_FINAL_PATH}"
        )

    print("scored rows:", len(scored))

    # -----------------------------------------------------
    # 컬럼 탐색
    # -----------------------------------------------------
    channel_id_col = _first_existing(scored, ["채널ID"])
    channel_name_col = _first_existing(scored, ["채널명"])
    upper_col = _first_existing(scored, ["대표상위세그먼트", "대표세그먼트"])
    lower_col = _first_existing(scored, ["대표하위세그먼트"])
    action_col = _first_existing(scored, ["액션버킷", "action_bucket"])
    rank_col = _first_existing(scored, ["최종순위", "rank"])
    final_score_col = _first_existing(scored, ["최종점수", "final_score"])

    base_col = _first_existing(scored, ["채널력점수"])
    growth_col = _first_existing(scored, ["성장성점수"])
    fan_col = _first_existing(scored, ["팬밀도점수"])
    live_col = _first_existing(scored, ["라이브친화점수"])
    exec_col = _first_existing(scored, ["실전성점수"])

    subs_col = _first_existing(scored, ["채널구독자수"])
    view_col = _first_existing(scored, ["최근영상조회수평균"])
    eng_col = _first_existing(scored, ["최근영상참여율평균"])

    growth_proxy_col = _first_existing(scored, ["성장성점수_proxy"])
    growth_conf_col = _first_existing(scored, ["성장성신뢰도"])
    growth_conf_grade_col = _first_existing(scored, ["성장성신뢰도등급"])

    # 운영형 shortlist 컬럼
    shortlist_selected_col = _first_existing(scored, ["shortlist_선정여부"])
    shortlist_type_col = _first_existing(scored, ["shortlist_유형"])
    operation_priority_col = _first_existing(scored, ["운영우선순위"])
    recommend_reason_col = _first_existing(scored, ["추천사유"])
    caution_reason_col = _first_existing(scored, ["주의사유"])
    decision_basis_col = _first_existing(scored, ["자동판정근거"])

    _safe_numeric(
        scored,
        [
            final_score_col,
            base_col,
            growth_col,
            fan_col,
            live_col,
            exec_col,
            subs_col,
            view_col,
            eng_col,
            growth_proxy_col,
            growth_conf_col,
            "성장성점수_raw",
            "최종점수분위",
            "채널력점수분위",
            "성장성점수분위",
            "팬밀도점수분위",
            "라이브친화점수분위",
            "실전성점수분위",
            operation_priority_col,
        ],
    )

    if channel_id_col is not None:
        scored[channel_id_col] = scored[channel_id_col].astype(str).str.strip()

    # -----------------------------------------------------
    # step5 tracking 결과 merge
    # -----------------------------------------------------
    scored = _merge_tracking(scored, channel_id_col=channel_id_col)

    # tracking merge 후 숫자형 보정
    _safe_numeric(
        scored,
        [
            "전회차순위",
            "순위변동",
            "운영우선순위변동",
            "최종점수변동",
            "성장성점수변동",
            "팬밀도점수변동",
            "실전성점수변동",
        ],
    )

    # -----------------------------------------------------
    # 정렬 보정
    # -----------------------------------------------------
    if rank_col is not None and rank_col in scored.columns:
        scored = scored.sort_values(rank_col, ascending=True).reset_index(drop=True)
    elif final_score_col is not None and final_score_col in scored.columns:
        scored = scored.sort_values(final_score_col, ascending=False).reset_index(drop=True)
        scored["최종순위"] = np.arange(1, len(scored) + 1)
        rank_col = "최종순위"

    total_rows = len(scored)
    unique_channels = scored[channel_id_col].nunique() if channel_id_col is not None else total_rows
    unique_upper_segments = scored[upper_col].nunique(dropna=True) if upper_col is not None else None

    # -----------------------------------------------------
    # 액션버킷 요약
    # -----------------------------------------------------
    action_counts = {}
    if action_col is not None and action_col in scored.columns:
        vc = scored[action_col].fillna("미분류").value_counts(dropna=False)
        action_counts = vc.to_dict()

    # -----------------------------------------------------
    # shortlist / 변화량 요약
    # -----------------------------------------------------
    shortlist_count = _count_bool_like(scored[shortlist_selected_col]) if shortlist_selected_col in scored.columns else 0
    new_shortlist_count = _count_bool_like(scored["shortlist_신규선정여부"]) if "shortlist_신규선정여부" in scored.columns else 0
    retained_shortlist_count = _count_bool_like(scored["shortlist_유지여부"]) if "shortlist_유지여부" in scored.columns else 0
    dropped_shortlist_count = _count_bool_like(scored["shortlist_이탈여부"]) if "shortlist_이탈여부" in scored.columns else 0
    new_entry_count = _count_bool_like(scored["신규진입여부"]) if "신규진입여부" in scored.columns else 0

    # -----------------------------------------------------
    # 1) dashboard_summary.csv
    # -----------------------------------------------------
    summary_row = {
        "기준시각": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "후보행수": total_rows,
        "고유채널수": unique_channels,
        "상위세그먼트수": unique_upper_segments,
        "평균최종점수": scored[final_score_col].mean() if final_score_col is not None else None,
        "중앙최종점수": scored[final_score_col].median() if final_score_col is not None else None,
        "평균채널력점수": scored[base_col].mean() if base_col is not None else None,
        "평균성장성점수": scored[growth_col].mean() if growth_col is not None else None,
        "평균팬밀도점수": scored[fan_col].mean() if fan_col is not None else None,
        "평균라이브친화점수": scored[live_col].mean() if live_col is not None else None,
        "평균실전성점수": scored[exec_col].mean() if exec_col is not None else None,
        "평균성장성신뢰도": scored[growth_conf_col].mean() if growth_conf_col is not None else None,
        "shortlist선정수": shortlist_count,
        "shortlist선정비율": _pct(shortlist_count, total_rows),
        "shortlist신규선정수": new_shortlist_count,
        "shortlist유지수": retained_shortlist_count,
        "shortlist이탈수": dropped_shortlist_count,
        "신규진입수": new_entry_count,
        "tracking파일존재여부": CANDIDATE_SHORTLIST_TRACKING_PATH.exists(),
    }

    for bucket in ACTION_BUCKETS:
        cnt = action_counts.get(bucket, 0)
        summary_row[f"{bucket}수"] = cnt
        summary_row[f"{bucket}비율"] = _pct(cnt, total_rows)

    dashboard_summary = pd.DataFrame([summary_row])

    # -----------------------------------------------------
    # 2) dashboard_candidate_table.csv
    # -----------------------------------------------------
    base_candidate_cols = [
        rank_col,
        channel_id_col,
        channel_name_col,
        upper_col,
        lower_col,
        subs_col,
        view_col,
        eng_col,
        growth_proxy_col,
        growth_conf_col,
        growth_conf_grade_col,
        base_col,
        growth_col,
        fan_col,
        live_col,
        exec_col,
        final_score_col,
        action_col,
    ]

    operational_cols = [c for c in OPERATIONAL_COL_CANDIDATES if c in scored.columns]
    tracking_cols = [c for c in TRACKING_COL_CANDIDATES if c in scored.columns and c != "채널ID"]

    candidate_cols = base_candidate_cols + operational_cols + tracking_cols
    candidate_cols = [c for c in candidate_cols if c is not None and c in scored.columns]
    candidate_cols = list(dict.fromkeys(candidate_cols))

    dashboard_candidate = scored[candidate_cols].copy()

    rename_candidate = {
        rank_col: "최종순위",
        channel_id_col: "채널ID",
        channel_name_col: "채널명",
        upper_col: "대표상위세그먼트",
        lower_col: "대표하위세그먼트",
        subs_col: "채널구독자수",
        view_col: "최근영상조회수평균",
        eng_col: "최근영상참여율평균",
        growth_proxy_col: "성장성점수_proxy",
        growth_conf_col: "성장성신뢰도",
        growth_conf_grade_col: "성장성신뢰도등급",
        base_col: "채널력점수",
        growth_col: "성장성점수",
        fan_col: "팬밀도점수",
        live_col: "라이브친화점수",
        exec_col: "실전성점수",
        final_score_col: "최종점수",
        action_col: "액션버킷",
    }
    rename_candidate = {k: v for k, v in rename_candidate.items() if k is not None}
    dashboard_candidate = dashboard_candidate.rename(columns=rename_candidate)

    # 대시보드에서 바로 보기 좋게 shortlist 우선, 그다음 순위 순으로 정렬
    if "shortlist_선정여부" in dashboard_candidate.columns and "최종순위" in dashboard_candidate.columns:
        sort_tmp = dashboard_candidate.copy()
        sort_tmp["__shortlist_sort__"] = sort_tmp["shortlist_선정여부"].fillna(False).astype(str).str.lower().isin(["true", "1", "y", "yes", "선정"])
        dashboard_candidate = (
            sort_tmp.sort_values(["__shortlist_sort__", "최종순위"], ascending=[False, True])
            .drop(columns=["__shortlist_sort__"])
            .reset_index(drop=True)
        )

    # -----------------------------------------------------
    # 3) dashboard_segment_table.csv
    # -----------------------------------------------------
    if upper_col is not None:
        segment_rows = []

        for seg_name, g in scored.groupby(upper_col, dropna=False):
            row = {
                "대표상위세그먼트": seg_name,
                "후보수": len(g),
                "고유채널수": g[channel_id_col].nunique() if channel_id_col is not None else len(g),
                "평균최종점수": g[final_score_col].mean() if final_score_col is not None else None,
                "평균채널력점수": g[base_col].mean() if base_col is not None else None,
                "평균성장성점수": g[growth_col].mean() if growth_col is not None else None,
                "평균팬밀도점수": g[fan_col].mean() if fan_col is not None else None,
                "평균라이브친화점수": g[live_col].mean() if live_col is not None else None,
                "평균실전성점수": g[exec_col].mean() if exec_col is not None else None,
                "평균채널구독자수": g[subs_col].mean() if subs_col is not None else None,
                "평균최근영상조회수": g[view_col].mean() if view_col is not None else None,
                "평균최근영상참여율": g[eng_col].mean() if eng_col is not None else None,
            }

            if action_col is not None:
                action_vc = g[action_col].fillna("미분류").value_counts(dropna=False).to_dict()
                for bucket in ACTION_BUCKETS:
                    row[f"{bucket}수"] = action_vc.get(bucket, 0)

            if shortlist_selected_col is not None and shortlist_selected_col in g.columns:
                row["shortlist선정수"] = _count_bool_like(g[shortlist_selected_col])
                row["shortlist선정비율"] = _pct(row["shortlist선정수"], len(g))

            if "shortlist_신규선정여부" in g.columns:
                row["shortlist신규선정수"] = _count_bool_like(g["shortlist_신규선정여부"])

            if "신규진입여부" in g.columns:
                row["신규진입수"] = _count_bool_like(g["신규진입여부"])

            if "순위변동" in g.columns:
                row["평균순위변동"] = g["순위변동"].mean()

            if "최종점수변동" in g.columns:
                row["평균최종점수변동"] = g["최종점수변동"].mean()

            segment_rows.append(row)

        dashboard_segment = pd.DataFrame(segment_rows)

        if "평균최종점수" in dashboard_segment.columns:
            dashboard_segment = dashboard_segment.sort_values(
                "평균최종점수", ascending=False
            ).reset_index(drop=True)
    else:
        dashboard_segment = pd.DataFrame()

    # -----------------------------------------------------
    # 4) dashboard_reference_table.csv
    # 현재 목적에 맞게 "분포 요약 테이블"로 사용
    # -----------------------------------------------------
    reference_rows = []

    if action_col is not None:
        vc = scored[action_col].fillna("미분류").value_counts(dropna=False)
        for bucket, cnt in vc.items():
            reference_rows.append({
                "구분": "액션버킷",
                "항목": bucket,
                "건수": int(cnt),
                "비율": _pct(int(cnt), total_rows),
            })

    if shortlist_selected_col is not None and shortlist_selected_col in scored.columns:
        selected_cnt = _count_bool_like(scored[shortlist_selected_col])
        reference_rows.append({
            "구분": "shortlist",
            "항목": "선정",
            "건수": selected_cnt,
            "비율": _pct(selected_cnt, total_rows),
        })
        reference_rows.append({
            "구분": "shortlist",
            "항목": "미선정",
            "건수": total_rows - selected_cnt,
            "비율": _pct(total_rows - selected_cnt, total_rows),
        })

    if shortlist_type_col is not None and shortlist_type_col in scored.columns:
        type_vc = scored[shortlist_type_col].fillna("미분류").value_counts(dropna=False)
        for shortlist_type, cnt in type_vc.items():
            reference_rows.append({
                "구분": "shortlist_유형",
                "항목": shortlist_type,
                "건수": int(cnt),
                "비율": _pct(int(cnt), total_rows),
            })

    if "변동방향" in scored.columns:
        direction_vc = scored["변동방향"].fillna("미분류").value_counts(dropna=False)
        for direction, cnt in direction_vc.items():
            reference_rows.append({
                "구분": "변동방향",
                "항목": direction,
                "건수": int(cnt),
                "비율": _pct(int(cnt), total_rows),
            })

    if final_score_col is not None:
        bins = [-np.inf, 0.4, 0.5, 0.6, 0.7, np.inf]
        labels = ["0.40 이하", "0.40~0.50", "0.50~0.60", "0.60~0.70", "0.70 초과"]
        band = pd.cut(scored[final_score_col], bins=bins, labels=labels)
        band_vc = band.value_counts(dropna=False).sort_index()
        for score_band, cnt in band_vc.items():
            reference_rows.append({
                "구분": "최종점수밴드",
                "항목": str(score_band),
                "건수": int(cnt),
                "비율": _pct(int(cnt), total_rows),
            })

    if growth_conf_grade_col is not None:
        conf_vc = scored[growth_conf_grade_col].fillna("미분류").value_counts(dropna=False)
        for conf_grade, cnt in conf_vc.items():
            reference_rows.append({
                "구분": "성장성신뢰도등급",
                "항목": conf_grade,
                "건수": int(cnt),
                "비율": _pct(int(cnt), total_rows),
            })

    dashboard_reference = pd.DataFrame(reference_rows)

    # -----------------------------------------------------
    # 저장
    # -----------------------------------------------------
    dashboard_summary.to_csv(DASHBOARD_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    dashboard_candidate.to_csv(DASHBOARD_CANDIDATE_TABLE_PATH, index=False, encoding="utf-8-sig")
    dashboard_segment.to_csv(DASHBOARD_SEGMENT_TABLE_PATH, index=False, encoding="utf-8-sig")
    dashboard_reference.to_csv(DASHBOARD_REFERENCE_TABLE_PATH, index=False, encoding="utf-8-sig")

    print("saved:", DASHBOARD_SUMMARY_PATH)
    print("saved:", DASHBOARD_CANDIDATE_TABLE_PATH)
    print("saved:", DASHBOARD_SEGMENT_TABLE_PATH)
    print("saved:", DASHBOARD_REFERENCE_TABLE_PATH)

    print("[대시보드 요약]")
    print("후보행수:", total_rows)
    print("shortlist선정수:", shortlist_count)
    print("shortlist신규선정수:", new_shortlist_count)
    print("신규진입수:", new_entry_count)

    print("[STEP6] 대시보드용 데이터 저장 완료")


if __name__ == "__main__":
    run()
