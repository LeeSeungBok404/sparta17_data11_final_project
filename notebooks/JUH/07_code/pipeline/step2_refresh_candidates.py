import pandas as pd

from config import (
    API_KEYS,
    REQUEST_SLEEP,
    REFRESH_RECENT_VIDEO_TARGET,
    REFRESH_MAX_CHANNELS,
    LEGACY_CIME_FINAL_SHORTLIST_PATH,
    LEGACY_CIME_SIMILARITY_SCORED_PATH,
    CANDIDATE_PREPARED_PATH,
    CANDIDATE_REFRESH_VIDEO_RAW_PATH,
    CANDIDATE_REFRESH_CHANNEL_META_PATH,
    CANDIDATE_REFRESH_AGG_PATH,
    REFRESH_PROGRESS_PATH,
)
from utils.io_utils import (
    load_csv_safe,
    save_csv_safe,
    save_json,
    print_section,
    print_kv,
)
from utils.youtube_api_utils import (
    YouTubeAPIClient,
    safe_int,
    parse_duration_to_sec,
)


# =====================================================
# Refresh 실행 모드
# =====================================================
# True  : REFRESH_MAX_CHANNELS=300 배치 제한을 사용하지 않고 전체 후보 채널을 한 번에 refresh
# False : 기존처럼 REFRESH_MAX_CHANNELS 단위 순환 배치 refresh
REFRESH_ALL_CHANNELS_ONCE = True

# playlistItems 조회 실패 채널 로그 저장 경로
REFRESH_FAIL_LOG_PATH = CANDIDATE_REFRESH_VIDEO_RAW_PATH.parent / "candidate_refresh_fail_log.csv"


def _collect_all_target_channels():
    channel_ids = set()

    for path, col in [
        (LEGACY_CIME_FINAL_SHORTLIST_PATH, "채널ID"),
        (LEGACY_CIME_SIMILARITY_SCORED_PATH, "채널ID"),
        (CANDIDATE_PREPARED_PATH, "채널ID"),
    ]:
        if path.exists():
            df = pd.read_csv(path, encoding="utf-8-sig")
            if col in df.columns:
                vals = df[col].dropna().astype(str).str.strip().unique().tolist()
                channel_ids.update(vals)

    return sorted(channel_ids)


def _load_refresh_progress():
    progress = load_csv_safe(REFRESH_PROGRESS_PATH)
    if progress is None or len(progress) == 0:
        return {
            "refresh_batch_cursor": 0,
            "last_run": None,
            "refresh_channel_count": 0,
            "quota_used_total": 0,
            "exhausted_api_keys": [],
        }

    row = progress.iloc[0].to_dict()
    row.setdefault("refresh_batch_cursor", 0)
    row.setdefault("last_run", None)
    row.setdefault("refresh_channel_count", 0)
    row.setdefault("quota_used_total", 0)
    row.setdefault("exhausted_api_keys", [])
    return row


def _load_refresh_progress_json():
    try:
        import json
        if REFRESH_PROGRESS_PATH.exists():
            with open(REFRESH_PROGRESS_PATH, "r", encoding="utf-8") as f:
                row = json.load(f)
            row.setdefault("refresh_batch_cursor", 0)
            row.setdefault("last_run", None)
            row.setdefault("refresh_channel_count", 0)
            row.setdefault("quota_used_total", 0)
            row.setdefault("exhausted_api_keys", [])
            return row
    except Exception:
        pass

    return {
        "refresh_batch_cursor": 0,
        "last_run": None,
        "refresh_channel_count": 0,
        "quota_used_total": 0,
        "exhausted_api_keys": [],
    }


def _get_rotation_batch(channel_ids, batch_size, cursor):
    total = len(channel_ids)
    if total == 0:
        return [], 0, 0

    start = int(cursor) % total
    end = start + int(batch_size)

    if end <= total:
        batch = channel_ids[start:end]
    else:
        batch = channel_ids[start:] + channel_ids[: end - total]

    next_cursor = end % total
    return batch, start, next_cursor


def _fallback_uploads_playlist_id(channel_id: str):
    if isinstance(channel_id, str) and channel_id.startswith("UC"):
        return "UU" + channel_id[2:]
    return None


def _save_refresh_progress(
    *,
    target_channel_count,
    total_candidates,
    batch_start,
    next_cursor,
    refresh_batch_size,
    yt,
):
    save_json(
        REFRESH_PROGRESS_PATH,
        {
            "last_run": pd.Timestamp.now(tz="Asia/Seoul").isoformat(),
            "refresh_channel_count": int(target_channel_count),
            "refresh_total_candidates": int(total_candidates),
            "refresh_batch_cursor": int(next_cursor),
            "refresh_batch_start": int(batch_start),
            "refresh_batch_size": int(refresh_batch_size),
            "refresh_all_channels_once": bool(REFRESH_ALL_CHANNELS_ONCE),
            "quota_used_total": int(getattr(yt, "quota_used_total", 0)),
            "exhausted_api_keys": getattr(yt, "exhausted_api_keys", []),
        },
    )


