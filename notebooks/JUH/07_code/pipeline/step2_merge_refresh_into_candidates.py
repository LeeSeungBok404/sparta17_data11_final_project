import pandas as pd

from config import (
    CANDIDATE_PREPARED_PATH,
    CANDIDATE_PREPARED_BACKUP_PATH,
    CANDIDATE_REFRESH_AGG_PATH,
)
from utils.io_utils import (
    load_csv_safe,
    save_csv_safe,
    print_section,
    print_kv,
)


def _clean_object_columns(df: pd.DataFrame) -> pd.DataFrame:
    for col in df.columns:
        if df[col].dtype == "object":
            df[col] = df[col].astype(str).str.strip()
            df.loc[df[col].isin(["", "nan", "None", "NaN"]), col] = pd.NA
    return df


def _coalesce_latest(base_df: pd.DataFrame, latest_df: pd.DataFrame, base_col: str, latest_col: str):
    """
    latest_col 값이 존재하면 base_col을 최신값으로 대체
    """
    if latest_col not in latest_df.columns:
        return base_df

    if base_col not in base_df.columns:
        base_df[base_col] = pd.NA

    base_df[base_col] = latest_df[latest_col].combine_first(base_df[base_col])
    return base_df


def run():
    print_section("STEP2 - Refresh 결과 후보 테이블 반영")

    if not CANDIDATE_PREPARED_PATH.exists():
        raise FileNotFoundError(f"prepared 후보 파일 없음: {CANDIDATE_PREPARED_PATH}")

    if not CANDIDATE_REFRESH_AGG_PATH.exists():
        print(f"refresh 집계 파일이 없어 merge를 건너뜁니다: {CANDIDATE_REFRESH_AGG_PATH}")
        return

    prepared_df = load_csv_safe(CANDIDATE_PREPARED_PATH)
    refresh_df = load_csv_safe(CANDIDATE_REFRESH_AGG_PATH)

    prepared_df = _clean_object_columns(prepared_df)
    refresh_df = _clean_object_columns(refresh_df)

    if "채널ID" not in prepared_df.columns:
        raise ValueError("prepared 후보 파일에 '채널ID' 컬럼이 없습니다.")
    if "채널ID" not in refresh_df.columns:
        raise ValueError("refresh 집계 파일에 '채널ID' 컬럼이 없습니다.")

    print_kv("prepared rows", len(prepared_df))
    print_kv("refresh rows", len(refresh_df))

    # backup
    save_csv_safe(prepared_df, CANDIDATE_PREPARED_BACKUP_PATH)

    # refresh 중복 제거
    refresh_df = refresh_df.drop_duplicates(subset=["채널ID"], keep="last").copy()

    merged = prepared_df.merge(
        refresh_df,
        on="채널ID",
        how="left",
        suffixes=("", "_refreshdup")
    )

    # -----------------------------------------------------
    # 최신값 우선 반영할 컬럼 매핑
    # -----------------------------------------------------
    latest_map = {
        "채널명": "채널명_최신",
        "채널설명": "채널설명_최신",
        "채널구독자수": "채널구독자수_최신",
        "채널총조회수": "채널총조회수_최신",
        "채널총영상수": "채널총영상수_최신",
        "최근수집영상수": "최근수집영상수_최신",
        "최근영상조회수평균": "최근영상조회수평균_최신",
        "최근영상좋아요평균": "최근영상좋아요평균_최신",
        "최근영상댓글수평균": "최근영상댓글수평균_최신",
        "최근영상참여율평균": "최근영상참여율평균_최신",
        "최근영상실제라이브시작비율": "최근영상실제라이브시작비율_최신",
        "최근영상길이초평균": "최근영상길이초평균_최신",
    }

    # 숫자형 보정
    numeric_base_cols = [
        "채널구독자수",
        "채널총조회수",
        "채널총영상수",
        "최근수집영상수",
        "최근영상조회수평균",
        "최근영상좋아요평균",
        "최근영상댓글수평균",
        "최근영상참여율평균",
        "최근영상실제라이브시작비율",
        "최근영상길이초평균",
    ]
    numeric_latest_cols = list(latest_map.values())

    for col in numeric_base_cols:
        if col in merged.columns:
            merged[col] = pd.to_numeric(merged[col], errors="coerce")

    for col in numeric_latest_cols:
        if col in merged.columns:
            merged[col] = pd.to_numeric(merged[col], errors="coerce")

    # 최신값 coalesce
    for base_col, latest_col in latest_map.items():
        merged = _coalesce_latest(merged, merged, base_col, latest_col)

    # refresh 반영 여부 플래그
    if "refresh반영여부" not in merged.columns:
        merged["refresh반영여부"] = 0

    merged["refresh반영여부"] = merged["채널ID"].isin(
        refresh_df["채널ID"].astype(str).str.strip().tolist()
    ).astype(int)

    # 불필요한 refreshdup 컬럼 정리
    drop_cols = [c for c in merged.columns if c.endswith("_refreshdup")]
    if drop_cols:
        merged = merged.drop(columns=drop_cols)

    save_csv_safe(merged, CANDIDATE_PREPARED_PATH)

    print_kv("saved prepared", CANDIDATE_PREPARED_PATH)
    print_kv("backup prepared", CANDIDATE_PREPARED_BACKUP_PATH)
    print_kv("refresh applied rows", int(merged["refresh반영여부"].fillna(0).sum()) if "refresh반영여부" in merged.columns else 0)
    print("STEP2 - Refresh 결과 후보 테이블 반영 완료")


if __name__ == "__main__":
    run()