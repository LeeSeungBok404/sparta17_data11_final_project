# uv run python notebooks/LSB/fan_cafe.py all

import sys
import re
import json
import time
import shutil
import concurrent.futures
from pathlib import Path
from urllib.parse import quote

import pandas as pd
from playwright.sync_api import sync_playwright

from pydantic_ai import Agent
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider


# ============================================================
# 실행 설정
# ============================================================
MODE = sys.argv[1] if len(sys.argv) >= 2 else "test"

TEST_LIMIT = 50

# all 모드에서 1회 실행당 최대 처리 streamer 수
BATCH_LIMIT = 500

# all 모드에서 1회 실행당 Gemini 최대 호출 수
MAX_API_CALLS = 500

PROJECT_ID = "fan-cafe-collect"
LOCATION = "global"
MODEL_NAME = "gemini-2.5-flash-lite"

DATA_DIR = Path("integreted/data")
BASE_INPUT_PATH = DATA_DIR / "검증하자검증.csv"
SAMPLE_OUTPUT_PATH = DATA_DIR / "fancafe_sample.csv"
CHECKED_PREFIX = "검증하자검증_fancafe_checked"

STREAMER_COL = "streamer_name"
URL_COL = "fancafe_url"
MEMBER_COL = "fancafe_member_count"
STATUS_COL = "fancafe_status"
REASON_COL = "fancafe_reason"


# ============================================================
# Gemini Agent
# ============================================================
provider = GoogleProvider(
    vertexai=True,
    project=PROJECT_ID,
    location=LOCATION,
)

model = GoogleModel(MODEL_NAME, provider=provider)

agent = Agent(
    model,
    system_prompt="""
너는 네이버 카페 검색 결과에서 스트리머의 팬카페를 판별하는 검증자다.

[우선순위 규칙]
1. 가장 먼저 streamer_name 개인 팬카페가 있는지 찾는다.
2. 개인 팬카페가 있다면 반드시 그것을 선택한다.
3. 개인 팬카페가 없다면, streamer_name이 속한 그룹/팀/크루의 팬카페도 허용한다.
4. 단, 개인 팬카페와 그룹 팬카페가 동시에 존재하면 반드시 개인 팬카페를 선택한다.
5. 검색 결과가 애매할 경우, 카페 주제/카테고리가 "팬카페 > 스트리머/유튜버" 또는 "방송/연예 > 인터넷방송"에 해당하는 카페를 우선 선택한다.

[판단 기준]
- 카페명, 설명, 검색 텍스트에 streamer_name이 직접 포함되면 강한 근거다.
- streamer_name이 없고 그룹명만 있는 경우는 텍스트에 streamer_name 관련 내용이나 소속 관계가 있어야 한다.
- 동명이인, 일반 연예인 팬카페, 무관한 카페, 근거 부족인 경우 선택하지 않는다.
- 확신이 낮으면 선택하지 않는다.

[중요]
- 반드시 가장 적절한 후보 1개만 선택한다.
- 없으면 found=false로 한다.
- 출력은 반드시 JSON만 한다.

형식:
{
  "found": true 또는 false,
  "selected_index": 숫자 또는 null,
  "reason": "짧은 판단 근거"
}
"""
)


class QuotaExceededError(Exception):
    pass


# ============================================================
# 파일 관리
# ============================================================
def get_checked_files():
    pattern = f"{CHECKED_PREFIX}*.csv"
    files = []

    for path in DATA_DIR.glob(pattern):
        m = re.search(rf"{re.escape(CHECKED_PREFIX)}(\d+)\.csv$", path.name)
        if m:
            files.append((int(m.group(1)), path))

    files.sort(key=lambda x: x[0])
    return files


def get_paths():
    if MODE != "all":
        return BASE_INPUT_PATH, SAMPLE_OUTPUT_PATH, None

    checked_files = get_checked_files()

    if not checked_files:
        # 첫 all 실행
        input_path = BASE_INPUT_PATH
        output_path = DATA_DIR / f"{CHECKED_PREFIX}1.csv"
        current_num = 1
    else:
        # 마지막 checked 파일에서 이어서 시작
        last_num, input_path = checked_files[-1]

        # 일단 마지막 파일에 중간 저장하면서 이어감
        # 정상적으로 batch가 끝나면 다음 번호 파일도 생성
        output_path = input_path
        current_num = last_num

    return input_path, output_path, current_num


