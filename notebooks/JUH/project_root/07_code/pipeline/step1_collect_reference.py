import pandas as pd
from datetime import datetime, timezone

from config import (
    API_KEYS,
    REQUEST_SLEEP,
    RECENT_VIDEO_TARGET,
    MIN_DURATION_SEC,
    MAX_PLAYLIST_PAGES,
    CIME_TOP30_MAPPING_PATH,
    CIME_CHANNEL_INFO_RAW_PATH,
    CIME_RECENT_VIDEO_RAW_PATH,
    CIME_CHANNEL_INFO_PROCESSED_PATH,
    CIME_TOP30_REFERENCE_PROFILE_PATH,
    REFERENCE_COLLECT_PROGRESS_PATH,
)
from utils.io_utils import (
    load_csv_safe,
    save_csv_safe,
    save_json,
    clean_object_columns,
    print_section,
    print_kv,
)
from utils.youtube_api_utils import (
    YouTubeAPIClient,
    safe_int,
    parse_duration_to_sec,
)


def _fallback_uploads_playlist_id(channel_id: str):
    if isinstance(channel_id, str) and channel_id.startswith("UC"):
        return "UU" + channel_id[2:]
    return None


def run():
    print_section("STEP1 - CME 레퍼런스 채널 수집")

    df = load_csv_safe(CIME_TOP30_MAPPING_PATH)
    df = clean_object_columns(df)

    if "본채널여부" in df.columns:
        df = df[df["본채널여부"].fillna("").eq("Y")].copy()

    df = df[df["유튜브채널ID"].notna()].copy()
    df["유튜브채널ID"] = df["유튜브채널ID"].astype(str)

    print_kv("입력 rows", len(df))
    print_kv("유니크 채널 수", df["유튜브채널ID"].nunique())

    yt = YouTubeAPIClient(api_keys=API_KEYS, request_sleep=REQUEST_SLEEP)

    # -----------------------------------------------------
    # 1) 채널 정보 수집
    # -----------------------------------------------------
    channel_rows = []
    channel_ids = df["유튜브채널ID"].unique().tolist()

    for i in range(0, len(channel_ids), 50):
        batch_ids = channel_ids[i:i+50]
        resp = yt.get_channels_info(batch_ids)

        item_map = {item["id"]: item for item in resp.get("items", [])}

        for ch_id in batch_ids:
            item = item_map.get(ch_id, {})
            snippet = item.get("snippet", {})
            stats = item.get("statistics", {})
            branding = item.get("brandingSettings", {})
            branding_channel = branding.get("channel", {}) if isinstance(branding, dict) else {}
            content = item.get("contentDetails", {})
            related = content.get("relatedPlaylists", {}) if isinstance(content, dict) else {}
            topic = item.get("topicDetails", {})

            uploads_playlist_id = related.get("uploads")
            if not uploads_playlist_id:
                uploads_playlist_id = _fallback_uploads_playlist_id(ch_id)

            channel_rows.append({
                "유튜브채널ID": ch_id,
                "채널명_API": snippet.get("title"),
                "채널설명_API": snippet.get("description"),
                "채널개설일_API": snippet.get("publishedAt"),
                "채널국가_API": snippet.get("country"),
                "채널구독자수_API": safe_int(stats.get("subscriberCount")),
                "채널총조회수_API": safe_int(stats.get("viewCount")),
                "채널총영상수_API": safe_int(stats.get("videoCount")),
                "브랜딩키워드_API": branding_channel.get("keywords"),
                "토픽카테고리_API": "|".join(topic.get("topicCategories", [])) if isinstance(topic.get("topicCategories", []), list) else None,
                "업로드플레이리스트ID": uploads_playlist_id,
                "채널수집시각": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            })

        print(f"[channels] {min(i+50, len(channel_ids))}/{len(channel_ids)} | quota={yt.quota_used_total}")

    channel_df = pd.DataFrame(channel_rows)
    save_csv_safe(channel_df, CIME_CHANNEL_INFO_RAW_PATH)

    # -----------------------------------------------------
    # 2) 최근 영상 수집
    # -----------------------------------------------------
    video_rows = []

    for idx, row in channel_df.iterrows():
        ch_id = row["유튜브채널ID"]
        playlist_id = row.get("업로드플레이리스트ID", None)

        if pd.isna(playlist_id) or not playlist_id:
            print(f"[skip] uploads playlist 없음 | channel_id={ch_id}")
            continue

        try:
            candidate_video_ids = []
            page_token = None
            page_count = 0

            while page_count < MAX_PLAYLIST_PAGES and len(candidate_video_ids) < RECENT_VIDEO_TARGET * 3:
                try:
                    pl_resp = yt.get_playlist_items(playlist_id, page_token=page_token)
                except Exception as e:
                    print(f"[playlist fail] channel_id={ch_id} playlist_id={playlist_id} err={e}")
                    break

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
                print(f"[skip] 최근 영상 없음 | channel_id={ch_id}")
                continue

            detail_rows = []
            for i in range(0, len(candidate_video_ids), 50):
                batch_vids = candidate_video_ids[i:i+50]
                try:
                    detail_resp = yt.get_video_details(batch_vids)
                except Exception as e:
                    print(f"[video detail fail] channel_id={ch_id} err={e}")
                    continue

                for v in detail_resp.get("items", []):
                    snippet = v.get("snippet", {})
                    stats = v.get("statistics", {})
                    content = v.get("contentDetails", {})
                    live = v.get("liveStreamingDetails", {})

                    duration_raw = content.get("duration")
                    duration_sec = parse_duration_to_sec(duration_raw)

                    if duration_sec is not None and duration_sec < MIN_DURATION_SEC:
                        continue

                    detail_rows.append({
                        "유튜브채널ID": ch_id,
                        "video_id": v.get("id"),
                        "video_title": snippet.get("title"),
                        "video_description": snippet.get("description"),
                        "video_published_at": snippet.get("publishedAt"),
                        "view_count": safe_int(stats.get("viewCount")),
                        "like_count": safe_int(stats.get("likeCount")),
                        "comment_count": safe_int(stats.get("commentCount")),
                        "duration": duration_raw,
                        "duration_sec": duration_sec,
                        "has_live_actual_start": int("actualStartTime" in live),
                        "video_collected_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    })

            if detail_rows:
                tmp = pd.DataFrame(detail_rows)
                tmp["video_published_at"] = pd.to_datetime(tmp["video_published_at"], errors="coerce", utc=True)
                tmp = tmp.sort_values("video_published_at", ascending=False).head(RECENT_VIDEO_TARGET).copy()
                tmp["engagement_per_view"] = (
                    (tmp["like_count"].fillna(0) + tmp["comment_count"].fillna(0))
                    / tmp["view_count"].replace(0, pd.NA)
                )
                video_rows.extend(tmp.to_dict("records"))

            print(
                f"[reference videos] {idx+1}/{len(channel_df)} "
                f"| channel_id={ch_id} "
                f"| saved={min(len(detail_rows), RECENT_VIDEO_TARGET)} "
                f"| quota={yt.quota_used_total}"
            )

        except Exception as e:
            print(f"[channel fail] channel_id={ch_id} err={e}")
            continue

    video_df = pd.DataFrame(video_rows)
    save_csv_safe(video_df, CIME_RECENT_VIDEO_RAW_PATH)

    # -----------------------------------------------------
    # 3) 채널 단위 집계
    # -----------------------------------------------------
    if len(video_df) > 0:
        agg = (
            video_df.groupby("유튜브채널ID")
            .agg(
                최근수집영상수=("video_id", "count"),
                최근영상조회수평균=("view_count", "mean"),
                최근영상좋아요수평균=("like_count", "mean"),
                최근영상댓글수평균=("comment_count", "mean"),
                최근영상참여율평균=("engagement_per_view", "mean"),
                최근영상실제라이브시작비율=("has_live_actual_start", "mean"),
                최근영상길이초평균=("duration_sec", "mean"),
                최근최신업로드일=("video_published_at", "max"),
            )
            .reset_index()
        )
    else:
        agg = pd.DataFrame(columns=["유튜브채널ID"])

    merged = df.merge(channel_df, on="유튜브채널ID", how="left").merge(agg, on="유튜브채널ID", how="left")

    # 레퍼런스 자동 추천
    merged["레퍼런스자동추천"] = (
        (merged["본채널여부"].fillna("") == "Y") &
        (pd.to_numeric(merged["채널구독자수_API"], errors="coerce").fillna(0) >= 100) &
        (pd.to_numeric(merged["채널총영상수_API"], errors="coerce").fillna(0) >= 3) &
        (pd.to_numeric(merged["최근수집영상수"], errors="coerce").fillna(0) >= 3)
    ).map({True: "Y", False: "N"})

    merged["레퍼런스자동추천_엄격"] = (
        (merged["본채널여부"].fillna("") == "Y") &
        (pd.to_numeric(merged["채널구독자수_API"], errors="coerce").fillna(0) >= 500) &
        (pd.to_numeric(merged["채널총영상수_API"], errors="coerce").fillna(0) >= 5) &
        (pd.to_numeric(merged["최근수집영상수"], errors="coerce").fillna(0) >= 5)
    ).map({True: "Y", False: "N"})

    save_csv_safe(merged, CIME_CHANNEL_INFO_PROCESSED_PATH)
    save_csv_safe(merged, CIME_TOP30_REFERENCE_PROFILE_PATH)

    save_json(
        REFERENCE_COLLECT_PROGRESS_PATH,
        {
            "last_run_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "reference_channel_count": int(df["유튜브채널ID"].nunique()),
            "saved_video_rows": int(len(video_df)),
            "quota_used_total": yt.quota_used_total,
            "exhausted_api_keys": yt.exhausted_api_keys,
        },
    )

    print_kv("최종 quota", yt.quota_used_total)
    print_kv("channel raw", CIME_CHANNEL_INFO_RAW_PATH)
    print_kv("video raw", CIME_RECENT_VIDEO_RAW_PATH)
    print_kv("processed", CIME_CHANNEL_INFO_PROCESSED_PATH)
    print_kv("reference profile", CIME_TOP30_REFERENCE_PROFILE_PATH)