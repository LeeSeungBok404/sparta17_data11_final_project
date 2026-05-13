# =========================================================
# STEP 10.5 - 채널 프로필 이미지 URL 보강
#
# 목적:
# - dashboard_candidate_table.csv의 channel_id 기준으로
#   YouTube Data API channels.list(part=snippet)를 호출
# - channel_thumbnail_url / channel_url / channel_custom_url 추가
# - 결과를 dashboard_candidate_table.csv에 다시 덮어써서
#   Streamlit 대시보드에서 바로 사용할 수 있게 함
#
# 저장 위치:
#   07_code/pipeline/step6_5_enrich_channel_thumbnails.py
# =========================================================

from pathlib import Path
from datetime import datetime
import json
import time
import random
import traceback
import requests
import pandas as pd

from config import (
    API_KEYS,
    DASHBOARD_CANDIDATE_TABLE_PATH,
    INTERMEDIATE_DIR,
)

# =========================================================
# 설정
# =========================================================

BATCH_SIZE = 50
REQUEST_SLEEP_SEC = 0.15
MAX_RETRY_PER_BATCH = 3
YOUTUBE_CHANNELS_URL = "https://www.googleapis.com/youtube/v3/channels"

OUTPUT_DIR = INTERMEDIATE_DIR / "channel_enrichment"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

THUMBNAIL_MASTER_PATH = OUTPUT_DIR / "channel_thumbnail_master.csv"
CHECKPOINT_PATH = OUTPUT_DIR / "channel_thumbnail_checkpoint.json"
FAILED_PATH = OUTPUT_DIR / "channel_thumbnail_failed.csv"
EXHAUSTED_KEYS_PATH = OUTPUT_DIR / "exhausted_api_keys.json"


# =========================================================
# 유틸
# =========================================================

def read_csv_safely(path: Path) -> pd.DataFrame:
    for enc in ["utf-8-sig", "utf-8", "cp949"]:
        try:
            return pd.read_csv(path, encoding=enc)
        except UnicodeDecodeError:
            continue
    return pd.read_csv(path)


def save_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def load_json(path: Path, default):
    if not path.exists():
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def chunk_list(items, size):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def pick_thumbnail_url(thumbnails: dict) -> str:
    if not isinstance(thumbnails, dict):
        return ""

    return (
        thumbnails.get("high", {}).get("url")
        or thumbnails.get("medium", {}).get("url")
        or thumbnails.get("default", {}).get("url")
        or ""
    )


def normalize_channel_url(channel_id: str) -> str:
    if not channel_id:
        return ""
    return f"https://www.youtube.com/channel/{channel_id}"


def parse_quota_error(resp_json: dict) -> bool:
    try:
        errors = resp_json.get("error", {}).get("errors", [])
        reasons = {e.get("reason") for e in errors}
        message = resp_json.get("error", {}).get("message", "")

        quota_reasons = {
            "quotaExceeded",
            "dailyLimitExceeded",
            "userRateLimitExceeded",
            "rateLimitExceeded",
        }

        return bool(reasons & quota_reasons) or ("quota" in message.lower())
    except Exception:
        return False


def request_channels_list(channel_ids, api_key):
    params = {
        "part": "snippet",
        "id": ",".join(channel_ids),
        "key": api_key,
        "maxResults": 50,
    }

    resp = requests.get(YOUTUBE_CHANNELS_URL, params=params, timeout=20)

    try:
        data = resp.json()
    except Exception:
        data = {"raw_text": resp.text}

    if resp.status_code != 200:
        return False, data

    return True, data


def get_channel_id_col(df: pd.DataFrame) -> str:
    candidates = [
        "channel_id",
        "채널ID",
        "채널아이디",
        "youtube_channel_id",
    ]

    for col in candidates:
        if col in df.columns:
            return col

    raise KeyError(
        "channel_id 컬럼을 찾지 못했습니다. 현재 컬럼 목록:\n"
        + ", ".join(df.columns)
    )


# =========================================================
# main run
# =========================================================

