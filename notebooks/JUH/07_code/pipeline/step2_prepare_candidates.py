import pandas as pd
import numpy as np

from config import (
    CANDIDATE_AGG_INPUT_PATH,
    CANDIDATE_DISCOVERY_MERGED_PATH,
    CANDIDATE_PREPARED_PATH,
    MIN_SUBSCRIBERS_FOR_CANDIDATE,
    MIN_VIDEO_SAMPLE_FOR_CANDIDATE,
    LOWER_TO_UPPER_SEGMENT,
)


def _clean_object_columns(df: pd.DataFrame) -> pd.DataFrame:
    for col in df.columns:
        if df[col].dtype == "object":
            df[col] = df[col].astype(str).str.strip()
            df.loc[df[col].isin(["", "nan", "None", "NaN", "<NA>"]), col] = pd.NA
    return df


def _get_mode_or_first(series: pd.Series):
    s = series.dropna().astype(str)
    if len(s) == 0:
        return pd.NA
    mode_vals = s.mode()
    if len(mode_vals) > 0:
        return mode_vals.iloc[0]
    return s.iloc[0]


def _ensure_segment_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    입력 df에 세그먼트 컬럼을 보정한다.

    우선순위
    1) lower_segment / upper_segment
    2) 대표하위세그먼트 / 대표상위세그먼트
    3) segment_seed / 대표세그먼트
    """
    lower_col = None
    for c in ["lower_segment", "대표하위세그먼트", "segment_seed", "대표세그먼트"]:
        if c in df.columns:
            lower_col = c
            break

    upper_col = None
    for c in ["upper_segment", "대표상위세그먼트"]:
        if c in df.columns:
            upper_col = c
            break

    if lower_col is not None:
        df["대표하위세그먼트"] = df[lower_col]
    else:
        df["대표하위세그먼트"] = pd.NA

    if upper_col is not None:
        df["대표상위세그먼트"] = df[upper_col]
    else:
        df["대표상위세그먼트"] = pd.NA

    df["대표상위세그먼트"] = df["대표상위세그먼트"].fillna(
        df["대표하위세그먼트"].map(LOWER_TO_UPPER_SEGMENT)
    )

    df["대표세그먼트"] = df["대표상위세그먼트"]
    return df


def _log_segment_distribution(df: pd.DataFrame, title: str = ""):
    if title:
        print(f"\n===== {title} =====")

    if "대표상위세그먼트" in df.columns:
        print("\n[대표상위세그먼트 분포]")
        print(df["대표상위세그먼트"].value_counts(dropna=False))

    if "대표하위세그먼트" in df.columns:
        print("\n[대표하위세그먼트 분포]")
        print(df["대표하위세그먼트"].value_counts(dropna=False).head(30))


def _build_discovery_channel_agg(video_path) -> pd.DataFrame:
    """
    discovery 결과(youtube_video_kr.csv)를 채널 단위로 집계해서
    prepared 입력에 직접 반영할 수 있는 형태로 만든다.
    """
    if not video_path.exists():
        print(f"[discovery agg] 파일 없음: {video_path}")
        return pd.DataFrame(columns=["채널ID"])

    dfv = pd.read_csv(video_path, encoding="utf-8-sig")
    if dfv.empty:
        print("[discovery agg] video raw 비어 있음")
        return pd.DataFrame(columns=["채널ID"])

    dfv = _clean_object_columns(dfv)

    rename_map = {}
    if "channel_id" in dfv.columns:
        rename_map["channel_id"] = "채널ID"
    if "channel_title" in dfv.columns:
        rename_map["channel_title"] = "채널명"
    if rename_map:
        dfv = dfv.rename(columns=rename_map)

    if "채널ID" not in dfv.columns:
        raise ValueError("discovery raw에 channel_id/채널ID 컬럼이 없습니다.")

    for c in ["view_count", "like_count", "comment_count", "duration_sec"]:
        if c in dfv.columns:
            dfv[c] = pd.to_numeric(dfv[c], errors="coerce")

    if "has_live_actual_start" in dfv.columns:
        dfv["has_live_actual_start"] = pd.to_numeric(dfv["has_live_actual_start"], errors="coerce")

    if "published_at" in dfv.columns:
        dfv["published_at"] = pd.to_datetime(dfv["published_at"], errors="coerce", utc=True).dt.tz_localize(None)

    if "view_count" in dfv.columns:
        dfv["engagement_per_view"] = (
            (dfv.get("like_count", 0).fillna(0) + dfv.get("comment_count", 0).fillna(0))
            / dfv["view_count"].replace(0, np.nan)
        )
    else:
        dfv["engagement_per_view"] = np.nan

    dfv = _ensure_segment_columns(dfv)

    agg_dict = {
        "채널명": _get_mode_or_first,
        "대표하위세그먼트": _get_mode_or_first,
        "대표상위세그먼트": _get_mode_or_first,
        "대표세그먼트": _get_mode_or_first,
    }

    if "view_count" in dfv.columns:
        agg_dict["view_count"] = "mean"
    if "like_count" in dfv.columns:
        agg_dict["like_count"] = "mean"
    if "comment_count" in dfv.columns:
        agg_dict["comment_count"] = "mean"
    if "engagement_per_view" in dfv.columns:
        agg_dict["engagement_per_view"] = "mean"
    if "has_live_actual_start" in dfv.columns:
        agg_dict["has_live_actual_start"] = "mean"
    if "duration_sec" in dfv.columns:
        agg_dict["duration_sec"] = "mean"
    if "published_at" in dfv.columns:
        agg_dict["published_at"] = "max"
    if "video_id" in dfv.columns:
        agg_dict["video_id"] = "count"

    grouped = dfv.groupby("채널ID", as_index=False).agg(agg_dict)

    rename_final = {
        "view_count": "최근영상조회수평균",
        "like_count": "최근영상좋아요평균",
        "comment_count": "최근영상댓글수평균",
        "engagement_per_view": "최근영상참여율평균",
        "has_live_actual_start": "최근영상실제라이브시작비율",
        "duration_sec": "최근영상길이초평균",
        "published_at": "최근최신업로드일",
        "video_id": "수집영상수",
    }
    grouped = grouped.rename(columns=rename_final)

    grouped["discovery반영여부"] = 1

    grouped["대표상위세그먼트"] = grouped["대표상위세그먼트"].fillna(
        grouped["대표하위세그먼트"].map(LOWER_TO_UPPER_SEGMENT)
    )
    grouped["대표세그먼트"] = grouped["대표상위세그먼트"]

    print("[discovery agg] rows:", len(grouped))
    return grouped


def _coalesce_columns(base_df: pd.DataFrame, update_df: pd.DataFrame, key: str, columns: list) -> pd.DataFrame:
    merged = base_df.merge(
        update_df[[key] + [c for c in columns if c in update_df.columns]],
        on=key,
        how="left",
        suffixes=("", "__new")
    )

    for col in columns:
        new_col = f"{col}__new"
        if new_col in merged.columns:
            if col not in merged.columns:
                merged[col] = pd.NA
            merged[col] = merged[new_col].combine_first(merged[col])

    drop_cols = [c for c in merged.columns if c.endswith("__new")]
    if drop_cols:
        merged = merged.drop(columns=drop_cols)

    return merged


def run():
    print("[STEP2] 일반 후보 데이터 준비 시작")

    if not CANDIDATE_AGG_INPUT_PATH.exists():
        raise FileNotFoundError(f"입력 파일 없음: {CANDIDATE_AGG_INPUT_PATH}")

    # -----------------------------------------------------
    # 1) 기존 candidate agg input 로드
    # -----------------------------------------------------
    df = pd.read_csv(CANDIDATE_AGG_INPUT_PATH, encoding="utf-8-sig")
    print("원본 rows:", len(df))
    print("원본 cols:", len(df.columns))

    df = _clean_object_columns(df)
    df = _ensure_segment_columns(df)

    if "채널ID" not in df.columns:
        raise ValueError("candidate agg input에 '채널ID' 컬럼이 없습니다.")

    if "discovery반영여부" not in df.columns:
        df["discovery반영여부"] = 0

    # -----------------------------------------------------
    # 2) discovery 채널 집계 생성 및 merge
    # -----------------------------------------------------
    df_discovery_agg = _build_discovery_channel_agg(CANDIDATE_DISCOVERY_MERGED_PATH)

    if not df_discovery_agg.empty:
        missing_channels = df_discovery_agg.loc[
            ~df_discovery_agg["채널ID"].astype(str).isin(df["채널ID"].astype(str))
        ].copy()

        if len(missing_channels) > 0:
            print(f"[discovery merge] base에 없던 신규 채널 추가: {len(missing_channels)}")
            all_cols = sorted(set(df.columns) | set(missing_channels.columns))
            df = df.reindex(columns=all_cols)
            missing_channels = missing_channels.reindex(columns=all_cols)
            df = pd.concat([df, missing_channels], ignore_index=True)

        update_cols = [
            "채널명",
            "대표하위세그먼트",
            "대표상위세그먼트",
            "대표세그먼트",
            "수집영상수",
            "최근영상조회수평균",
            "최근영상좋아요평균",
            "최근영상댓글수평균",
            "최근영상참여율평균",
            "최근영상실제라이브시작비율",
            "최근영상길이초평균",
            "최근최신업로드일",
            "discovery반영여부",
        ]
        df = _coalesce_columns(df, df_discovery_agg, key="채널ID", columns=update_cols)

        df["대표상위세그먼트"] = df["대표상위세그먼트"].fillna(
            df["대표하위세그먼트"].map(LOWER_TO_UPPER_SEGMENT)
        )
        df["대표세그먼트"] = df["대표상위세그먼트"]

        print("[discovery merge] 반영 후 rows:", len(df))

    # -----------------------------------------------------
    # 3) 필터링
    # -----------------------------------------------------
    if "한국채널추정여부" in df.columns:
        df["한국채널추정여부"] = pd.to_numeric(df["한국채널추정여부"], errors="coerce")
        before = len(df)
        df = df[df["한국채널추정여부"] == 1].copy()
        print(f"한국채널추정여부 필터: {before} -> {len(df)}")

    if "채널구독자수" in df.columns:
        df["채널구독자수"] = pd.to_numeric(df["채널구독자수"], errors="coerce")
        before = len(df)
        df = df[df["채널구독자수"].fillna(0) >= MIN_SUBSCRIBERS_FOR_CANDIDATE].copy()
        print(f"채널구독자수 필터: {before} -> {len(df)}")

    # -----------------------------------------------------
    # 3-1) 수집영상수 필터 완화형
    # - 일반 채널: 기존 기준 유지
    # - discovery반영여부 == 1: 1개 이상이면 통과
    # -----------------------------------------------------
    if "수집영상수" in df.columns:
        df["수집영상수"] = pd.to_numeric(df["수집영상수"], errors="coerce")
        if "discovery반영여부" not in df.columns:
            df["discovery반영여부"] = 0

        df["discovery반영여부"] = pd.to_numeric(df["discovery반영여부"], errors="coerce").fillna(0)

        before = len(df)

        normal_mask = (df["discovery반영여부"] != 1) & (df["수집영상수"].fillna(0) >= MIN_VIDEO_SAMPLE_FOR_CANDIDATE)
        discovery_relaxed_mask = (df["discovery반영여부"] == 1) & (df["수집영상수"].fillna(0) >= 1)

        df = df[normal_mask | discovery_relaxed_mask].copy()

        print(
            f"수집영상수 필터(완화형): {before} -> {len(df)} "
            f"| 일반기준>={MIN_VIDEO_SAMPLE_FOR_CANDIDATE}, discovery반영채널>=1"
        )

    # -----------------------------------------------------
    # 4) 채널ID 기준 대표값 1행 정리
    # -----------------------------------------------------
    if "채널ID" in df.columns:
        before = len(df)

        agg_dict = {}
        for col in df.columns:
            if col == "채널ID":
                continue

            if col in ["대표상위세그먼트", "대표하위세그먼트", "대표세그먼트", "채널명"]:
                agg_dict[col] = _get_mode_or_first
            elif df[col].dtype == "object":
                agg_dict[col] = _get_mode_or_first
            else:
                agg_dict[col] = "first"

        df = (
            df.groupby("채널ID", as_index=False)
              .agg(agg_dict)
        )

        df["대표상위세그먼트"] = df["대표상위세그먼트"].fillna(
            df["대표하위세그먼트"].map(LOWER_TO_UPPER_SEGMENT)
        )
        df["대표세그먼트"] = df["대표상위세그먼트"]

        print(f"채널ID 중복제거: {before} -> {len(df)}")

    print("최종 rows:", len(df))
    print("최종 cols:", len(df.columns))

    _log_segment_distribution(df, title="prepared 최종 세그먼트 분포")

    target_segments = ["일렉기타연주", "드럼연주"]
    if "대표하위세그먼트" in df.columns:
        print("\n[신규 세그먼트 반영 확인]")
        print(df[df["대표하위세그먼트"].isin(target_segments)]["대표하위세그먼트"].value_counts(dropna=False))

    if "discovery반영여부" in df.columns:
        print("\n[discovery반영여부 분포]")
        print(df["discovery반영여부"].value_counts(dropna=False))

    df.to_csv(CANDIDATE_PREPARED_PATH, index=False, encoding="utf-8-sig")
    print("저장 완료:", CANDIDATE_PREPARED_PATH)


if __name__ == "__main__":
    run()