def make_next_output_path(current_num):
    return DATA_DIR / f"{CHECKED_PREFIX}{current_num + 1}.csv"


def save_checkpoint(df, output_path):
    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"  중간 저장 완료 → {output_path}")


# ============================================================
# 유틸
# ============================================================
def is_empty_url(value):
    if pd.isna(value):
        return True

    value = str(value).strip()
    return value in ["", "nan", "None", "null"]


def is_already_processed(value):
    if pd.isna(value):
        return False

    value = str(value).strip()
    return value not in ["", "nan", "None", "null"]


def parse_member_count(text):
    if not isinstance(text, str):
        return ""

    text = text.replace(",", "")
    text = text.replace(" ", "")

    patterns = [
        r"멤버수([0-9.]+)만?",
        r"회원수([0-9.]+)만?",
        r"멤버([0-9.]+)만?명?",
        r"회원([0-9.]+)만?명?",
        r"([0-9.]+)만명",
        r"멤버수([0-9]+)",
        r"회원수([0-9]+)",
        r"멤버([0-9]+)",
        r"회원([0-9]+)",
    ]

    for pattern in patterns:
        m = re.search(pattern, text)
        if m:
            num = float(m.group(1))
            if "만" in m.group(0):
                return int(num * 10000)
            return int(num)

    return ""


def safe_json_loads(raw):
    raw = str(raw).strip()
    raw = raw.replace("```json", "").replace("```", "").strip()

    try:
        return json.loads(raw)
    except Exception:
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            return json.loads(m.group(0))
        raise


# ============================================================
# 네이버 카페 검색
# ============================================================
def search_naver_cafe(page, streamer_name, max_candidates=20):
    queries = [f"{streamer_name}"]
    candidates = []
    page_load_failed = False

    preferred_categories = [
        "팬카페",
        "스트리머/유튜버",
        "방송/연예",
        "인터넷방송",
    ]

    for query in queries:
        url = f"https://section.cafe.naver.com/ca-fe/home/search/cafes?q={quote(query)}"
        print(f"  검색어: {query}")

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(3000)
        except Exception as e:
            print(f"  페이지 이동 실패: {e}")
            page_load_failed = True
            continue

        links = page.locator("a").all()

        for a in links:
            try:
                href = a.get_attribute("href")
                title = a.inner_text().strip()

                if not href or not title:
                    continue

                if "cafe.naver.com" not in href:
                    continue

                if any(c["url"] == href for c in candidates):
                    continue

                full_text = title

                try:
                    parent = a.locator("xpath=./ancestor::*[self::li or self::div][1]")
                    full_text = parent.inner_text().strip()
                except Exception:
                    pass

                member_count = parse_member_count(full_text)

                category_score = sum(
                    1 for keyword in preferred_categories
                    if keyword in full_text
                )

                candidates.append({
                    "title": title[:120],
                    "url": href,
                    "text": full_text[:1000],
                    "member_count": member_count,
                    "search_query": query,
                    "category_score": category_score,
                })

            except Exception:
                continue

    # 팬카페/스트리머/인터넷방송 카테고리 신호가 있는 후보를 앞쪽으로 정렬
    candidates = sorted(
        candidates,
        key=lambda c: (
            c.get("category_score", 0),
            1 if streamer_name in c.get("text", "") else 0,
            1 if c.get("member_count") not in ["", None] else 0,
        ),
        reverse=True,
    )

    return candidates[:max_candidates], page_load_failed


# ============================================================
# Gemini 판단
# ============================================================
def run_agent_sync(prompt_text):
    return agent.run_sync(prompt_text)


