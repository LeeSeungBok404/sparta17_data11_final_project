import pandas as pd
import numpy as np

from config import (
    CANDIDATE_SCORED_FINAL_PATH,
    CANDIDATE_SCORED_SNAPSHOT_PATH,
    FINAL_CORE_OUTPUT_DIR,
)


SHORTLIST_TRACKING_PATH = FINAL_CORE_OUTPUT_DIR / "candidate_shortlist_tracking.csv"


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


def _safe_bool_series(s: pd.Series) -> pd.Series:
    """
    True/False, 1/0, 문자열 true/false/yes/no 등을 bool로 안정 변환.
    """
    if s is None:
        return pd.Series(dtype=bool)

    if s.dtype == bool:
        return s.fillna(False)

    return (
        s.fillna(False)
        .astype(str)
        .str.strip()
        .str.lower()
        .isin(["true", "1", "yes", "y", "t"])
    )


def _get_latest_previous_snapshot(snapshot_df: pd.DataFrame) -> pd.DataFrame:
    """
    scored snapshot에서 가장 최신 회차를 가져온다.
    snapshot_date가 있으면 최신 날짜 기준,
    snapshot_ts_kst가 있으면 최신 timestamp 기준으로 정렬한다.
    """
    if snapshot_df.empty:
        return pd.DataFrame()

    df = snapshot_df.copy()

    if "snapshot_ts_kst" in df.columns:
        df["__snapshot_sort_ts__"] = pd.to_datetime(
            df["snapshot_ts_kst"], errors="coerce"
        )
        latest_ts = df["__snapshot_sort_ts__"].max()
        if pd.notna(latest_ts):
            latest = df[df["__snapshot_sort_ts__"] == latest_ts].copy()
            latest = latest.drop(columns=["__snapshot_sort_ts__"], errors="ignore")
            return latest

    if "snapshot_date" in df.columns:
        df["__snapshot_sort_date__"] = pd.to_datetime(
            df["snapshot_date"], errors="coerce"
        )
        latest_date = df["__snapshot_sort_date__"].max()
        if pd.notna(latest_date):
            latest = df[df["__snapshot_sort_date__"] == latest_date].copy()
            latest = latest.drop(columns=["__snapshot_sort_date__"], errors="ignore")
            return latest

    return df.copy()


def _select_and_prefix(df: pd.DataFrame, key_col: str, prefix: str) -> pd.DataFrame:
    """
    비교에 필요한 컬럼만 남기고 현재_/이전_ prefix를 붙인다.
    key_col은 채널ID로 통일한다.
    """
    if df.empty:
        return pd.DataFrame(columns=["채널ID"])

    use = df.copy()

    if key_col != "채널ID":
        use = use.rename(columns={key_col: "채널ID"})

    keep_cols = [
        "채널ID",
        "채널명",
        "대표상위세그먼트",
        "대표하위세그먼트",
        "최종순위",
        "운영우선순위",
        "최종점수",
        "채널력점수",
        "성장성점수",
        "팬밀도점수",
        "라이브친화점수",
        "실전성점수",
        "액션버킷",
        "shortlist_선정여부",
        "shortlist_유형",
        "추천사유",
        "주의사유",
        "자동판정근거",
    ]

    keep_cols = [c for c in keep_cols if c in use.columns]
    use = use[keep_cols].copy()

    rename_map = {}
    for c in use.columns:
        if c != "채널ID":
            rename_map[c] = f"{prefix}_{c}"

    use = use.rename(columns=rename_map)

    use["채널ID"] = use["채널ID"].astype(str).str.strip()
    use = use.drop_duplicates(subset=["채널ID"], keep="last").reset_index(drop=True)

    return use


