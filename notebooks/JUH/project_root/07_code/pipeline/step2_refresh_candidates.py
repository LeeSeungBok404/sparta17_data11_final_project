import pandas as pd

from config import (
    API_KEYS,
    REQUEST_SLEEP,
    REFRESH_RECENT_VIDEO_TARGET,
    REFRESH_MAX_CHANNELS,
    CIME_FINAL_SHORTLIST_PATH,
    CIME_SIMILARITY_SCORED_PATH,
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


def _collect_target_channels():
    channel_ids = set()

    for path, col in [
        (CIME_FINAL_SHORTLIST_PATH, "채널ID"),
        (CIME_SIMILARITY_SCORED_PATH, "채널ID"),
        (CANDIDATE_PREPARED_PATH, "채널ID"),
    ]:
        if path.exists():
            df = pd.read_csv(path, encoding="utf-8-sig")
            if col in df.columns:
                vals = df[col].dropna().astype(str).unique().tolist()
                channel_ids.update(vals)

    return list(channel_ids)[:REFRESH_MAX_CHANNELS]


def _fallback_uploads_playlist_id(channel_id: str):
    if isinstance(channel_id, str) and channel_id.startswith("UC"):
        return "UU" + channel_id[2:]
    return None


def run():
    print_section("STEP2 - 후보 채널 Refresh")

    target_channel_ids = _collect_target_channels()
    if not target_channel_ids:
        print("refresh 대상 채널이 없습니다.")
        return

    print_kv("refresh 대상 채널 수", len(target_channel_ids))

    yt = YouTubeAPIClient(api_keys=API_KEYS, request_sleep=REQUEST_SLEEP)

    # -----------------------------------------------------
    # 1) channels.list 로 채널 메타 수집
    # -----------------------------------------------------
    channel_rows = []

    for i in range(0, len(target_channel_ids), 50):
        batch_ids = target_channel_ids[i:i+50]
        resp = yt.get_channels_info(batch_ids)
        item_map = {item["id"]: item for item in resp.get("items", [])}

        for ch_id in batch_ids:
            item = item_map.get(ch_id, {})
            snippet = item.get("snippet", {})
            stats = item.get("statistics", {})
            content = item.get("contentDetails", {})
            related = content.get("relatedPlaylists", {}) if isinstance(content, dict) else {}

            uploads_playlist_id = related.get("uploads")
            if not uploads_playlist_id:
                uploads_playlist_id = _fallback_uploads_playlist_id(ch_id)

            channel_rows.append({
                "채널ID": ch_id,
                "채널명_최신": snippet.get("title"),
                "채널설명_최신": snippet.get("description"),
                "채널개설일_최신": snippet.get("publishedAt"),
                "채널국가_최신": snippet.get("country"),
                "채널구독자수_최신": safe_int(stats.get("subscriberCount")),
                "채널총조회수_최신": safe_int(stats.get("viewCount")),
                "채널총영상수_최신": safe_int(stats.get("videoCount")),
                "업로드플레이리스트ID": uploads_playlist_id,
            })

        print(f"[refresh channels] {min(i+50, len(target_channel_ids))}/{len(target_channel_ids)} | quota={yt.quota_used_total}")

    channel_meta_df = pd.DataFrame(channel_rows)
    save_csv_safe(channel_meta_df, CANDIDATE_REFRESH_CHANNEL_META_PATH)

    # -----------------------------------------------------
    # 2) 최근 영상 수집
    # -----------------------------------------------------
    video_rows = []

    for idx, row in channel_meta_df.iterrows():
        ch_id = row["채널ID"]
        playlist_id = row.get("업로드플레이리스트ID")

        if pd.isna(playlist_id) or not playlist_id:
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
                    video_id = item.get("contentDetails", {}).get("videoId")
                    if video_id:
                        candidate_video_ids.append(str(video_id))

                page_token = pl_resp.get("nextPageToken")
                if not page_token:
                    break

            candidate_video_ids = list(dict.fromkeys(candidate_video_ids))
            if not candidate_video_ids:
                continue

            detail_rows = []
            for i in range(0, len(candidate_video_ids), 50):
                batch_vids = candidate_video_ids[i:i+50]
                detail_resp = yt.get_video_details(batch_vids)

                for v in detail_resp.get("items", []):
                    snippet = v.get("snippet", {})
                    stats = v.get("statistics", {})
                    content = v.get("contentDetails", {})
                    live = v.get("liveStreamingDetails", {})

                    duration_raw = content.get("duration")
                    duration_sec = parse_duration_to_sec(duration_raw)

                    detail_rows.append({
                        "채널ID": ch_id,
                        "video_id": v.get("id"),
                        "title": snippet.get("title"),
                        "description": snippet.get("description"),
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

            print(f"[refresh videos] {idx+1}/{len(channel_meta_df)} | channel_id={ch_id} | quota={yt.quota_used_total}")

        except Exception as e:
            print(f"[refresh fail] channel_id={ch_id} | err={e}")
            continue

    refresh_video_df = pd.DataFrame(video_rows)
    save_csv_safe(refresh_video_df, CANDIDATE_REFRESH_VIDEO_RAW_PATH)

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

    save_json(
        REFRESH_PROGRESS_PATH,
        {
            "last_run": pd.Timestamp.now(tz="Asia/Seoul").isoformat(),
            "refresh_channel_count": len(target_channel_ids),
            "quota_used_total": yt.quota_used_total,
            "exhausted_api_keys": yt.exhausted_api_keys,
        },
    )

    print("\n===== Refresh 완료 =====")
    print("quota_total:", yt.quota_used_total)
    print("channel_meta:", CANDIDATE_REFRESH_CHANNEL_META_PATH)
    print("refresh_video_raw:", CANDIDATE_REFRESH_VIDEO_RAW_PATH)
    print("refresh_agg:", CANDIDATE_REFRESH_AGG_PATH)


if __name__ == "__main__":
    run()