def judge_with_gemini(streamer_name, candidates):
    if not candidates:
        return {
            "found": False,
            "selected_index": None,
            "reason": "검색 후보 없음"
        }

    user_prompt = {
        "streamer_name": streamer_name,
        "candidates": [
            {
                "index": i,
                "title": c["title"],
                "url": c["url"],
                "text": c["text"],
                "member_count": c["member_count"],
                "search_query": c["search_query"],
            }
            for i, c in enumerate(candidates)
        ]
    }

    try:
        prompt_text = json.dumps(user_prompt, ensure_ascii=False)

        # Playwright sync_api와 PydanticAI run_sync event loop 충돌 방지
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(run_agent_sync, prompt_text)
            result = future.result()

        decision = safe_json_loads(result.output)

        return {
            "found": decision.get("found", False),
            "selected_index": decision.get("selected_index", None),
            "reason": decision.get("reason", ""),
        }

    except Exception as e:
        err = str(e)

        if (
            "quota" in err.lower()
            or "exceeded" in err.lower()
            or "429" in err
            or "insufficient" in err.lower()
            or "resource exhausted" in err.lower()
        ):
            raise QuotaExceededError(err)

        return {
            "found": False,
            "selected_index": None,
            "reason": f"Gemini 판단 실패: {err}"
        }


# ============================================================
# 브라우저 실행
# ============================================================
def launch_browser(p):
    try:
        print("Chrome 실행 시도...")
        return p.chromium.launch(channel="chrome", headless=False)
    except Exception as e:
        print(f"Chrome 실행 실패, Chromium으로 대체: {e}")
        return p.chromium.launch(headless=False)


