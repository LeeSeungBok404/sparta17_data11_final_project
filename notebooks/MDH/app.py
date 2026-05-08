import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from textwrap import dedent
import base64
from urllib.parse import quote


# ============================================================
# 페이지 설정
# ============================================================
st.set_page_config(page_title="CIME STREAM PLANET", layout="wide")


# ============================================================
# CSS
# ============================================================
st.markdown(dedent("""
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">

<style>
.stApp {
    background:
        radial-gradient(circle at top left, rgba(0, 242, 255, 0.16), transparent 30%),
        radial-gradient(circle at top right, rgba(191, 64, 191, 0.16), transparent 28%),
        radial-gradient(circle at bottom, rgba(255, 188, 0, 0.08), transparent 35%),
        #05070a;
    color: white;
}

.main {
    background-color: #05070a;
    color: #ffffff;
    font-family: 'Pretendard', sans-serif;
}

div[data-testid="column"] {
    padding: 10px;
}

/* KPI 카드 */
.stMetric {
    background: rgba(255,255,255,0.05);
    padding: 15px;
    border-radius: 12px;
    border: 1px solid #1e2631;
    color: white;
}

/* 세그먼트 전략 카드 */
.segment-card {
    background: rgba(17, 20, 24, 0.92);
    border: 1px solid #2d333b;
    border-radius: 16px;
    padding: 18px 14px;
    transition: 0.3s;
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
    min-height: 185px;
}

.segment-card.active {
    border-color: #ffbc00;
    box-shadow: 0 0 18px rgba(255, 188, 0, 0.45);
    transform: translateY(-2px);
}

.segment-card i {
    margin-bottom: 12px;
    color: #8b949e;
}

.segment-card.active i {
    color: #ffbc00;
}

.seg-name {
    font-size: 18px;
    font-weight: bold;
    margin-bottom: 5px;
    color: #ffffff;
}

.segment-card.active .seg-name {
    color: #ffbc00;
}

.seg-count {
    font-size: 24px;
    font-weight: 800;
    color: #ffbc00;
    margin-bottom: 8px;
}

.seg-desc {
    font-size: 12px;
    color: #8b949e;
    line-height: 1.5;
    white-space: pre-wrap;
}

/* 인물 카드 */
.rank-card {
    background: rgba(17, 20, 24, 0.92);
    border-radius: 20px;
    padding: 20px;
    text-align: center;
    border: 1px solid #2d333b;
    position: relative;
    transition: 0.3s;
    min-height: 250px;
}

.rank-card:hover {
    border-color: #00f2ff;
    box-shadow: 0 0 15px rgba(0, 242, 255, 0.4);
    transform: translateY(-2px);
}

.rank-badge {
    position: absolute;
    top: 14px;
    left: 14px;
    width: 32px;
    height: 32px;
    padding: 0;
    border-radius: 9px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 800;
    font-size: 19px;
}

.rank-normal {
    background: #2d333b;
    color: #fff;
}

                   .rank-gold {
    background: linear-gradient(135deg, #FFD700, #C99700);
    color: #1a1a1a;
    box-shadow: 0 0 12px rgba(255, 215, 0, 0.55);
}

.rank-silver {
    background: linear-gradient(135deg, #E5E7EB, #9CA3AF);
    color: #1a1a1a;
    box-shadow: 0 0 12px rgba(229, 231, 235, 0.45);
}

.rank-bronze {
    background: linear-gradient(135deg, #CD7F32, #8B4513);
    color: #ffffff;
    box-shadow: 0 0 12px rgba(205, 127, 50, 0.45);
}

.avatar-circle {
    width: 100px;
    height: 100px;
    border-radius: 50%;
    margin: 0 auto 15px;
    border: 3px solid #1e2631;
    background: #05070a;
    overflow: hidden;
}

.avatar-circle img {
    width: 100%;
    height: 100%;
    object-fit: cover;
}

/* 태그 */
.tag-segment {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 11px;
    font-weight: bold;
    margin-top: 8px;
}

.tag-슈퍼노바 {
    background: rgba(255, 75, 75, 0.2);
    color: #ff4b4b;
    border: 1px solid #ff4b4b;
}

.tag-성단 {
    background: rgba(255, 188, 0, 0.2);
    color: #ffbc00;
    border: 1px solid #ffbc00;
}

.tag-화이트홀 {
    background: rgba(0, 242, 255, 0.2);
    color: #00f2ff;
    border: 1px solid #00f2ff;
}

.tag-프로토스타 {
    background: rgba(0, 255, 135, 0.2);
    color: #00ff87;
    border: 1px solid #00ff87;
}

.tag-코멧 {
    background: rgba(191, 64, 191, 0.2);
    color: #bf40bf;
    border: 1px solid #bf40bf;
}

/* 사이드바 */
[data-testid="stSidebar"] {
    background-color: #0d1117;
    border-left: 1px solid #30363d;
}

/* 사이드바가 열려 있을 때만 넓게 */
[data-testid="stSidebar"][aria-expanded="true"] {
    min-width: 380px;
    max-width: 380px;
}

/* 사이드바 내부 콘텐츠도 열려 있을 때만 넓게 */
[data-testid="stSidebar"][aria-expanded="true"] > div:first-child {
    min-width: 380px;
    max-width: 380px;
}

/* 테이블 */
.custom-table {
    width: 100%;
    border-collapse: collapse;
    margin-top: 10px;
}

.custom-table th {
    text-align: left;
    padding: 12px;
    border-bottom: 2px solid #1e2631;
    color: #8b949e;
    font-size: 13px;
}

.custom-table td {
    padding: 12px;
    border-bottom: 1px solid #1e2631;
    font-size: 14px;
    color: white;
}

/* 버튼 */
div.stButton > button {
    background: rgba(255, 255, 255, 0.06);
    color: #ffffff;
    border: 1px solid #2d333b;
    border-radius: 12px;
    padding: 8px 12px;
    font-weight: 700;
    transition: 0.25s;
}

div.stButton > button:hover {
    background: rgba(0, 242, 255, 0.12);
    color: #00f2ff;
    border-color: #00f2ff;
    box-shadow: 0 0 10px rgba(0, 242, 255, 0.25);
}
                   
                   /* 사이드바 안의 닫기 버튼 좌우 마진 */
[data-testid="stSidebar"] div.stButton > button {
    width: calc(100% - 32px);
    margin-left: 20px;
    margin-right: 20px;
}
                   
</style>
"""), unsafe_allow_html=True)