def run():
    print("=" * 80)
    print("STEP 10.5 - 채널 프로필 이미지 URL 보강 시작")
    print("=" * 80)

    if not API_KEYS:
        raise ValueError(
            "config.API_KEYS가 비어 있습니다. PROJECT_ROOT/.env의 YOUTUBE_API_KEYS를 확인하세요."
        )

    input_path = DASHBOARD_CANDIDATE_TABLE_PATH

    if not input_path.exists():
        raise FileNotFoundError(f"대시보드 후보 CSV가 없습니다: {input_path}")

    df = read_csv_safely(input_path)
    channel_id_col = get_channel_id_col(df)

    df[channel_id_col] = df[channel_id_col].astype(str).str.strip()

    channel_ids = (
        df[channel_id_col]
        .replace(["", "nan", "None", "NaN"], pd.NA)
        .dropna()
        .drop_duplicates()
        .tolist()
    )

    print(f"입력 파일: {input_path}")
    print(f"후보 rows: {len(df):,}")
    print(f"unique channel_id: {len(channel_ids):,}")
    print(f"API 키 개수: {len(API_KEYS):,}")

    # 기존 master 로드
    if THUMBNAIL_MASTER_PATH.exists():
        master_df = read_csv_safely(THUMBNAIL_MASTER_PATH)
    else:
        master_df = pd.DataFrame(columns=[
            "channel_id",
            "channel_title_api",
            "channel_description_api",
            "channel_thumbnail_url",
            "channel_custom_url",
            "channel_url",
            "published_at_api",
            "collected_at",
        ])

    done_ids = set()
    if not master_df.empty and "channel_id" in master_df.columns:
        done_ids = set(master_df["channel_id"].astype(str).dropna().unique())

    checkpoint = load_json(CHECKPOINT_PATH, default={
        "done_ids": [],
        "failed_ids": [],
        "quota_used_estimate": 0,
        "last_updated": None,
    })

    done_ids |= set(checkpoint.get("done_ids", []))
    failed_ids = set(checkpoint.get("failed_ids", []))
    quota_used_estimate = int(checkpoint.get("quota_used_estimate", 0))

    exhausted_keys = load_json(EXHAUSTED_KEYS_PATH, default={"exhausted_keys": []})
    exhausted_key_set = set(exhausted_keys.get("exhausted_keys", []))

    remaining_ids = [cid for cid in channel_ids if cid not in done_ids]

    print("-" * 80)
    print(f"이미 수집 완료 channel_id: {len(done_ids):,}")
    print(f"수집 대상 remaining channel_id: {len(remaining_ids):,}")
    print(f"이전 quota 사용량 추정치: {quota_used_estimate:,}")
    print(f"소진 처리된 API 키 수: {len(exhausted_key_set):,}")
    print("-" * 80)

    available_keys = [k for k in API_KEYS if k not in exhausted_key_set]

    if not available_keys:
        print("사용 가능한 API 키가 없습니다. 기존 master만 사용해 merge를 진행합니다.")
    else:
        batches = list(chunk_list(remaining_ids, BATCH_SIZE))
        total_batches = len(batches)

        print(f"예상 API 호출 수: {total_batches:,}")
        print(f"예상 추가 quota 사용량: {total_batches:,} units")

        all_new_rows = []
        all_failed_rows = []
        api_key_idx = 0

        for batch_num, batch_ids in enumerate(batches, start=1):
            success = False
            last_error = None

            for retry in range(1, MAX_RETRY_PER_BATCH + 1):
                if not available_keys:
                    print("사용 가능한 API 키가 모두 소진되었습니다. 이후 batch는 생략합니다.")
                    break

                api_key = available_keys[api_key_idx % len(available_keys)]

                try:
                    ok, data = request_channels_list(batch_ids, api_key)
                    quota_used_estimate += 1

                    if not ok:
                        last_error = data

                        if parse_quota_error(data):
                            exhausted_key_set.add(api_key)
                            available_keys = [k for k in available_keys if k != api_key]
                            save_json(EXHAUSTED_KEYS_PATH, {"exhausted_keys": list(exhausted_key_set)})
                            print(
                                f"[{batch_num}/{total_batches}] API 키 quota 소진 감지 → 키 제외 "
                                f"(남은 키 {len(available_keys)}개)"
                            )
                            continue

                        print(
                            f"[{batch_num}/{total_batches}] 요청 실패 "
                            f"retry={retry}/{MAX_RETRY_PER_BATCH} | "
                            f"error={data.get('error', {}).get('message', str(data)[:120])}"
                        )
                        time.sleep(1.5 * retry)
                        continue

                    items = data.get("items", [])
                    returned_ids = set()

                    for item in items:
                        cid = item.get("id", "")
                        snippet = item.get("snippet", {}) or {}
                        thumbnails = snippet.get("thumbnails", {}) or {}

                        returned_ids.add(cid)

                        all_new_rows.append({
                            "channel_id": cid,
                            "channel_title_api": snippet.get("title", ""),
                            "channel_description_api": snippet.get("description", ""),
                            "channel_thumbnail_url": pick_thumbnail_url(thumbnails),
                            "channel_custom_url": snippet.get("customUrl", ""),
                            "channel_url": normalize_channel_url(cid),
                            "published_at_api": snippet.get("publishedAt", ""),
                            "collected_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        })
                        done_ids.add(cid)

                    missing_ids = set(batch_ids) - returned_ids
                    for mid in missing_ids:
                        all_failed_rows.append({
                            "channel_id": mid,
                            "reason": "not_returned_by_channels_list",
                            "failed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        })
                        failed_ids.add(mid)

                    success = True
                    break

                except Exception as e:
                    last_error = str(e)
                    print(f"[{batch_num}/{total_batches}] 예외 발생 retry={retry}/{MAX_RETRY_PER_BATCH}: {e}")
                    traceback.print_exc()
                    time.sleep(1.5 * retry)

            if not success and batch_ids:
                for cid in batch_ids:
                    all_failed_rows.append({
                        "channel_id": cid,
                        "reason": f"request_failed: {str(last_error)[:200]}",
                        "failed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    })
                    failed_ids.add(cid)

            # 주기적 저장
            if batch_num % 10 == 0 or batch_num == total_batches:
                if all_new_rows:
                    new_df = pd.DataFrame(all_new_rows)
                    master_df = pd.concat([master_df, new_df], ignore_index=True)
                    master_df = master_df.drop_duplicates(subset=["channel_id"], keep="last")
                    master_df.to_csv(THUMBNAIL_MASTER_PATH, index=False, encoding="utf-8-sig")
                    all_new_rows = []

                if all_failed_rows:
                    failed_df = pd.DataFrame(all_failed_rows)

                    if FAILED_PATH.exists():
                        old_failed = read_csv_safely(FAILED_PATH)
                        failed_df = pd.concat([old_failed, failed_df], ignore_index=True)

                    failed_df = failed_df.drop_duplicates(subset=["channel_id", "reason"], keep="last")
                    failed_df.to_csv(FAILED_PATH, index=False, encoding="utf-8-sig")
                    all_failed_rows = []

                checkpoint = {
                    "done_ids": sorted(list(done_ids)),
                    "failed_ids": sorted(list(failed_ids)),
                    "quota_used_estimate": quota_used_estimate,
                    "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }

                save_json(CHECKPOINT_PATH, checkpoint)
                save_json(EXHAUSTED_KEYS_PATH, {"exhausted_keys": list(exhausted_key_set)})

                print(
                    f"[checkpoint] batch {batch_num}/{total_batches} | "
                    f"done={len(done_ids):,} | failed={len(failed_ids):,} | "
                    f"quota_used_estimate={quota_used_estimate:,} | "
                    f"available_keys={len(available_keys):,}"
                )

            time.sleep(REQUEST_SLEEP_SEC + random.uniform(0, 0.08))

    # master 다시 로드
    if THUMBNAIL_MASTER_PATH.exists():
        thumbnail_df = read_csv_safely(THUMBNAIL_MASTER_PATH)
    else:
        thumbnail_df = pd.DataFrame(columns=[
            "channel_id",
            "channel_thumbnail_url",
            "channel_url",
            "channel_custom_url",
            "channel_title_api",
        ])

    merge_cols = [
        "channel_id",
        "channel_thumbnail_url",
        "channel_url",
        "channel_custom_url",
        "channel_title_api",
    ]

    available_merge_cols = [c for c in merge_cols if c in thumbnail_df.columns]

    # 기존 보강 컬럼이 있으면 제거 후 최신 master 기준으로 재merge
    drop_cols = [
        "channel_thumbnail_url",
        "channel_url",
        "channel_custom_url",
        "channel_title_api",
        "channel_id_thumb",
    ]

    df_base = df.drop(columns=[c for c in drop_cols if c in df.columns], errors="ignore")

    df_enriched = df_base.merge(
        thumbnail_df[available_merge_cols].drop_duplicates(subset=["channel_id"], keep="last"),
        left_on=channel_id_col,
        right_on="channel_id",
        how="left",
        suffixes=("", "_thumb"),
    )

    if channel_id_col != "channel_id" and "channel_id" in df_enriched.columns:
        df_enriched = df_enriched.drop(columns=["channel_id"])

    # dashboard_candidate_table.csv에 바로 덮어쓰기
    df_enriched.to_csv(input_path, index=False, encoding="utf-8-sig")

    thumb_count = (
        df_enriched["channel_thumbnail_url"].notna().sum()
        if "channel_thumbnail_url" in df_enriched.columns
        else 0
    )

    print("=" * 80)
    print("STEP 10.5 - 채널 프로필 이미지 URL 보강 완료")
    print(f"저장 파일: {input_path}")
    print(f"thumbnail URL 보유 rows: {thumb_count:,} / {len(df_enriched):,}")
    print(f"총 quota 사용량 추정치: {quota_used_estimate:,}")
    print(f"수집 완료 channel_id: {len(done_ids):,}")
    print(f"실패 channel_id: {len(failed_ids):,}")
    print(f"소진 API 키 수: {len(exhausted_key_set):,}")
    print("=" * 80)


if __name__ == "__main__":
    run()