# ============================================================
# 메인
# ============================================================
def main():
    input_path, output_path, current_num = get_paths()

    print(f"실행 모드: {MODE}")
    print(f"입력 파일: {input_path}")
    print(f"중간 저장 파일: {output_path}")

    if MODE == "all":
        print(f"이번 실행 최대 처리 수: {BATCH_LIMIT}")
        print(f"이번 실행 Gemini 최대 호출 수: {MAX_API_CALLS}")
    else:
        print(f"test 샘플 수: {TEST_LIMIT}")

    df = pd.read_csv(input_path, encoding="utf-8-sig")

    for col in [URL_COL, MEMBER_COL, STATUS_COL, REASON_COL]:
        if col not in df.columns:
            df[col] = ""
            
    df[MEMBER_COL] = pd.to_numeric(df[MEMBER_COL], errors="coerce").astype("Int64")

    target_streamers = []

    for streamer_name in df[STREAMER_COL].dropna().unique():
        streamer_name = str(streamer_name).strip()

        mask = df[STREAMER_COL].astype(str).str.strip() == streamer_name
        urls = df.loc[mask, URL_COL]

        # fancafe_url이 완전히 빈 streamer만 처리
        # Not_Found도 처리 완료로 간주
        if all(is_empty_url(v) for v in urls):
            target_streamers.append(streamer_name)

    if MODE == "all":
        target_streamers = target_streamers[:BATCH_LIMIT]
    else:
        target_streamers = target_streamers[:TEST_LIMIT]
        df = df[df[STREAMER_COL].astype(str).str.strip().isin(target_streamers)].copy()

    print(f"이번 실행 처리 대상 streamer 수: {len(target_streamers)}")

    api_call_count = 0
    processed_count = 0
    found_count = 0
    not_found_count = 0
    stopped_early = False

    with sync_playwright() as p:
        browser = launch_browser(p)
        page = browser.new_page()

        try:
            for i, streamer_name in enumerate(target_streamers, start=1):
                print(f"\n[{i}/{len(target_streamers)}] 검색: {streamer_name}")

                mask = df[STREAMER_COL].astype(str).str.strip() == streamer_name

                candidates, page_load_failed = search_naver_cafe(page, streamer_name)

                print(f"  후보 수: {len(candidates)}")
                for idx, c in enumerate(candidates):
                    print(
                        f"  후보 {idx}: {c['title']} / 멤버수={c['member_count']} / {c['url']}"
                    )

                # 후보가 없으면 Gemini 호출하지 않음
                if not candidates:
                    if page_load_failed:
                        df.loc[mask, URL_COL] = "Search_Error"
                        df.loc[mask, MEMBER_COL] = pd.NA
                        df.loc[mask, STATUS_COL] = "Search_Error"
                        df.loc[mask, REASON_COL] = "페이지 이동 실패"
                        not_found_count += 1
                        print("  Search_Error: 페이지 이동 실패 / Gemini 호출 안 함")
                    else:
                        df.loc[mask, URL_COL] = "Not_Found"
                        df.loc[mask, MEMBER_COL] = pd.NA
                        df.loc[mask, STATUS_COL] = "Not_Found"
                        df.loc[mask, REASON_COL] = "검색 후보 없음"
                        not_found_count += 1
                        print("  Not_Found: 검색 후보 없음 / Gemini 호출 안 함")

                    processed_count += 1
                    save_checkpoint(df, output_path)
                    time.sleep(1.2)
                    continue

                if api_call_count >= MAX_API_CALLS:
                    print("\nAPI 호출 제한 도달 → 저장 후 종료")
                    stopped_early = True
                    save_checkpoint(df, output_path)
                    break

                try:
                    decision = judge_with_gemini(streamer_name, candidates)
                    api_call_count += 1

                    print(f"  Gemini 사용 횟수: {api_call_count}/{MAX_API_CALLS}")
                    print("  Gemini 판단:", decision)

                except QuotaExceededError as e:
                    print("\nQuota 초과 또는 호출 제한 발생 → 저장 후 종료")
                    print(f"오류 내용: {e}")
                    stopped_early = True
                    save_checkpoint(df, output_path)
                    break

                if decision.get("found") is True:
                    selected_index = decision.get("selected_index")

                    if isinstance(selected_index, int) and 0 <= selected_index < len(candidates):
                        selected = candidates[selected_index]

                        df.loc[mask, URL_COL] = selected["url"]
                        df.loc[mask, MEMBER_COL] = selected["member_count"]
                        df.loc[mask, STATUS_COL] = "Found"
                        df.loc[mask, REASON_COL] = decision.get("reason", "")

                        print(f"  FOUND → {selected['url']}")
                        print(f"  멤버수 → {selected['member_count']}")
                        found_count += 1
                    else:
                        df.loc[mask, URL_COL] = "Not_Found"
                        df.loc[mask, MEMBER_COL] = pd.NA
                        df.loc[mask, STATUS_COL] = "Not_Found"
                        df.loc[mask, REASON_COL] = "Gemini selected_index 오류"

                        print("  Not_Found: selected_index 오류")
                        not_found_count += 1
                else:
                    df.loc[mask, URL_COL] = "Not_Found"
                    df.loc[mask, MEMBER_COL] = pd.NA
                    df.loc[mask, STATUS_COL] = "Not_Found"
                    df.loc[mask, REASON_COL] = decision.get("reason", "")

                    print("  Not_Found")
                    not_found_count += 1

                processed_count += 1
                save_checkpoint(df, output_path)
                time.sleep(1.2)

        finally:
            browser.close()
            
    # 같은 streamer_name 기준으로 fancafe_url / member_count / status / reason 빈값 보정
    for col in [URL_COL, MEMBER_COL, STATUS_COL, REASON_COL]:
        df[col] = df.groupby(STREAMER_COL)[col].transform(lambda s: s.ffill().bfill())

    save_checkpoint(df, output_path)

    # all 모드에서 정상적으로 batch가 끝났으면 다음 번호 파일 생성
    if MODE == "all" and not stopped_early and processed_count > 0:
        next_output_path = make_next_output_path(current_num)
        shutil.copy2(output_path, next_output_path)

        print("\n이번 batch 정상 완료")
        print(f"현재 결과 파일: {output_path}")
        print(f"다음 실행 시작 파일로 복사됨: {next_output_path}")
        print("다음에 다시 아래 명령을 실행하면 최신 checked 파일에서 이어서 시작합니다.")
        print("uv run python notebooks/LSB/fan_cafe.py all")

    print("\n완료 또는 중단")
    print(f"이번 실행 처리 수: {processed_count}")
    print(f"URL 찾은 수: {found_count}")
    print(f"Not_Found/Search_Error 처리 수: {not_found_count}")
    print(f"이번 실행 Gemini 실제 호출 수: {api_call_count}")
    print(f"마지막 저장 위치: {output_path}")

    if MODE == "all" and stopped_early:
        print("\n중간에 끊겼거나 API 제한으로 중단되었습니다.")
        print(f"다음 실행 시 이 파일부터 이어서 시작합니다: {output_path}")
        print("명령어:")
        print("uv run python notebooks/LSB/fan_cafe.py all")


if __name__ == "__main__":
    main()