def run():
    if REFRESH_ALL_CHANNELS_ONCE:
        print_section("STEP2 - 후보 채널 Refresh (전체 후보 일괄 실행)")
    else:
        print_section("STEP2 - 후보 채널 Refresh (전체 후보 순환 배치형)")

    all_target_channel_ids = _collect_all_target_channels()
    if not all_target_channel_ids:
        print("refresh 대상 채널이 없습니다.")
        return

    total_candidates = len(all_target_channel_ids)
    print_kv("refresh 전체 후보 채널 수", total_candidates)
    print_kv("refresh_all_channels_once", REFRESH_ALL_CHANNELS_ONCE)

    progress = _load_refresh_progress_json()

    if REFRESH_ALL_CHANNELS_ONCE:
        # REFRESH_MAX_CHANNELS=300 제한을 사용하지 않고 전체 후보를 한 번에 refresh한다.
        # 단, YouTube channels.list API는 한 번에 50개까지만 조회 가능하므로 50개씩 나누어 호출한다.
        target_channel_ids = all_target_channel_ids
        batch_start = 0
        next_cursor = 0
        refresh_batch_size = len(target_channel_ids)
    else:
        current_cursor = int(progress.get("refresh_batch_cursor", 0))
        target_channel_ids, batch_start, next_cursor = _get_rotation_batch(
            channel_ids=all_target_channel_ids,
            batch_size=REFRESH_MAX_CHANNELS,
            cursor=current_cursor,
        )
        refresh_batch_size = REFRESH_MAX_CHANNELS

    print_kv("이번 refresh 배치 시작 cursor", batch_start)
    print_kv("이번 refresh 대상 채널 수", len(target_channel_ids))
    print_kv("다음 refresh cursor", next_cursor)
    print_kv("refresh_batch_size", refresh_batch_size)

    yt = YouTubeAPIClient(api_keys=API_KEYS, request_sleep=REQUEST_SLEEP)

    # -----------------------------------------------------
    # 1) channels.list 로 채널 메타 수집
    # -----------------------------------------------------
    channel_rows = []

    for i in range(0, len(target_channel_ids), 50):
        batch_ids = target_channel_ids[i:i + 50]
        resp = yt.get_channels_info(batch_ids)
        item_map = {item["id"]: item for item in resp.get("items", [])}

        for ch_id in batch_ids:
            item = item_map.get(ch_id)
            meta_found = item is not None

            if meta_found:
                snippet = item.get("snippet", {})
                stats = item.get("statistics", {})
                content = item.get("contentDetails", {})
                related = content.get("relatedPlaylists", {}) if isinstance(content, dict) else {}

                uploads_playlist_id = related.get("uploads")
                if not uploads_playlist_id:
                    uploads_playlist_id = _fallback_uploads_playlist_id(ch_id)
            else:
                # channels.list에서 조회되지 않는 삭제/비공개/오류 채널은 playlist fallback을 만들지 않는다.
                # fallback으로 UU...를 만들면 playlistItems에서 404가 반복될 수 있다.
                snippet = {}
                stats = {}
                uploads_playlist_id = None

            channel_rows.append({
                "채널ID": ch_id,
                "채널메타조회성공여부": int(meta_found),
                "채널명_최신": snippet.get("title"),
                "채널설명_최신": snippet.get("description"),
                "채널개설일_최신": snippet.get("publishedAt"),
                "채널국가_최신": snippet.get("country"),
                "채널구독자수_최신": safe_int(stats.get("subscriberCount")),
                "채널총조회수_최신": safe_int(stats.get("viewCount")),
                "채널총영상수_최신": safe_int(stats.get("videoCount")),
                "업로드플레이리스트ID": uploads_playlist_id,
            })

        print(
            f"[refresh channels] "
            f"{min(i + 50, len(target_channel_ids))}/{len(target_channel_ids)} "
            f"| quota={yt.quota_used_total}"
        )

    channel_meta_df = pd.DataFrame(channel_rows)
    save_csv_safe(channel_meta_df, CANDIDATE_REFRESH_CHANNEL_META_PATH)

    # -----------------------------------------------------
    # 2) 최근 영상 수집
    # -----------------------------------------------------
    video_rows = []
    fail_rows = []

    for idx, row in channel_meta_df.iterrows():
        ch_id = row["채널ID"]
        playlist_id = row.get("업로드플레이리스트ID")

        if pd.isna(playlist_id) or not playlist_id:
            fail_rows.append({
                "채널ID": ch_id,
                "업로드플레이리스트ID": playlist_id,
                "fail_stage": "playlist_missing",
                "error": "uploads playlist id missing",
            })
            continue

        try:
            candidate_video_ids = []
            page_token = None
            page_count = 0

            while page_count < 5 and len(candidate_video_ids) < REFRESH_RECENT_VIDEO_TARGET * 3:
                pl_resp = yt.get_playlist_items(playlist_id, page_token=page_token)
                items = pl_resp.get("items", [])
                if not items:
                    break

                page_count += 1
                for item in items:
                    content = item.get("contentDetails", {})
                    vid = content.get("videoId")
                    if vid:
                        candidate_video_ids.append(vid)

                page_token = pl_resp.get("nextPageToken")
                if not page_token:
                    break

            candidate_video_ids = list(dict.fromkeys(candidate_video_ids))
            if not candidate_video_ids:
                fail_rows.append({
                    "채널ID": ch_id,
                    "업로드플레이리스트ID": playlist_id,
                    "fail_stage": "video_id_empty",
                    "error": "no candidate video ids",
                })
                continue

            detail_resp = yt.get_video_details(candidate_video_ids)
            detail_rows = []

            for item in detail_resp.get("items", []):
                snippet = item.get("snippet", {})
                stats = item.get("statistics", {})
                live = item.get("liveStreamingDetails", {})
                duration_raw = item.get("contentDetails", {}).get("duration")
                duration_sec = parse_duration_to_sec(duration_raw)

                detail_rows.append({
                    "채널ID": ch_id,
                    "video_id": item.get("id"),
                    "title": snippet.get("title"),
                    "published_at": snippet.get("publishedAt"),
                    "view_count": safe_int(stats.get("viewCount")),
                    "like_count": safe_int(stats.get("likeCount")),
                    "comment_count": safe_int(stats.get("commentCount")),
                    "duration": duration_raw,
                    "duration_sec": duration_sec,
                    "has_live_actual_start": int("actualStartTime" in live),
                })

            if detail_rows:
                tmp = pd.DataFrame(detail_rows)
                tmp["published_at"] = pd.to_datetime(tmp["published_at"], errors="coerce", utc=True)
                tmp = tmp.sort_values("published_at", ascending=False).head(REFRESH_RECENT_VIDEO_TARGET).copy()
                tmp["engagement_per_view"] = (
                    (tmp["like_count"].fillna(0) + tmp["comment_count"].fillna(0))
                    / tmp["view_count"].replace(0, pd.NA)
                )
                video_rows.extend(tmp.to_dict("records"))
            else:
                fail_rows.append({
                    "채널ID": ch_id,
                    "업로드플레이리스트ID": playlist_id,
                    "fail_stage": "video_detail_empty",
                    "error": "video detail response empty",
                })

            print(
                f"[refresh videos] {idx + 1}/{len(channel_meta_df)} "
                f"| channel_id={ch_id} | quota={yt.quota_used_total}"
            )

        except Exception as e:
            fail_rows.append({
                "채널ID": ch_id,
                "업로드플레이리스트ID": playlist_id,
                "fail_stage": "exception",
                "error": str(e),
            })
            print(f"[refresh fail] channel_id={ch_id} | err={e}")
            continue

    refresh_video_df = pd.DataFrame(video_rows)
    save_csv_safe(refresh_video_df, CANDIDATE_REFRESH_VIDEO_RAW_PATH)

    if fail_rows:
        fail_df = pd.DataFrame(fail_rows)
        save_csv_safe(fail_df, REFRESH_FAIL_LOG_PATH)
        print(f"refresh fail log 저장: {REFRESH_FAIL_LOG_PATH} | rows={len(fail_df)}")

    # -----------------------------------------------------
    # 3) 채널 단위 최신 집계
    # -----------------------------------------------------
    if len(refresh_video_df) > 0:
        refresh_agg = (
            refresh_video_df.groupby("채널ID")
            .agg(
                최근수집영상수_최신=("video_id", "count"),
                최근영상조회수평균_최신=("view_count", "mean"),
                최근영상좋아요평균_최신=("like_count", "mean"),
                최근영상댓글수평균_최신=("comment_count", "mean"),
                최근영상참여율평균_최신=("engagement_per_view", "mean"),
                최근영상실제라이브시작비율_최신=("has_live_actual_start", "mean"),
                최근영상길이초평균_최신=("duration_sec", "mean"),
                최근최신업로드일_최신=("published_at", "max"),
            )
            .reset_index()
        )
    else:
        refresh_agg = pd.DataFrame(columns=["채널ID"])

    refresh_final = channel_meta_df.merge(refresh_agg, on="채널ID", how="left")
    save_csv_safe(refresh_final, CANDIDATE_REFRESH_AGG_PATH)

    # -----------------------------------------------------
    # 4) progress 저장
    # -----------------------------------------------------
    _save_refresh_progress(
        target_channel_count=len(target_channel_ids),
        total_candidates=total_candidates,
        batch_start=batch_start,
        next_cursor=next_cursor,
        refresh_batch_size=refresh_batch_size,
        yt=yt,
    )

    print("\n===== Refresh 완료 =====")
    print("quota_total:", yt.quota_used_total)
    print("channel_meta:", CANDIDATE_REFRESH_CHANNEL_META_PATH)
    print("refresh_video_raw:", CANDIDATE_REFRESH_VIDEO_RAW_PATH)
    print("refresh_agg:", CANDIDATE_REFRESH_AGG_PATH)
    print("refresh_fail_log:", REFRESH_FAIL_LOG_PATH)


if __name__ == "__main__":
    run()