def img_to_base64(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()

# ============================================================
# 헤더
# ============================================================

title_icon = img_to_base64("assets/제목아이콘.png")
date_icon = img_to_base64("assets/달력.png")

st.markdown(
    f"""
    <div style="
        display: flex;
        align-items: center;
        gap: 12px;
        margin-bottom: 0px;
    ">
        <img src="data:image/png;base64,{title_icon}" 
             style="width: 42px; height: 42px; object-fit: contain;">
        <h1 style="
            margin: 0;
            color: white;
            font-size: 42px;
            font-weight: 800;
        ">
            CIME STREAM PLANET
        </h1>
    </div>
    """,
    unsafe_allow_html=True
)

st.markdown(
    f"""
    <div style="
        text-align: right;
        color: #c9d1d9;
        font-size: 16px;
        font-weight: 600;
        margin-top: -6px;
        margin-bottom: 18px;
        padding-right: 20px;
        white-space: nowrap;
    ">
        <img src="data:image/png;base64,{date_icon}" 
             style="width: 18px; height: 18px; object-fit: contain; vertical-align: -3px; margin-right: 6px;">
        2025.01.01 ~ 2026.03.31
    </div>
    """,
    unsafe_allow_html=True
)


# ============================================================
# KPI 요약
# ============================================================
k1, k2, k3 = st.columns(3)

with k1:
    st.metric("총 분석 스트리머 수", "1,240 명")

with k2:
    st.metric("평균 뷰어십", "237,712")

with k3:
    st.metric("평균 도네이션", "₩ 4,884,841")

st.write("")


# ============================================================
# 임시 데이터 생성
# ============================================================
@st.cache_data
def get_mock_data():
    np.random.seed(42)

    segments = ["슈퍼노바", "성단", "화이트홀", "프로토스타", "코멧"]
    data = []

    for s in segments:
        for i in range(10):
            score = np.random.uniform(70, 98, 1).round(1)[0]

            if s == "슈퍼노바":
                segment_filter_value = np.random.choice(["그룹", "개인"])
            elif s == "코멧":
                segment_filter_value = np.random.choice(["X 강세형", "유튜브 강세형", "하이브리드"])
            else:
                segment_filter_value = "해당 없음"

            data.append({
                "순위": 0,
                "스트리머": f"스트리머_{s}_{i}",
                "플랫폼": np.random.choice(["SOOP", "치지직"]),
                "세그먼트": s,
                "세그먼트필터": segment_filter_value,
                "스코어": score,
                "뷰어십": np.random.randint(20000, 150000),
                "도네이션": np.random.randint(1000000, 50000000),
                "방송시간": np.random.randint(80, 250),
                "평균시청자": np.random.randint(2000, 20000),
                "최고시청자": np.random.randint(5000, 50000),
                "특징": "압도적 성장세, 충성 팬덤 보유"
            })

    return pd.DataFrame(data)


df = get_mock_data()


# ============================================================
# 상태 관리
# ============================================================
if "current_seg" not in st.session_state:
    st.session_state.current_seg = "슈퍼노바"

if "show_sidebar" not in st.session_state:
    st.session_state.show_sidebar = False

if "selected_streamer" not in st.session_state:
    st.session_state.selected_streamer = None


# ============================================================
# 세그먼트 전략 카드
# ============================================================
st.write("### 🛸 세그먼트 전략")

seg_data = {
    "슈퍼노바": {
        "icon": "fa-solid fa-star",
        "count": "173명",
        "desc": "고성장 유망주\n팬카페 상위 10%\n고성장 특이 후보"
    },
    "성단": {
        "icon": "fa-solid fa-users",
        "count": "549명",
        "desc": "최상위 체급\n팬덤지수 상위 20%\n안정적 1군"
    },
    "화이트홀": {
        "icon": "fa-solid fa-sun",
        "count": "945명",
        "desc": "도네이션 상위 10%\n채팅 활성 상위 20%"
    },
    "프로토스타": {
        "icon": "fa-solid fa-leaf",
        "count": "1,577명",
        "desc": "성장 잠재력\n팔로워 상승세"
    },
    "코멧": {
        "icon": "fa-solid fa-meteor",
        "count": "1,118명",
        "desc": "유튜브 유입\n외부 팬덤 강세 후보"
    },
}

segments = list(seg_data.keys())

query_seg = st.query_params.get("seg")

if query_seg in segments and query_seg != st.session_state.current_seg:
    st.session_state.current_seg = query_seg
    st.session_state.show_sidebar = False
    st.session_state.selected_streamer = None

seg_cols = st.columns(5)

for i, seg in enumerate(segments):
    with seg_cols[i]:
        info = seg_data[seg]
        active_class = "active" if st.session_state.current_seg == seg else ""
        seg_url = quote(seg)

        segment_card_html = (
            f'<a href="?seg={seg_url}" target="_self" style="text-decoration:none;">'
            f'<div class="segment-card {active_class}" style="cursor:pointer;">'
            f'<i class="{info["icon"]} fa-2x"></i>'
            f'<div class="seg-name">{seg}</div>'
            f'<div class="seg-count">{info["count"]}</div>'
            f'<div class="seg-desc">{info["desc"]}</div>'
            f'</div>'
            f'</a>'
        )

        st.markdown(segment_card_html, unsafe_allow_html=True)


st.write("---")


# ============================================================
# 필터 영역
# ============================================================
if st.session_state.current_seg in ["슈퍼노바", "코멧"]:
    f1, f2, _ = st.columns([1, 1, 2])
else:
    f1, _, _ = st.columns([1, 1, 2])

platform_filter = f1.selectbox(
    "플랫폼 필터",
    ["전체", "SOOP", "치지직"]
)

segment_detail_filter = "전체"

if st.session_state.current_seg == "슈퍼노바":
    segment_detail_filter = f2.selectbox(
        "세그먼트 필터",
        ["전체", "그룹", "개인"]
    )

elif st.session_state.current_seg == "코멧":
    segment_detail_filter = f2.selectbox(
        "세그먼트 필터",
        ["전체", "X 강세형", "유튜브 강세형", "하이브리드"]
    )


# ============================================================
# 데이터 필터링
# ============================================================
filtered_df = df[df["세그먼트"] == st.session_state.current_seg].copy()

if platform_filter != "전체":
    filtered_df = filtered_df[filtered_df["플랫폼"] == platform_filter].copy()

if segment_detail_filter != "전체":
    filtered_df = filtered_df[filtered_df["세그먼트필터"] == segment_detail_filter].copy()

filtered_df = filtered_df.sort_values("스코어", ascending=False).reset_index(drop=True)
filtered_df["순위"] = filtered_df.index + 1

top_5 = filtered_df.head(5)

# ============================================================
# TOP 5 카드
# ============================================================
st.write(f"### 🏆 **{st.session_state.current_seg}** TOP 5")

if top_5.empty:
    st.warning("선택한 조건에 해당하는 스트리머가 없습니다.")

else:
    card_cols = st.columns(5)

    for i, (_, row) in enumerate(top_5.iterrows()):
        avatar_url = f"https://api.dicebear.com/7.x/avataaars/svg?seed={row['스트리머']}"

        rank_class = "rank-normal"

        if i == 0:
            rank_class = "rank-gold"
        elif i == 1:
            rank_class = "rank-silver"
        elif i == 2:
            rank_class = "rank-bronze"

        card_html = (
            f'<div class="rank-card">'
            f'<div class="rank-badge {rank_class}">{i + 1}</div>'
            f'<div class="avatar-circle">'
            f'<img src="{avatar_url}" alt="avatar">'
            f'</div>'
            f'<div style="font-weight:bold; font-size:18px;">{row["스트리머"]}</div>'
            f'<div class="tag-segment tag-{row["세그먼트"]}">{row["세그먼트"]}</div>'
            f'<div style="margin-top:15px; font-size:12px; color:#8b949e;">종합 스코어</div>'
            f'<div style="font-size:24px; font-weight:800; color:#ffbc00;">{row["스코어"]}</div>'
            f'</div>'
        )

        with card_cols[i]:
            st.markdown(card_html, unsafe_allow_html=True)

            if st.button("상세 보기", key=f"card_btn_{i}", use_container_width=True):
                st.session_state.selected_streamer = row.to_dict()
                st.session_state.show_sidebar = True
                st.rerun()


# ============================================================
# 사이드바 상세 정보
# ============================================================
if st.session_state.show_sidebar and st.session_state.selected_streamer is not None:
    with st.sidebar:
        s = st.session_state.selected_streamer
        avatar_url = f"https://api.dicebear.com/7.x/avataaars/svg?seed={s['스트리머']}"

        sidebar_header_html = (
            f'<div style="text-align:center; padding:30px 0 10px;">'
            f'<div class="avatar-circle" style="width:130px; height:130px; border:4px solid #00f2ff;">'
            f'<img src="{avatar_url}" alt="avatar">'
            f'</div>'
            f'<h2 style="margin-bottom:5px;">'
            f'{s["스트리머"]} '
            f'<div style="display:flex; justify-content:center; gap:8px; align-items:center; flex-wrap:wrap;">'
            f'<span class="tag-segment tag-{s["세그먼트"]}">{s["세그먼트"]}</span>'
            f'<span style="color:#8b949e; font-size:14px;">{s["플랫폼"]}</span>'
            f'</div>'
            f'</div>'
        )

        st.markdown(sidebar_header_html, unsafe_allow_html=True)

        st.write("---")

        metrics = {
            "뷰어십 점수": (s["뷰어십"], 150000, "#ff4b4b"),
            "도네이션 점수": (s["도네이션"], 50000000, "#ffbc00"),
            "방송시간 점수": (s["방송시간"], 300, "#00ff87"),
            "평균 시청자": (s["평균시청자"], 20000, "#00f2ff"),
            "최고 시청자": (s["최고시청자"], 50000, "#bf40bf")
        }

        for m_name, (val, max_val, color) in metrics.items():
            percent = min(val / max_val, 1.0) * 100
            val_text = f"{val:,.0f}"

            metric_html = (
                f'<div style="margin:0 20px 18px 20px;">'

            #    지표명
                f'<div style="font-size:14px; font-weight:bold; margin-bottom:5px; color:white;">'
                f'{m_name}'
                f'</div>'

                # 바 + 수치
                f'<div style="display:flex; align-items:center; gap:10px;">'

                # 바 전체 영역
                f'<div style="flex:1; background:rgba(255,255,255,0.05); height:8px; border-radius:4px; overflow:hidden;">'
                f'<div style="background:{color}; height:100%; border-radius:4px; width:{percent}%;"></div>'
                f'</div>'

                # 수치
                f'<div style="min-width:105px; text-align:right; font-size:15px; font-weight:800; color:{color};">'
                f'{val_text}'
                f'</div>'

                f'</div>'
                f'</div>'
            )

            st.markdown(metric_html, unsafe_allow_html=True)

        st.write("")
        

        if st.button("상세 정보 닫기", use_container_width=True):
            st.session_state.show_sidebar = False
            st.session_state.selected_streamer = None
            st.rerun()


# ============================================================
# 하단 TOP 10 리스트 & 그래프
# ============================================================
st.write("---")

col_left, col_right = st.columns([1.5, 1])

with col_left:
    st.subheader(f"📋 **{st.session_state.current_seg}** 영입 우선순위 리스트")

    table_html = "<table class='custom-table'><thead><tr>"
    table_html += "<th>순위</th><th>스트리머명</th><th>플랫폼</th><th>스코어</th><th>뷰어십(Bar)</th><th>특징</th>"
    table_html += "</tr></thead><tbody>"

    for _, row in filtered_df.head(10).iterrows():
        bar_width = min((row["뷰어십"] / 150000) * 100, 100)

        table_html += "<tr>"
        table_html += f"<td>{row['순위']}</td>"
        table_html += f"<td><b>{row['스트리머']}</b></td>"
        table_html += f"<td><span class='tag-segment tag-{row['세그먼트']}'>{row['플랫폼']}</span></td>"
        table_html += f"<td style='color:#00f2ff; font-weight:bold;'>{row['스코어']}</td>"
        table_html += "<td style='width:150px;'>"
        table_html += "<div style='background:#1e2631; width:100%; height:8px; border-radius:4px;'>"
        table_html += f"<div style='background:#818cf8; width:{bar_width}%; height:100%; border-radius:4px;'></div>"
        table_html += "</div>"
        table_html += "</td>"
        table_html += f"<td style='font-size:12px; color:#8b949e;'>{row['특징']}</td>"
        table_html += "</tr>"

    table_html += "</tbody></table>"

    st.markdown(table_html, unsafe_allow_html=True)


with col_right:
    st.subheader(f"🌌 **{st.session_state.current_seg}** 세그먼트 분석 분포")

    if filtered_df.empty:
        st.warning("그래프를 표시할 데이터가 없습니다.")
    else:
        fig = px.scatter(
            filtered_df,
            x="평균시청자",
            y="스코어",
            size="뷰어십",
            color="플랫폼",
            hover_name="스트리머",
            color_discrete_map={
                "SOOP": "#00f2ff",
                "치지직": "#bf40bf"
            },
            template="plotly_dark"
        )

        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=0, r=0, t=20, b=0),
            font_color="white"
        )

        st.plotly_chart(fig, use_container_width=True)