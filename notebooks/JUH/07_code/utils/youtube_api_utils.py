import re
import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class QuotaExhaustedError(Exception):
    pass


class YouTubeAPIClient:
    def __init__(self, api_keys: list[str], request_sleep: float = 0.12):
        if not api_keys:
            raise ValueError("api_keys가 비어 있습니다.")
        self.api_keys = api_keys.copy()
        self.active_api_keys = api_keys.copy()
        self.exhausted_api_keys = []
        self.api_key_idx = 0
        self.quota_used_total = 0
        self.request_sleep = request_sleep
        self.session = self._build_session()

    def _build_session(self):
        session = requests.Session()
        retry_strategy = Retry(
            total=2,
            connect=2,
            read=2,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    def _get_next_api_key(self):
        if not self.active_api_keys:
            raise QuotaExhaustedError("모든 API KEY quota 소진")
        key = self.active_api_keys[self.api_key_idx % len(self.active_api_keys)]
        self.api_key_idx += 1
        return key

    def _mark_key_exhausted(self, key: str):
        if key in self.active_api_keys:
            self.active_api_keys.remove(key)
        if key not in self.exhausted_api_keys:
            self.exhausted_api_keys.append(key)

    def get_json(self, url: str, params: dict, quota_cost: int = 1, max_key_retry: int = 100):
        quota_reasons = {
            "quotaexceeded",
            "dailylimitexceeded",
            "dailylimitexceededunreg",
            "userratelimitexceeded",
            "ratelimitexceeded",
        }

        tried = 0
        last_error = None

        while tried < max_key_retry:
            if not self.active_api_keys:
                raise QuotaExhaustedError("모든 API KEY quota 소진")

            key = self._get_next_api_key()
            local_params = params.copy()
            local_params["key"] = key

            try:
                r = self.session.get(url, params=local_params, timeout=30)

                if r.status_code == 403:
                    try:
                        err = r.json()
                    except Exception:
                        err = {"error": {"message": r.text}}

                    reasons = []
                    try:
                        reasons = [
                            e.get("reason", "").lower()
                            for e in err.get("error", {}).get("errors", [])
                        ]
                    except Exception:
                        pass

                    msg = str(err).lower()
                    if any(reason in quota_reasons for reason in reasons) or "quota" in msg:
                        print(f"[KEY 소진 감지] {key}")
                        self._mark_key_exhausted(key)
                        tried += 1
                        time.sleep(0.4)
                        continue

                    r.raise_for_status()

                r.raise_for_status()
                self.quota_used_total += quota_cost
                time.sleep(self.request_sleep)
                return r.json()

            except QuotaExhaustedError:
                raise
            except Exception as e:
                last_error = e
                tried += 1
                time.sleep(0.5)

        raise last_error if last_error else Exception("API 호출 실패")

    # -----------------------------------------------------
    # YouTube API helpers
    # -----------------------------------------------------
    def get_channels_info(self, channel_ids: list[str]):
        if not channel_ids:
            return {"items": []}
        url = "https://www.googleapis.com/youtube/v3/channels"
        params = {
            "id": ",".join(channel_ids),
            "part": "snippet,statistics,brandingSettings,contentDetails,status,topicDetails"
        }
        return self.get_json(url, params, quota_cost=1)

    def get_playlist_items(self, playlist_id: str, page_token: str | None = None):
        url = "https://www.googleapis.com/youtube/v3/playlistItems"
        params = {
            "playlistId": playlist_id,
            "part": "snippet,contentDetails",
            "maxResults": 50
        }
        if page_token:
            params["pageToken"] = page_token
        return self.get_json(url, params, quota_cost=1)

    def get_video_details(self, video_ids: list[str]):
        if not video_ids:
            return {"items": []}
        url = "https://www.googleapis.com/youtube/v3/videos"
        params = {
            "id": ",".join(video_ids),
            "part": "snippet,statistics,contentDetails,liveStreamingDetails"
        }
        return self.get_json(url, params, quota_cost=1)

    def search_channels(
        self,
        query: str,
        region_code: str = "KR",
        relevance_language: str = "ko",
        page_token: str | None = None
    ):
        url = "https://www.googleapis.com/youtube/v3/search"
        params = {
            "q": query,
            "part": "snippet",
            "type": "channel",
            "maxResults": 10,
            "order": "relevance",
            "regionCode": region_code,
            "relevanceLanguage": relevance_language,
        }
        if page_token:
            params["pageToken"] = page_token
        return self.get_json(url, params, quota_cost=100)

    def search_videos(
        self,
        query: str,
        region_code: str = "KR",
        relevance_language: str = "ko",
        published_after: str | None = None,
        published_before: str | None = None,
        page_token: str | None = None
    ):
        url = "https://www.googleapis.com/youtube/v3/search"
        params = {
            "q": query,
            "part": "snippet",
            "type": "video",
            "maxResults": 50,
            "order": "relevance",
            "regionCode": region_code,
            "relevanceLanguage": relevance_language,
        }
        if published_after:
            params["publishedAfter"] = published_after
        if published_before:
            params["publishedBefore"] = published_before
        if page_token:
            params["pageToken"] = page_token
        return self.get_json(url, params, quota_cost=100)


def safe_int(x):
    try:
        if x is None or x == "":
            return None
        return int(x)
    except Exception:
        return None


def parse_duration_to_sec(duration):
    if not duration:
        return None
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", str(duration))
    if not m:
        return None
    h = int(m.group(1) or 0)
    mnt = int(m.group(2) or 0)
    s = int(m.group(3) or 0)
    return h * 3600 + mnt * 60 + s