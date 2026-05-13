import pandas as pd
import numpy as np

from config import (
    CANDIDATE_REFRESH_VIDEO_MASTER_PATH,
    CANDIDATE_GROWTH_PROXY_PATH,
)


def pct_rank_high_is_good(series):
    """
    값이 클수록 좋은 지표를 0~1 분위 점수로 변환한다.

    주의:
    pandas rank(pct=True, ascending=False)는 큰 값일수록 낮은 pct를 부여한다.
    후보 스코어링에서는 조회수/구독자수/참여율/성장률처럼 큰 값이 좋은 지표가
    높은 점수를 받아야 하므로 ascending=True를 사용한다.

    예: 후보가 100개일 때 가장 큰 값은 1.00에 가까운 점수,
        가장 작은 값은 0.01에 가까운 점수를 받는다.
    """
    s = pd.to_numeric(series, errors="coerce")
    return s.rank(method="average", pct=True, ascending=True)


def pct_rank_desc(series):
    """
    기존 함수명 호환용 alias.
    실제 동작은 '높을수록 좋은 점수' 기준이다.
    """
    return pct_rank_high_is_good(series)


def weighted_mean_ignore_nan(values, weights):
    vals = []
    ws = []
    for k, v in values.items():
        if pd.notna(v):
            vals.append(v)
            ws.append(weights[k])
    if not vals:
        return np.nan
    return np.average(vals, weights=ws)


def growth_rate(curr, prev):
    curr = pd.to_numeric(curr, errors="coerce")
    prev = pd.to_numeric(prev, errors="coerce")
    return np.where((pd.notna(prev)) & (prev != 0), (curr - prev) / prev, np.nan)


def clip01(x):
    return np.clip(x, 0, 1)


