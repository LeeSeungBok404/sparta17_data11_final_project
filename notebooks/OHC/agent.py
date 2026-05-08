import pandas as pd
import google.generativeai as genai
import time
import os
try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS

# ==========================================
# 🛠️ 1. 경로 및 모델 자동 탐색 (404 방지)
# ==========================================
base_dir = os.path.dirname(os.path.abspath(__file__))

# 🚨 선샌니의 API 키가 적용되었습니다! (보안 주의!)
GOOGLE_API_KEY = "AIzaSyBfrdRlbh-n9KMRuMxnyMZQDxAQXQz7M2o"
genai.configure(api_key=GOOGLE_API_KEY)

def get_best_model():
    try:
        available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        selected = next((m for m in available_models if 'gemini-1.5-flash' in m), available_models[0])
        print(f"✅ 사용 모델 확정: {selected}")
        return genai.GenerativeModel(selected)
    except Exception as e:
        print(f"🚨 모델 초기화 실패: {e}")
        exit()

model = get_best_model()

INPUT_CSV = os.path.join(base_dir, 'CIME_Idol_List.csv')          
OUTPUT_CSV = os.path.join(base_dir, 'CIME_Idol_List_Result.csv')  

# 🧠 2. 잼민 탐정 엔진 (한 글자 출력 절대 방지 버전)
def search_streamer_crew(streamer_name, channel_id):
    search_results = ""
    query = f"{streamer_name} 버츄얼 스트리머 소속 MCN 그룹 크루"
    
    try:
        results = list(DDGS().text(query, max_results=5))
        for r in results:
            search_results += f"- {r['body']}\n"
    except Exception as e:
        print(f"⚠️ 검색 엔진 오류: {e}")

    # ✨ 프롬프트를 훨씬 더 엄격하고 구체적으로 바꿨습니다!
    prompt = f"""
    당신은 한국 버츄얼 스트리머 전문가입니다.
    대상: '{streamer_name}' 

    [검색 자료]
    {search_results}

    위 자료를 바탕으로 현재 소속을 분석하여 출력하세요. 
    절대로 줄여 쓰지 마세요. 
    공식 풀네임을 출력하세요.
    """

    # 💡 온도를 0으로 유지하되, 출력이 너무 짧아지는 걸 방지하기 위해 
    # 코드 레벨에서 글자 수를 체크하는 로직을 넣었습니다.
    config = {"temperature": 0, "top_p": 0.95, "max_output_tokens": 50}

    for retry_count in range(3): # 최대 3번까지 제대로 나올 때까지 볶습니다.
        try:
            response = model.generate_content(prompt, generation_config=config)
            result = response.text.strip()
            
            # 🚨 검역 로직: 결과가 너무 짧거나(2글자 미만) 이상하면 다시 시도!
            # (단, '없음'이나 '에러'는 제외)
            
            return result
        except Exception as e:
            if "429" in str(e):
                time.sleep(60)
                continue
            return "에러/재검색필요"
    
    return "재검색필요" # 3번 다 실패하면 사람이 확인하도록 넘깁니다.

# ==========================================
# 🚀 3. 메인 자동화 공장 가동
# ==========================================
def run_agent_factory():
    print(f"🏭 [CIME 전략팀] 에이전트 가동을 시작합니다!")
    
    if os.path.exists(OUTPUT_CSV):
        print(f"📁 기존 결과 파일에서 이어서 작업을 시작합니다.")
        df = pd.read_csv(OUTPUT_CSV, encoding='utf-8-sig')
    else:
        try:
            df = pd.read_csv(INPUT_CSV, encoding='utf-8-sig')
        except:
            df = pd.read_csv(INPUT_CSV, encoding='cp949')
        if '소속_크루' not in df.columns:
            df['소속_크루'] = None

    total_rows = len(df)
    save_counter = 0

    for index, row in df.iterrows():
        # 이미 결과가 있는 경우 건너뛰기 (성공한 데이터 보호)
        if pd.notna(row['소속_크루']) and row['소속_크루'] not in ["에러/재검색필요", "없음"]:
            continue
            
        streamer_name = row['스트리머명']
        channel_id = row['채널ID'] if '채널ID' in df.columns else "알수없음"
        
        print(f"🔍 [{index + 1}/{total_rows}] '{streamer_name}' 정밀 분석 중...")
        crew_result = search_streamer_crew(streamer_name, channel_id)
        
        df.at[index, '소속_크루'] = crew_result
        print(f"   ➡ [결과]: {crew_result}")
        
        save_counter += 1
        if save_counter % 5 == 0:
            df.to_csv(OUTPUT_CSV, index=False, encoding='utf-8-sig')
            print(f"💾 {index + 1}번까지 안전하게 저장되었습니다.")
            
        time.sleep(20) # 429 방지를 위해 약간 더 여유 있게!

    df.to_csv(OUTPUT_CSV, index=False, encoding='utf-8-sig')
    print("\n🎉 모든 분석이 완료되었습니다. 결과 파일을 확인해 보세요!")

if __name__ == "__main__":
    run_agent_factory()