def _ensure_tracking_columns(tracking: pd.DataFrame) -> pd.DataFrame:
    """
    구버전 snapshot 호환 처리.

    이전 snapshot이 operational shortlist 적용 전 파일이면
    이전_운영우선순위, 이전_shortlist_선정여부 같은 컬럼이 없을 수 있다.
    이 경우 변화량 계산이 중단되지 않도록 누락 컬럼을 만든다.
    """
    required_cols = [
        "이전_채널명",
        "현재_채널명",
        "이전_대표상위세그먼트",
        "현재_대표상위세그먼트",
        "이전_대표하위세그먼트",
        "현재_대표하위세그먼트",
        "이전_최종순위",
        "현재_최종순위",
        "이전_운영우선순위",
        "현재_운영우선순위",
        "이전_최종점수",
        "현재_최종점수",
        "이전_채널력점수",
        "현재_채널력점수",
        "이전_성장성점수",
        "현재_성장성점수",
        "이전_팬밀도점수",
        "현재_팬밀도점수",
        "이전_라이브친화점수",
        "현재_라이브친화점수",
        "이전_실전성점수",
        "현재_실전성점수",
        "이전_액션버킷",
        "현재_액션버킷",
        "이전_shortlist_선정여부",
        "현재_shortlist_선정여부",
        "이전_shortlist_유형",
        "현재_shortlist_유형",
        "현재_추천사유",
        "현재_주의사유",
        "현재_자동판정근거",
    ]

    for c in required_cols:
        if c not in tracking.columns:
            tracking[c] = np.nan

    return tracking


def _make_change_direction(row):
    if bool(row.get("신규진입여부", False)):
        return "신규진입"

    rank_delta = row.get("순위변동")
    score_delta = row.get("최종점수변동")

    if pd.notna(rank_delta):
        if rank_delta >= 20:
            return "급상승"
        if rank_delta >= 5:
            return "상승"
        if rank_delta <= -20:
            return "급하락"
        if rank_delta <= -5:
            return "하락"

    if pd.notna(score_delta):
        if score_delta >= 0.05:
            return "점수상승"
        if score_delta <= -0.05:
            return "점수하락"

    return "유지"


def _make_change_summary(row):
    parts = []

    if bool(row.get("신규진입여부", False)):
        parts.append("신규 후보 진입")

    rank_delta = row.get("순위변동")
    if pd.notna(rank_delta):
        if rank_delta > 0:
            parts.append(f"순위 {int(rank_delta)}단계 상승")
        elif rank_delta < 0:
            parts.append(f"순위 {abs(int(rank_delta))}단계 하락")

    score_delta = row.get("최종점수변동")
    if pd.notna(score_delta):
        if score_delta > 0:
            parts.append(f"최종점수 +{score_delta:.3f}")
        elif score_delta < 0:
            parts.append(f"최종점수 {score_delta:.3f}")

    growth_delta = row.get("성장성점수변동")
    if pd.notna(growth_delta):
        if growth_delta > 0:
            parts.append(f"성장성 +{growth_delta:.3f}")
        elif growth_delta < 0:
            parts.append(f"성장성 {growth_delta:.3f}")

    if bool(row.get("액션버킷변동여부", False)):
        prev_bucket = row.get("이전_액션버킷")
        curr_bucket = row.get("현재_액션버킷")
        if pd.notna(prev_bucket) and pd.notna(curr_bucket):
            parts.append(f"버킷 변경: {prev_bucket} → {curr_bucket}")

    if bool(row.get("shortlist_신규선정여부", False)):
        parts.append("shortlist 신규 선정")

    if bool(row.get("shortlist_이탈여부", False)):
        parts.append("shortlist 이탈")

    if not parts:
        return "주요 변동 없음"

    return " / ".join(parts)


