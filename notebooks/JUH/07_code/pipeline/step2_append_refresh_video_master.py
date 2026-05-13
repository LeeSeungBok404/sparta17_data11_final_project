import pandas as pd
from pathlib import Path

from config import (
    RAW_CANDIDATE_DIR,
    CANDIDATE_REFRESH_VIDEO_RAW_PATH,
    CANDIDATE_REFRESH_VIDEO_MASTER_PATH,
)


def _read_csv_flexible(path: Path) -> pd.DataFrame:
    for enc in ["utf-8-sig", "utf-8", "cp949", "euc-kr"]:
        try:
            return pd.read_csv(path, encoding=enc)
        except Exception:
            continue
    raise ValueError(f"CSV 읽기 실패: {path}")


def _normalize_df(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # 문자열 key 정리
    if "채널ID" in df.columns:
        df["채널ID"] = df["채널ID"].astype(str).str.strip()

    if "video_id" in df.columns:
        df["video_id"] = df["video_id"].astype(str).str.strip()

    if "published_at" in df.columns:
        df["published_at"] = pd.to_datetime(df["published_at"], errors="coerce", utc=True).dt.tz_localize(None)

    return df


def run():
    print("[STEP] refresh video raw master append 시작")

    if not CANDIDATE_REFRESH_VIDEO_RAW_PATH.exists():
        raise FileNotFoundError(f"새 refresh raw 파일 없음: {CANDIDATE_REFRESH_VIDEO_RAW_PATH}")

    RAW_CANDIDATE_DIR.mkdir(parents=True, exist_ok=True)

    df_new = _read_csv_flexible(CANDIDATE_REFRESH_VIDEO_RAW_PATH)
    df_new = _normalize_df(df_new)

    print("new raw rows:", len(df_new))

    if CANDIDATE_REFRESH_VIDEO_MASTER_PATH.exists():
        df_old = _read_csv_flexible(CANDIDATE_REFRESH_VIDEO_MASTER_PATH)
        df_old = _normalize_df(df_old)
        print("old master rows:", len(df_old))

        # 컬럼 union 맞추기
        all_cols = sorted(set(df_old.columns) | set(df_new.columns))
        df_old = df_old.reindex(columns=all_cols)
        df_new = df_new.reindex(columns=all_cols)

        df_master = pd.concat([df_old, df_new], ignore_index=True)
    else:
        print("기존 master 없음 -> 새 raw로 master 생성")
        df_master = df_new.copy()

    before_dedup = len(df_master)

    # --------------------------------------------------
    # dedup 우선순위
    # 1) video_id
    # 2) 없으면 보조키(채널ID + published_at + title)
    # --------------------------------------------------
    if "video_id" in df_master.columns:
        df_master = df_master.drop_duplicates(subset=["video_id"], keep="last")
    else:
        backup_keys = [c for c in ["채널ID", "published_at", "title"] if c in df_master.columns]
        if backup_keys:
            df_master = df_master.drop_duplicates(subset=backup_keys, keep="last")

    after_dedup = len(df_master)

    df_master.to_csv(CANDIDATE_REFRESH_VIDEO_MASTER_PATH, index=False, encoding="utf-8-sig")

    print("before dedup:", before_dedup)
    print("after dedup :", after_dedup)
    print("saved master:", CANDIDATE_REFRESH_VIDEO_MASTER_PATH)

    if "채널ID" in df_master.columns:
        print("master unique channels:", df_master["채널ID"].nunique())
    if "video_id" in df_master.columns:
        print("master unique videos:", df_master["video_id"].nunique())


if __name__ == "__main__":
    run()