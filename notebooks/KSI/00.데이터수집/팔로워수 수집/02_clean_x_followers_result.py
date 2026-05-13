"""
x_followers_result.csv 정리 스크립트

목적:
- 기존 수집 결과 파일에서 숫자 / NOT_FOUND / SUSPENDED 만 남김
- PARSE_FAIL / NO_FOLLOWER_TEXT / RATE_LIMIT / ERROR 등 애매한 실패는 제거
- 예전에 잘못 섞인 10컬럼 로그 행도 최대한 복구해서 정상 결과만 반영
- username 기준으로 중복이 있으면 뒤에 나온 정상 결과를 최종값으로 사용
- 원본은 .backup_YYYYMMDD_HHMMSS.csv 로 백업

실행:
  python clean_x_followers_result.py

옵션:
  python clean_x_followers_result.py --input x_followers_result.csv --output x_followers_result.csv
  python clean_x_followers_result.py --output x_followers_result_clean.csv
"""

import argparse
import csv
import re
import shutil
from collections import Counter
from datetime import datetime
from pathlib import Path


FINAL_STATUSES = {"NOT_FOUND", "SUSPENDED"}


def normalize_username(username: str) -> str:
    return (username or "").strip().lstrip("@").lower()


def is_final_value(value: str) -> bool:
    v = (value or "").strip()
    return bool(re.fullmatch(r"\d+", v)) or v in FINAL_STATUSES


def parse_row(row):
    """
    반환:
      (channel_id, streamer_name, username, twitter_url, followers_count) 또는 None

    지원 형태:
    1) 정상 5컬럼
       channel_id, streamer_name, username, twitter_url, followers_count

    2) 예전 잘못 섞인 10컬럼
       index, channel_id, streamer_name, platform, username, twitter_url,
       followers_count, status, collected_at, current_url
    """
    if len(row) == 5:
        channel_id, streamer_name, username, twitter_url, followers_count = row
        followers_count = (followers_count or "").strip()

        if not is_final_value(followers_count):
            return None

        return {
            "channel_id": channel_id,
            "streamer_name": streamer_name,
            "username": username,
            "twitter_url": twitter_url,
            "followers_count": followers_count,
        }

    if len(row) >= 10:
        # 10컬럼 로그 행 복구
        # [0] index, [1] channel_id, [2] streamer_name, [3] platform,
        # [4] username, [5] twitter_url, [6] followers_count, [7] status ...
        channel_id = row[1]
        streamer_name = row[2]
        username = row[4]
        twitter_url = row[5]
        followers_count_raw = (row[6] or "").strip()
        status = (row[7] or "").strip()

        if followers_count_raw.isdigit():
            followers_count = followers_count_raw
        elif status in FINAL_STATUSES:
            followers_count = status
        else:
            return None

        if not is_final_value(followers_count):
            return None

        return {
            "channel_id": channel_id,
            "streamer_name": streamer_name,
            "username": username,
            "twitter_url": twitter_url,
            "followers_count": followers_count,
        }

    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="x_followers_result.csv")
    parser.add_argument("--output", default="x_followers_result.csv")
    parser.add_argument("--no-backup", action="store_true")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        raise FileNotFoundError(f"입력 파일이 없습니다: {input_path}")

    if input_path.resolve() == output_path.resolve() and not args.no_backup:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = input_path.with_name(f"{input_path.stem}.backup_{ts}{input_path.suffix}")
        shutil.copy2(input_path, backup_path)
        print(f"[백업 생성] {backup_path}")

    final_by_username = {}
    total_rows = 0
    kept_rows = 0
    skipped_rows = 0
    malformed_rows = 0
    skipped_value_counter = Counter()

    with open(input_path, encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        header = next(reader, None)

        for row in reader:
            total_rows += 1

            parsed = parse_row(row)

            if parsed is None:
                skipped_rows += 1

                if len(row) == 5:
                    skipped_value_counter[(row[4] or "").strip()] += 1
                elif len(row) >= 10:
                    status = (row[7] or "").strip()
                    value = (row[6] or "").strip()
                    skipped_value_counter[status or value or "UNKNOWN"] += 1
                else:
                    malformed_rows += 1
                    skipped_value_counter[f"MALFORMED_LEN_{len(row)}"] += 1

                continue

            username_key = normalize_username(parsed["username"])
            if not username_key:
                skipped_rows += 1
                skipped_value_counter["EMPTY_USERNAME"] += 1
                continue

            # 뒤에 나온 정상 결과를 최종값으로 사용
            final_by_username[username_key] = parsed
            kept_rows += 1

    fieldnames = ["channel_id", "streamer_name", "username", "twitter_url", "followers_count"]

    with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for username_key in sorted(final_by_username):
            writer.writerow(final_by_username[username_key])

    status_counter = Counter(row["followers_count"] if not row["followers_count"].isdigit() else "OK"
                             for row in final_by_username.values())

    print()
    print("=" * 70)
    print("정리 완료")
    print("=" * 70)
    print(f"입력 파일: {input_path.resolve()}")
    print(f"출력 파일: {output_path.resolve()}")
    print(f"전체 읽은 행 수: {total_rows}")
    print(f"정상 후보로 읽은 행 수: {kept_rows}")
    print(f"최종 unique username 수: {len(final_by_username)}")
    print(f"제거한 애매/불량 행 수: {skipped_rows}")
    print(f"형식 자체가 이상한 행 수: {malformed_rows}")
    print()
    print("[최종 상태]")
    for k, v in status_counter.most_common():
        print(f"  {k}: {v}")
    print()
    print("[제거된 값 상위]")
    for k, v in skipped_value_counter.most_common(20):
        print(f"  {k}: {v}")

    print()
    print("다음 수집 실행 시 이 파일 기준으로 숫자 / NOT_FOUND / SUSPENDED 만 건너뛰고,")
    print("PARSE_FAIL / NO_FOLLOWER_TEXT / RATE_LIMIT / ERROR 계정은 다시 시도됩니다.")


if __name__ == "__main__":
    main()