def run():
    print("[STEP5] shortlist 변화 추적 생성 시작")

    current = _read_csv_if_exists(CANDIDATE_SCORED_FINAL_PATH)
    if current.empty:
        raise FileNotFoundError(
            f"candidate_scored_final.csv 없음 또는 비어있음: {CANDIDATE_SCORED_FINAL_PATH}"
        )

    snapshot = _read_csv_if_exists(CANDIDATE_SCORED_SNAPSHOT_PATH)

    print("current scored rows:", len(current))
    print("snapshot rows:", len(snapshot))

    current_key = _first_existing(current, ["채널ID", "channel_id", "유튜브채널ID"])
    if current_key is None:
        raise ValueError("current scored에서 채널 식별 컬럼을 찾지 못했습니다.")

    current_pref = _select_and_prefix(current, current_key, "현재")

    if snapshot.empty:
        print("[INFO] 기존 scored snapshot이 없어 전체 current를 신규진입으로 처리합니다.")
        previous_pref = pd.DataFrame(columns=["채널ID"])
    else:
        previous = _get_latest_previous_snapshot(snapshot)
        previous_key = _first_existing(previous, ["채널ID", "channel_id", "유튜브채널ID"])

        if previous_key is None:
            print("[WARN] snapshot에서 채널 식별 컬럼을 찾지 못했습니다. 전체 current를 신규진입으로 처리합니다.")
            previous_pref = pd.DataFrame(columns=["채널ID"])
        else:
            previous_pref = _select_and_prefix(previous, previous_key, "이전")

    tracking = current_pref.merge(previous_pref, on="채널ID", how="left")
    tracking = _ensure_tracking_columns(tracking)

    # -----------------------------------------------------
    # 숫자형 보정
    # -----------------------------------------------------
    numeric_cols = [
        "이전_최종순위",
        "현재_최종순위",
        "이전_운영우선순위",
        "현재_운영우선순위",
        "이전_최종점수",
        "현재_최종점수",
        "이전_채널력점수",
        "현재_채널력점수",
        "이전_성장성점수",
        "현재_성장성점수",
        "이전_팬밀도점수",
        "현재_팬밀도점수",
        "이전_라이브친화점수",
        "현재_라이브친화점수",
        "이전_실전성점수",
        "현재_실전성점수",
    ]
    _safe_numeric(tracking, numeric_cols)

    # -----------------------------------------------------
    # 변화량 계산
    # 순위변동은 양수 = 상승, 음수 = 하락
    # 예: 이전 30위, 현재 10위 → 30 - 10 = +20
    # -----------------------------------------------------
    tracking["순위변동"] = tracking["이전_최종순위"] - tracking["현재_최종순위"]
    tracking["운영우선순위변동"] = tracking["이전_운영우선순위"] - tracking["현재_운영우선순위"]

    tracking["최종점수변동"] = tracking["현재_최종점수"] - tracking["이전_최종점수"]
    tracking["채널력점수변동"] = tracking["현재_채널력점수"] - tracking["이전_채널력점수"]
    tracking["성장성점수변동"] = tracking["현재_성장성점수"] - tracking["이전_성장성점수"]
    tracking["팬밀도점수변동"] = tracking["현재_팬밀도점수"] - tracking["이전_팬밀도점수"]
    tracking["라이브친화점수변동"] = tracking["현재_라이브친화점수"] - tracking["이전_라이브친화점수"]
    tracking["실전성점수변동"] = tracking["현재_실전성점수"] - tracking["이전_실전성점수"]

    tracking["신규진입여부"] = tracking["이전_최종순위"].isna()

    tracking["액션버킷변동여부"] = (
        tracking["이전_액션버킷"].fillna("미분류").astype(str)
        != tracking["현재_액션버킷"].fillna("미분류").astype(str)
    )

    prev_shortlist = _safe_bool_series(tracking["이전_shortlist_선정여부"])
    curr_shortlist = _safe_bool_series(tracking["현재_shortlist_선정여부"])

    tracking["shortlist_신규선정여부"] = (~prev_shortlist) & curr_shortlist
    tracking["shortlist_유지여부"] = prev_shortlist & curr_shortlist
    tracking["shortlist_이탈여부"] = prev_shortlist & (~curr_shortlist)

    tracking["변동방향"] = tracking.apply(_make_change_direction, axis=1)
    tracking["변화요약"] = tracking.apply(_make_change_summary, axis=1)

    # -----------------------------------------------------
    # dashboard/export에서 쓰기 좋게 현재값 중심 컬럼 추가
    # -----------------------------------------------------
    tracking["채널명"] = tracking["현재_채널명"].combine_first(tracking["이전_채널명"])
    tracking["대표상위세그먼트"] = tracking["현재_대표상위세그먼트"].combine_first(
        tracking["이전_대표상위세그먼트"]
    )
    tracking["대표하위세그먼트"] = tracking["현재_대표하위세그먼트"].combine_first(
        tracking["이전_대표하위세그먼트"]
    )
    tracking["최종순위"] = tracking["현재_최종순위"]
    tracking["운영우선순위"] = tracking["현재_운영우선순위"]
    tracking["최종점수"] = tracking["현재_최종점수"]
    tracking["액션버킷"] = tracking["현재_액션버킷"]
    tracking["shortlist_선정여부"] = curr_shortlist
    tracking["shortlist_유형"] = tracking["현재_shortlist_유형"]
    tracking["추천사유"] = tracking["현재_추천사유"]
    tracking["주의사유"] = tracking["현재_주의사유"]
    tracking["자동판정근거"] = tracking["현재_자동판정근거"]

    # -----------------------------------------------------
    # 정렬
    # -----------------------------------------------------
    if "운영우선순위" in tracking.columns and tracking["운영우선순위"].notna().any():
        tracking = tracking.sort_values(
            ["shortlist_선정여부", "운영우선순위", "최종순위"],
            ascending=[False, True, True],
            na_position="last",
        ).reset_index(drop=True)
    else:
        tracking = tracking.sort_values(
            ["shortlist_선정여부", "최종순위"],
            ascending=[False, True],
            na_position="last",
        ).reset_index(drop=True)

    # -----------------------------------------------------
    # 컬럼 순서 정리
    # -----------------------------------------------------
    front_cols = [
        "채널ID",
        "채널명",
        "대표상위세그먼트",
        "대표하위세그먼트",
        "최종순위",
        "운영우선순위",
        "최종점수",
        "액션버킷",
        "shortlist_선정여부",
        "shortlist_유형",
        "추천사유",
        "주의사유",
        "자동판정근거",
        "이전_최종순위",
        "현재_최종순위",
        "순위변동",
        "이전_운영우선순위",
        "현재_운영우선순위",
        "운영우선순위변동",
        "최종점수변동",
        "채널력점수변동",
        "성장성점수변동",
        "팬밀도점수변동",
        "라이브친화점수변동",
        "실전성점수변동",
        "이전_액션버킷",
        "현재_액션버킷",
        "액션버킷변동여부",
        "이전_shortlist_선정여부",
        "현재_shortlist_선정여부",
        "shortlist_신규선정여부",
        "shortlist_유지여부",
        "shortlist_이탈여부",
        "변동방향",
        "변화요약",
    ]

    front_cols = [c for c in front_cols if c in tracking.columns]
    other_cols = [c for c in tracking.columns if c not in front_cols]
    tracking = tracking[front_cols + other_cols].copy()

    SHORTLIST_TRACKING_PATH.parent.mkdir(parents=True, exist_ok=True)
    tracking.to_csv(SHORTLIST_TRACKING_PATH, index=False, encoding="utf-8-sig")

    print("saved:", SHORTLIST_TRACKING_PATH)
    print("tracking rows:", len(tracking))

    if "변동방향" in tracking.columns:
        print("\n[변동방향 분포]")
        print(tracking["변동방향"].value_counts(dropna=False))

    if "shortlist_선정여부" in tracking.columns:
        print("\n[shortlist 선정 분포]")
        print(tracking["shortlist_선정여부"].value_counts(dropna=False))

    print("[STEP5] shortlist 변화 추적 생성 완료")


if __name__ == "__main__":
    run()