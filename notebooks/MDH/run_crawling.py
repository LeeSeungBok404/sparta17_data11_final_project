import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time
import random
import os
import csv


start_idx = 0    # 예: 0 (첫 번째 사람), 500 (두 번째 사람) ...
end_idx = 11997    # 예: 500 (첫 번째 사람), 1000 (두 번째 사람) ...

input_file = "bj_links_fancafe_url_collected.csv" 
# 파일명에 범위가 자동으로 들어가서 나중에 취합할 때 안 헷갈려요!
output_file = f"fancafe_crawling_results_v2_{start_idx}to{end_idx}.csv"
# =========================================================

# 1. 데이터 불러오기
full_df = pd.read_csv(input_file)

# 조건: URL은 채워져 있고, 가입자수나 게시글수는 비어있는 행만 가져오기
cond_url = full_df['fancafe_url'].notna() & (full_df['fancafe_url'].str.strip() != "")
cond_empty = full_df['fancafe_member_count'].isna() | full_df['fancafe_post_count'].isna()

# 조건을 만족하는 타겟 전체 명단
target_df = full_df[cond_url & cond_empty].copy()
total_empty_count = len(target_df)

# 2. 팀원 각자의 할당량만큼 자르기
df = target_df.iloc[start_idx:end_idx].copy()
my_target_count = len(df)

# 3. 이어하기 로직
if os.path.exists(output_file):
    done_df = pd.read_csv(output_file)
    done_ids = set(done_df['channel_id'].astype(str).tolist())
    print(f"\n기존 기록 확인: {len(done_ids)}개 완료됨. 남은 {my_target_count - len(done_ids)}개를 이어서 시작합니다.")
else:
    columns = ['channel_id', 'streamer_name', 'fancafe_url', 'fancafe_member_count', 'fancafe_post_count']
    with open(output_file, mode='w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(columns)
    done_ids = set()

# 4. Selenium 설정
options = webdriver.ChromeOptions()
options.add_argument('--start-maximized') 
options.add_argument('--window-size=1920,1080') 
options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

print(f"\n[전체 누락자 {total_empty_count}명 중 {start_idx}~{end_idx} 구간 수집 시작]")
print(f"내 할당량: {my_target_count}명")
print("="*60)

# 5. 분담된 루프 시작
current_idx = 0
for _, row in df.iterrows():
    current_idx += 1
    channel_id = str(row.get('channel_id'))
    
    if channel_id in done_ids:
        continue
        
    streamer_name = row.get('streamer_name')
    raw_url = str(row.get('fancafe_url'))
    pc_url = raw_url.replace("m.cafe.naver.com", "cafe.naver.com")
    
    member_count, post_count = "수집불가", "수집불가"
    
    try:
        driver.get(pc_url)
        time.sleep(random.uniform(3, 5)) 
        
        try:
            member_element = driver.find_element(By.CSS_SELECTOR, '.mem-cnt-info em')
            member_count = "".join(filter(str.isdigit, member_element.text))
        except:
            member_count = "0"

        try:
            li_tags = driver.find_elements(By.TAG_NAME, 'li')
            found_post = "0"
            for li in li_tags:
                text_content = li.text.replace(' ', '').replace('\n', '')
                if '전체글' in text_content:
                    found_post = "".join(filter(str.isdigit, text_content))
                    if found_post: break
            post_count = found_post
        except:
            post_count = "0"

        member_count = member_count if member_count else "0"
        post_count = post_count if post_count else "0"
            
    except Exception as e:
        member_count, post_count = "ERR", "ERR"

    print(f"진행도: [{current_idx}/{my_target_count}] | 스트리머: {streamer_name}")
    print(f"URL: {pc_url}")
    print(f"가입자: {member_count} | 게시글: {post_count}")
    print("-" * 60)

    with open(output_file, mode='a', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([channel_id, streamer_name, pc_url, member_count, post_count])

driver.quit()

new_done_count = my_target_count - len(done_ids)
print(f"\n{my_target_count}명 중 미수집된 {new_done_count}명 전원 수집 완료!")
print(f"결과 파일: {output_file} ")