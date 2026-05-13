from __future__ import annotations

from datetime import datetime, timezone, timedelta

import pandas as pd

from config import (
    CANDIDATE_PREPARED_PATH,
    CANDIDATE_GROWTH_PROXY_PATH,
    CANDIDATE_FEATURE_TABLE_PATH,
    CANDIDATE_SCORED_FINAL_PATH,
    CANDIDATE_PREPARED_SNAPSHOT_PATH,
    CANDIDATE_GROWTH_PROXY_SNAPSHOT_PATH,
    CANDIDATE_FEATURE_SNAPSHOT_PATH,
    CANDIDATE_SCORED_SNAPSHOT_PATH,
)


def _get_kst_now():
    kst = timezone(timedelta(hours=9))
    return datetime.now(kst)


def _resolve_key_col(df: pd.DataFrame) -> str | None:
    candidates = ["채널ID", "channel_id", "유튜브채널ID"]
    for c in candidates:
        if c in df.columns:
            return c
    return None


def _append_snapshot_overwrite_by_date_and_key(
    latest_path,
    snapshot_path,
    snapshot_cols: list[str] | None = None,
):
    if not latest_path.exists():
        print(f"[snapshot skip] latest 파일 없음: {latest_path}")
        return 0

    df = pd.read_csv(latest_path, encoding="utf-8-sig")

    if len(df) == 0:
        print(f"[snapshot skip] latest 파일 비어있음: {latest_path}")
        return 0

    if snapshot_cols is not None:
        use_cols = [c for c in snapshot_cols if c in df.columns]
        if not use_cols:
            print(f"[snapshot skip] 지정 컬럼 없음: {latest_path}")
            return 0
        df = df[use_cols].copy()

    key_col = _resolve_key_col(df)
    if key_col is None:
        print(f"[snapshot skip] 채널 식별 컬럼 없음: {latest_path}")
        return 0

    now_kst = _get_kst_now()
    snapshot_date = now_kst.strftime("%Y-%m-%d")
    snapshot_ts = now_kst.strftime("%Y-%m-%d %H:%M:%S")
    snapshot_week = f"{now_kst.isocalendar().year}-W{int(now_kst.isocalendar().week):02d}"

    df.insert(0, "snapshot_date", snapshot_date)
    df.insert(1, "snapshot_ts_kst", snapshot_ts)
    df.insert(2, "snapshot_week", snapshot_week)

    df[key_col] = df[key_col].astype(str).str.strip()

    if snapshot_path.exists():
        old_df = pd.read_csv(snapshot_path, encoding="utf-8-sig")

        if key_col in old_df.columns and "snapshot_date" in old_df.columns:
            old_df[key_col] = old_df[key_col].astype(str).str.strip()
            old_df["snapshot_date"] = old_df["snapshot_date"].astype(str).str.strip()

            remove_keys = set(df[key_col].tolist())
            old_df = old_df[
                ~(
                    (old_df["snapshot_date"] == snapshot_date)
                    & (old_df[key_col].isin(remove_keys))
                )
            ].copy()

        out_df = pd.concat([old_df, df], ignore_index=True)
    else:
        out_df = df.copy()

    out_df = out_df.drop_duplicates(
        subset=["snapshot_date", key_col],
        keep="last"
    ).reset_index(drop=True)

    out_df.to_csv(snapshot_path, index=False, encoding="utf-8-sig")
    print(
        f"[snapshot saved] {snapshot_path} | "
        f"appended_rows={len(df)} | total_rows={len(out_df)} | key_col={key_col}"
    )
    return len(df)


def run():
    print("=" * 60)
    print("STEP 10 - Snapshot append")
    print("=" * 60)

    prepared_cols = [
        "채널ID",
        "채널명",
        "대표상위세그먼트",
        "대표하위세그먼트",
        "채널구독자수",
        "수집영상수",
        "최근영상조회수평균",
        "최근영상참여율평균",
        "최근영상실제라이브시작비율",
        "한국채널추정여부",
        "discovery반영여부",
        "refresh반영여부",
    ]
    _append_snapshot_overwrite_by_date_and_key(
        latest_path=CANDIDATE_PREPARED_PATH,
        snapshot_path=CANDIDATE_PREPARED_SNAPSHOT_PATH,
        snapshot_cols=prepared_cols,
    )

    growth_cols = [
        "채널ID",
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
    _append_snapshot_overwrite_by_date_and_key(
        latest_path=CANDIDATE_GROWTH_PROXY_PATH,
        snapshot_path=CANDIDATE_GROWTH_PROXY_SNAPSHOT_PATH,
        snapshot_cols=growth_cols,
    )

    feature_cols = [
        "채널ID",
        "채널명",
        "대표상위세그먼트",
        "대표하위세그먼트",
        "채널구독자수",
        "최근영상조회수평균",
        "최근영상참여율평균",
        "최근영상실제라이브시작비율",
        "성장성점수_proxy",
        "성장성신뢰도",
        "성장성신뢰도등급",
        "채널력_조회수pct",
        "채널력_활동성pct",
        "채널력_구독자pct",
        "팬밀도_기본참여율pct",
        "라이브친화_기본pct",
        "라이브친화_성장변화pct",
        "팬채널리스크",
        "클립채널리스크",
        "기관채널리스크",
        "아카이브리스크",
        "실전성_대형채널패널티",
    ]
    _append_snapshot_overwrite_by_date_and_key(
        latest_path=CANDIDATE_FEATURE_TABLE_PATH,
        snapshot_path=CANDIDATE_FEATURE_SNAPSHOT_PATH,
        snapshot_cols=feature_cols,
    )

    scored_cols = [
        "채널ID",
        "채널명",
        "대표상위세그먼트",
        "대표하위세그먼트",
        "채널구독자수",
        "최근영상조회수평균",
        "최근영상참여율평균",
        "성장성점수_proxy",
        "성장성신뢰도",
        "성장성신뢰도등급",
        "채널력점수",
        "성장성점수",
        "팬밀도점수",
        "라이브친화점수",
        "실전성점수",
        "최종점수",
        "최종순위",
        "액션버킷",
    ]
    _append_snapshot_overwrite_by_date_and_key(
        latest_path=CANDIDATE_SCORED_FINAL_PATH,
        snapshot_path=CANDIDATE_SCORED_SNAPSHOT_PATH,
        snapshot_cols=scored_cols,
    )

    print("=" * 60)
    print("STEP 10 완료")
    print("=" * 60)


if __name__ == "__main__":
    run()