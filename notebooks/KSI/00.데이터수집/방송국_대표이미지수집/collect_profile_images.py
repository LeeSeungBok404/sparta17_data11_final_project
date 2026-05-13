import pandas as pd
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
import time
import re

INPUT_PATH = "core_candidates_834_image_targets_full.csv"
OUTPUT_PATH = "핵심후보군_전체834명_이미지URL추가.csv"

df = pd.read_csv(INPUT_PATH)

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
}


def clean_url(url):
    if pd.isna(url):
        return ""
    return str(url).strip()


def extract_soop_id(url):
    """
    SOOP/Afreeca 방송국 URL에서 BJ ID 추출

    지원 예시:
    https://www.sooplive.com/station/gosegu2
    https://ch.sooplive.co.kr/gosegu2
    https://bj.afreecatv.com/gosegu2
    https://play.sooplive.co.kr/gosegu2/...
    """
    url = clean_url(url)
    if not url:
        return None

    parsed = urlparse(url)
    host = parsed.netloc.lower()
    path_parts = [p for p in parsed.path.split("/") if p]

    if not path_parts:
        return None

    # 여기에 sooplive.com 추가!!!
    if (
        "sooplive.com" in host
        or "sooplive.co.kr" in host
        or "afreecatv.com" in host
    ):
        # 케이스 1: /station/아이디
        if path_parts[0] == "station" and len(path_parts) >= 2:
            return path_parts[1]

        # 케이스 2: /아이디
        if path_parts[0] not in ["station", "player", "app", "vod", "category"]:
            return path_parts[0]

        # 케이스 3: /player/아이디 같은 예외형
        if len(path_parts) >= 2:
            return path_parts[1]

    return None


def make_soop_profile_url(bj_id):
    """
    SOOP/Afreeca 프로필 이미지 URL 규칙
    ID 앞 2글자를 폴더로 사용
    """
    if not bj_id or len(bj_id) < 2:
        return None

    prefix = bj_id[:2]
    return f"https://profile.img.afreecatv.com/LOGO/{prefix}/{bj_id}/{bj_id}.jpg"

def check_image_url(image_url):
    try:
        res = requests.get(image_url, headers=headers, timeout=10)
        content_type = res.headers.get("Content-Type", "")

        if res.status_code == 200 and "image" in content_type:
            return True

        return False

    except Exception:
        return False


def extract_chzzk_channel_id(url):
    """
    CHZZK 채널 URL에서 channel_id 추출
    예:
    https://chzzk.naver.com/xxxxxxxx
    """
    url = clean_url(url)
    if not url:
        return None

    parsed = urlparse(url)
    host = parsed.netloc.lower()
    path_parts = [p for p in parsed.path.split("/") if p]

    if "chzzk.naver.com" in host and path_parts:
        return path_parts[0]

    return None


def get_chzzk_profile_image(channel_id):
    """
    CHZZK 채널 API에서 프로필 이미지 가져오기
    """
    api_url = f"https://api.chzzk.naver.com/service/v1/channels/{channel_id}"

    try:
        res = requests.get(api_url, headers=headers, timeout=10)
        if res.status_code != 200:
            return None, f"CHZZK_API실패_{res.status_code}"

        data = res.json()
        content = data.get("content", {})

        image_url = content.get("channelImageUrl")
        if image_url:
            return image_url, "OK_chzzk_api"

        return None, "CHZZK_이미지없음"

    except Exception as e:
        return None, f"CHZZK_에러_{type(e).__name__}"


def get_image_from_meta(url):
    """
    기존 방식: HTML meta 이미지 찾기
    """
    try:
        res = requests.get(url, headers=headers, timeout=10)

        if res.status_code != 200:
            return None, f"접속실패_{res.status_code}"

        soup = BeautifulSoup(res.text, "html.parser")

        og_image = soup.find("meta", property="og:image")
        if og_image and og_image.get("content"):
            return urljoin(url, og_image["content"].strip()), "OK_og_image"

        twitter_image = soup.find("meta", attrs={"name": "twitter:image"})
        if twitter_image and twitter_image.get("content"):
            return urljoin(url, twitter_image["content"].strip()), "OK_twitter_image"

        return None, "이미지못찾음"

    except Exception as e:
        return None, f"메타에러_{type(e).__name__}"


def get_profile_image(row):
    url = clean_url(row.get("broadcast_url", ""))
    platform = str(row.get("platform", "")).lower()

    if not url:
        return None, "URL없음"

    # 1. SOOP / Afreeca
    soop_id = extract_soop_id(url)
    if soop_id:
        image_url = make_soop_profile_url(soop_id)

        if check_image_url(image_url):
            return image_url, "OK_soop_url_rule"

        return None, "SOOP_이미지URL검증실패"

    # 2. CHZZK
    chzzk_id = extract_chzzk_channel_id(url)
    if chzzk_id:
        return get_chzzk_profile_image(chzzk_id)

    # 3. 그 외 fallback
    return get_image_from_meta(url)


profile_image_urls = []
image_statuses = []

for idx, row in df.iterrows():
    name = row.get("streamer_name", "")
    url = row.get("broadcast_url", "")

    print(f"[{idx + 1}/{len(df)}] {name} 이미지 확인 중...")

    image_url, status = get_profile_image(row)

    profile_image_urls.append(image_url)
    image_statuses.append(status)

    time.sleep(0.3)

df["profile_image_url"] = profile_image_urls
df["image_status"] = image_statuses

df.to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")

print("완료!")
print(df["image_status"].value_counts())
print(f"저장 파일: {OUTPUT_PATH}")