def run():
    print("=" * 80)
    print("master raw 기반 성장성 proxy 생성 시작")
    print("=" * 80)

    if not CANDIDATE_REFRESH_VIDEO_MASTER_PATH.exists():
        raise FileNotFoundError(f"master raw 파일 없음: {CANDIDATE_REFRESH_VIDEO_MASTER_PATH}")

    df = pd.read_csv(CANDIDATE_REFRESH_VIDEO_MASTER_PATH, encoding="utf-8-sig")
    print("master raw shape:", df.shape)

    required_cols = ["채널ID", "video_id", "published_at", "view_count", "like_count", "comment_count", "has_live_actual_start"]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"master raw에 필요한 컬럼 없음: {missing}")

    # -----------------------------------------------------
    # 기본 전처리
    # -----------------------------------------------------
    df = df.copy()
    df["채널ID"] = df["채널ID"].astype(str).str.strip()
    df["video_id"] = df["video_id"].astype(str).str.strip()
    df["published_at"] = pd.to_datetime(df["published_at"], errors="coerce", utc=True).dt.tz_localize(None)

    for c in ["view_count", "like_count", "comment_count", "has_live_actual_start"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    df = df[df["published_at"].notna()].copy()

    df["engagement_rate"] = np.where(
        (df["view_count"].notna()) & (df["view_count"] != 0),
        (df["like_count"].fillna(0) + df["comment_count"].fillna(0)) / df["view_count"],
        np.nan
    )

    # -----------------------------------------------------
    # 기준일 및 주차 윈도우
    # week1 = 7~13일 전
    # week2 = 14~20일 전
    # week3 = 21~27일 전
    # week4 = 28~34일 전
    # -----------------------------------------------------
    anchor_date = df["published_at"].max().normalize()
    print("anchor_date:", anchor_date.date())

    windows = {
        "week1": (anchor_date - pd.Timedelta(days=13), anchor_date - pd.Timedelta(days=7)),
        "week2": (anchor_date - pd.Timedelta(days=20), anchor_date - pd.Timedelta(days=14)),
        "week3": (anchor_date - pd.Timedelta(days=27), anchor_date - pd.Timedelta(days=21)),
        "week4": (anchor_date - pd.Timedelta(days=34), anchor_date - pd.Timedelta(days=28)),
    }

    for name, (s, e) in windows.items():
        print(f"{name}: {s.date()} ~ {e.date()}")

    # -----------------------------------------------------
    # 주차 라벨링
    # -----------------------------------------------------
    df["week_bucket"] = None
    for name, (s, e) in windows.items():
        mask = (df["published_at"] >= s) & (df["published_at"] <= e)
        df.loc[mask, "week_bucket"] = name

    df_4w = df[df["week_bucket"].notna()].copy()
    print("4-week window rows:", len(df_4w))
    print("4-week unique channels:", df_4w["채널ID"].nunique())

    # -----------------------------------------------------
    # 주차별 채널 집계
    # -----------------------------------------------------
    weekly = (
        df_4w.groupby(["채널ID", "week_bucket"], dropna=False)
        .agg(
            업로드수=("video_id", "count"),
            평균조회수=("view_count", "mean"),
            평균참여율=("engagement_rate", "mean"),
            라이브비율=("has_live_actual_start", "mean"),
        )
        .reset_index()
    )

    pivot = weekly.pivot(index="채널ID", columns="week_bucket")
    pivot.columns = [f"{metric}_{week}" for metric, week in pivot.columns]
    pivot = pivot.reset_index()

    all_channels = pd.DataFrame({"채널ID": sorted(df["채널ID"].dropna().unique())})
    out = all_channels.merge(pivot, on="채널ID", how="left")

    def get_col(name):
        return out[name] if name in out.columns else np.nan

    out["최근2주_업로드수"] = (
        pd.to_numeric(get_col("업로드수_week1"), errors="coerce").fillna(0)
        + pd.to_numeric(get_col("업로드수_week2"), errors="coerce").fillna(0)
    )
    out["이전2주_업로드수"] = (
        pd.to_numeric(get_col("업로드수_week3"), errors="coerce").fillna(0)
        + pd.to_numeric(get_col("업로드수_week4"), errors="coerce").fillna(0)
    )

    out["최근2주_평균조회수"] = pd.concat(
        [
            pd.to_numeric(get_col("평균조회수_week1"), errors="coerce"),
            pd.to_numeric(get_col("평균조회수_week2"), errors="coerce"),
        ],
        axis=1,
    ).mean(axis=1)

    out["이전2주_평균조회수"] = pd.concat(
        [
            pd.to_numeric(get_col("평균조회수_week3"), errors="coerce"),
            pd.to_numeric(get_col("평균조회수_week4"), errors="coerce"),
        ],
        axis=1,
    ).mean(axis=1)

    out["최근2주_평균참여율"] = pd.concat(
        [
            pd.to_numeric(get_col("평균참여율_week1"), errors="coerce"),
            pd.to_numeric(get_col("평균참여율_week2"), errors="coerce"),
        ],
        axis=1,
    ).mean(axis=1)

    out["이전2주_평균참여율"] = pd.concat(
        [
            pd.to_numeric(get_col("평균참여율_week3"), errors="coerce"),
            pd.to_numeric(get_col("평균참여율_week4"), errors="coerce"),
        ],
        axis=1,
    ).mean(axis=1)

    out["최근2주_라이브비율"] = pd.concat(
        [
            pd.to_numeric(get_col("라이브비율_week1"), errors="coerce"),
            pd.to_numeric(get_col("라이브비율_week2"), errors="coerce"),
        ],
        axis=1,
    ).mean(axis=1)

    out["이전2주_라이브비율"] = pd.concat(
        [
            pd.to_numeric(get_col("라이브비율_week3"), errors="coerce"),
            pd.to_numeric(get_col("라이브비율_week4"), errors="coerce"),
        ],
        axis=1,
    ).mean(axis=1)

    out["최근2주_조회수성장률"] = growth_rate(out["최근2주_평균조회수"], out["이전2주_평균조회수"])
    out["최근2주_참여율성장률"] = growth_rate(out["최근2주_평균참여율"], out["이전2주_평균참여율"])
    out["최근2주_업로드성장률"] = growth_rate(out["최근2주_업로드수"], out["이전2주_업로드수"])
    out["최근2주_라이브비율차이"] = (
        pd.to_numeric(out["최근2주_라이브비율"], errors="coerce")
        - pd.to_numeric(out["이전2주_라이브비율"], errors="coerce")
    )

    out["성장성_조회수pct"] = pct_rank_desc(out["최근2주_조회수성장률"])
    out["성장성_참여율pct"] = pct_rank_desc(out["최근2주_참여율성장률"])
    out["성장성_업로드pct"] = pct_rank_desc(out["최근2주_업로드성장률"])
    out["성장성_라이브pct"] = pct_rank_desc(out["최근2주_라이브비율차이"])

    out["성장성점수_proxy_raw"] = out.apply(
        lambda row: weighted_mean_ignore_nan(
            {
                "조회수": row["성장성_조회수pct"],
                "참여율": row["성장성_참여율pct"],
                "업로드": row["성장성_업로드pct"],
                "라이브": row["성장성_라이브pct"],
            },
            {
                "조회수": 0.35,
                "참여율": 0.30,
                "업로드": 0.20,
                "라이브": 0.15,
            },
        ),
        axis=1,
    )

    week_upload_cols = [c for c in ["업로드수_week1", "업로드수_week2", "업로드수_week3", "업로드수_week4"] if c in out.columns]
    if week_upload_cols:
        out["성장성수집영상수_4주"] = out[week_upload_cols].apply(pd.to_numeric, errors="coerce").fillna(0).sum(axis=1)
    else:
        out["성장성수집영상수_4주"] = 0

    out["성장성신뢰도"] = clip01(out["성장성수집영상수_4주"] / 8)

    out["성장성점수_proxy"] = (
        out["성장성신뢰도"] * out["성장성점수_proxy_raw"]
        + (1 - out["성장성신뢰도"]) * 0.5
    )
    out["성장성점수_proxy"] = out["성장성점수_proxy"].fillna(0.5)

    def conf_grade(row):
        if row["성장성수집영상수_4주"] == 0:
            return "미산출"
        elif row["성장성신뢰도"] >= 0.8:
            return "높음"
        elif row["성장성신뢰도"] >= 0.4:
            return "보통"
        else:
            return "낮음"

    out["성장성신뢰도등급"] = out.apply(conf_grade, axis=1)

    # -----------------------------------------------------
    # 분위 점수 방향성 sanity check
    # -----------------------------------------------------
    sanity_pairs = [
        ("최근2주_조회수성장률", "성장성_조회수pct"),
        ("최근2주_참여율성장률", "성장성_참여율pct"),
        ("최근2주_업로드성장률", "성장성_업로드pct"),
        ("최근2주_라이브비율차이", "성장성_라이브pct"),
    ]
    for value_col, score_col in sanity_pairs:
        if value_col in out.columns and score_col in out.columns:
            tmp = out[[value_col, score_col]].copy()
            tmp[value_col] = pd.to_numeric(tmp[value_col], errors="coerce")
            tmp[score_col] = pd.to_numeric(tmp[score_col], errors="coerce")
            tmp = tmp.dropna()
            if not tmp.empty:
                high_row = tmp.sort_values(value_col, ascending=False).head(1).iloc[0]
                low_row = tmp.sort_values(value_col, ascending=True).head(1).iloc[0]
                print(
                    f"[rank sanity] {value_col} -> {score_col} | "
                    f"max_value={high_row[value_col]:.4f}, max_score={high_row[score_col]:.4f} | "
                    f"min_value={low_row[value_col]:.4f}, min_score={low_row[score_col]:.4f}"
                )

    out.to_csv(CANDIDATE_GROWTH_PROXY_PATH, index=False, encoding="utf-8-sig")

    print("saved:", CANDIDATE_GROWTH_PROXY_PATH)
    print("\n[non-null check]")
    print("성장성점수_proxy ->", int(out["성장성점수_proxy"].notna().sum()))
    print(out["성장성신뢰도등급"].value_counts(dropna=False))

    show_cols = [c for c in [
        "채널ID",
        "최근2주_업로드수",
        "이전2주_업로드수",
        "최근2주_조회수성장률",
        "최근2주_참여율성장률",
        "최근2주_업로드성장률",
        "최근2주_라이브비율차이",
        "성장성수집영상수_4주",
        "성장성신뢰도",
        "성장성신뢰도등급",
        "성장성점수_proxy",
    ] if c in out.columns]

    print("\n[sample rows]")
    print(out[show_cols].head(20).to_string(index=False))

    print("=" * 80)
    print("master raw 기반 성장성 proxy 생성 완료")
    print("=" * 80)


if __name__ == "__main__":
    run()