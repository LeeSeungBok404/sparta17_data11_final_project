import pandas as pd
from config import (
    CANDIDATE_AGG_INPUT_PATH,
    FINAL_CORE_CANDIDATE_DIR,
    MIN_SUBSCRIBERS_FOR_CANDIDATE,
    MIN_VIDEO_SAMPLE_FOR_CANDIDATE,
)

OUTPUT_PREPARED_CANDIDATE_PATH = FINAL_CORE_CANDIDATE_DIR / "candidate_channel_prepared.csv"


def run():
    print("[STEP2] 일반 후보 데이터 준비 시작")

    if not CANDIDATE_AGG_INPUT_PATH.exists():
        raise FileNotFoundError(f"입력 파일 없음: {CANDIDATE_AGG_INPUT_PATH}")

    df = pd.read_csv(CANDIDATE_AGG_INPUT_PATH, encoding="utf-8-sig")
    print("원본 rows:", len(df))

    for col in df.columns:
        if df[col].dtype == "object":
            df[col] = df[col].astype(str).str.strip()
            df.loc[df[col].isin(["", "nan", "None", "NaN"]), col] = pd.NA

    # 한국 채널 추정 필터
    if "한국채널추정여부" in df.columns:
        df = df[df["한국채널추정여부"] == 1].copy()

    # 최소 기준 필터
    if "채널구독자수" in df.columns:
        df["채널구독자수"] = pd.to_numeric(df["채널구독자수"], errors="coerce")
        df = df[df["채널구독자수"].fillna(0) >= MIN_SUBSCRIBERS_FOR_CANDIDATE].copy()

    if "수집영상수" in df.columns:
        df["수집영상수"] = pd.to_numeric(df["수집영상수"], errors="coerce")
        df = df[df["수집영상수"].fillna(0) >= MIN_VIDEO_SAMPLE_FOR_CANDIDATE].copy()

    print("필터 후 rows:", len(df))
    df.to_csv(OUTPUT_PREPARED_CANDIDATE_PATH, index=False, encoding="utf-8-sig")
    print("저장 완료:", OUTPUT_PREPARED_CANDIDATE_PATH)