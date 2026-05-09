
import random
import textwrap

import streamlit as st


st.set_page_config(
    page_title="CIME MISSION CONTROL",
    layout="wide",
    initial_sidebar_state="expanded",
)

if "page" not in st.session_state:
    st.session_state.page = "대시보드 홈"

if "card" not in st.session_state:
    st.session_state.card = None

if "bg_html" not in st.session_state:
    random.seed(42)
    stars = []
    for _ in range(230):
        size = random.uniform(1.2, 4.2)
        x = random.uniform(0, 100)
        y = random.uniform(0, 100)
        delay = random.uniform(0, 7)
        duration = random.uniform(2.0, 6.0)
        opacity = random.uniform(0.65, 1.0)
        stars.append(
            f'<div class="twinkle-star" style="'
            f'width:{size:.1f}px;height:{size:.1f}px;'
            f'left:{x:.1f}%;top:{y:.1f}%;'
            f'--max-opacity:{opacity:.2f};'
            f'animation-delay:{delay:.1f}s;'
            f'animation-duration:{duration:.1f}s;"></div>'
        )
    st.session_state.bg_html = "".join(stars)


STARTRAIL_SEGMENTS = [
    {
        "num": "01",
        "ko": "성단",
        "en": "Star Cluster",
        "icon": "⭐",
        "icon_class": "icon-cluster",
        "purpose": '팬덤이 함께 이동할 가능성이 높은<br><span class="purpose-key">그룹형 후보군</span>',
        "criteria": "그룹/소속성, 팬덤 결집, 멤버 단위 이동 가능성",
        "point": "여러 스트리머와 팬덤을 함께 유입시켜 초기 트래픽을 빠르게 확보합니다.",
    },
    {
        "num": "02",
        "ko": "프로토스타",
        "en": "Protostar",
        "icon": "🌱",
        "icon_class": "icon-protostar",
        "purpose": '현재 규모는 작지만 방송 반응이 좋은<br><span class="purpose-key">성장형 후보군</span>',
        "criteria": "시청자 반응, 채팅, 뷰어십, 팔로워 대비 성과",
        "point": "성장 가능성이 높은 후보를 조기에 발굴해 CIME의 육성 타깃으로 활용합니다.",
    },
    {
        "num": "03",
        "ko": "위성",
        "en": "Satellite",
        "icon": "🛰️",
        "icon_class": "icon-satellite",
        "purpose": '소속 없이도 방송 성과가 검증된<br><span class="purpose-key">개인형 후보군</span>',
        "criteria": "도네이션, 채팅화력, 평균 시청자, 개인 활동 여부",
        "point": "검증된 개인 방송 화력을 바탕으로 안정적인 콘텐츠와 수익성을 확보합니다.",
    },
    {
        "num": "04",
        "ko": "슈퍼노바",
        "en": "Supernova",
        "icon": "💥",
        "icon_class": "icon-supernova",
        "purpose": '대중성과 팬덤 규모가 큰<br><span class="purpose-key">간판형 후보군</span>',
        "criteria": "팔로워, 최고 시청자, 유튜브 구독자, 팬덤지수, 방송화력",
        "point": "인지도 높은 스트리머를 통해 플랫폼 주목도와 외부 유입을 높입니다.",
    },
    {
        "num": "05",
        "ko": "코멧",
        "en": "Comet",
        "icon": "☄️",
        "icon_class": "icon-comet",
        "purpose": '방송 외 다른곳에서 인지도가 높은<br><span class="purpose-key">발견형 후보군</span>',
        "criteria": "유튜브 구독자, X 팔로워, 유튜브/X 유입지수, 플랫폼 대비 외부 체급",
        "point": "외부 팬덤을 CIME으로 연결해 새로운 이용자 유입을 만듭니다.",
    },
]

TRAIL_ICON_HTML = """
<div class="trail-spark-icon">
    <div class="trail-line trail-line-1"></div>
    <div class="trail-line trail-line-2"></div>
    <div class="trail-line trail-line-3"></div>
    <div class="trail-star trail-star-main">✦</div>
    <div class="trail-star trail-star-small">✦</div>
    <div class="trail-star trail-star-tiny">✦</div>
    <div class="trail-dot trail-dot-1"></div>
    <div class="trail-dot trail-dot-2"></div>
</div>
"""

SEED_ICON_HTML = """
<div class="seed-search-icon">
    <div class="seed-lens"></div>
    <div class="seed-handle"></div>
    <div class="seed-star-core">✦</div>
    <div class="seed-sparkle-1">✦</div>
    <div class="seed-sparkle-2">✦</div>
    <div class="seed-dot-1"></div>
    <div class="seed-dot-2"></div>
</div>
"""


STAR_SEED_CARDS = [
    {
        "num": "01",
        "icon": "search",
        "title": "후보 수집 기준",
        "desc": "유튜브 활동 채널 중<br>영입 검토 가능한 후보를 모읍니다.",
    },
    {
        "num": "02",
        "icon": "chat",
        "title": "팬 반응 밀도",
        "desc": "조회수 대비 좋아요·댓글로<br>팬덤 반응 강도를 봅니다.",
    },
    {
        "num": "03",
        "icon": "live",
        "title": "라이브 전환성",
        "desc": "콘텐츠 유형과 라이브 신호로<br>방송 전환 가능성을 봅니다.",
    },
    {
        "num": "04",
        "icon": "filter",
        "title": "실전 리스크",
        "desc": "기관·방송사·팬클립 등<br>영입 제외 대상을 구분합니다.",
    },
    {
        "num": "05",
        "icon": "check",
        "title": "액션버킷",
        "desc": "점수와 리스크를 함께 보고<br>검토 우선순위를 나눕니다.",
    },
]



def clean_html(markup: str) -> str:
    """Markdown이 HTML을 코드블록으로 오해하지 않도록 줄 앞 공백을 제거한다."""
    return "\n".join(line.strip() for line in textwrap.dedent(markup).strip().splitlines())


def html(markup: str) -> None:
    st.markdown(clean_html(markup), unsafe_allow_html=True)


st.markdown(
    clean_html(
        """
        <style>
        #MainMenu { visibility: hidden; }
        footer { visibility: hidden; }

        .stApp {
            background:
                radial-gradient(circle at 56% 31%, rgba(127, 47, 255, 0.42), transparent 28%),
                radial-gradient(circle at 60% 79%, rgba(121, 51, 255, 0.16), transparent 32%),
                linear-gradient(180deg, #050411 0%, #09051C 52%, #050411 100%);
            color: #F8F2FF;
        }

        [data-testid="stHeader"] {
            background: rgba(8, 12, 22, 0.96);
        }

        .block-container {
            max-width: 1540px;
            padding-top: 2.2rem;
            padding-left: 4.7rem;
            padding-right: 4.7rem;
            padding-bottom: 5rem;
        }

        h1, h2, h3, p {
            color: inherit;
        }

        .star-layer {
            position: fixed;
            left: 300px;
            top: 0;
            right: 0;
            bottom: 0;
            pointer-events: none;
            z-index: 0;
            overflow: hidden;
        }

        .twinkle-star {
            position: absolute;
            border-radius: 50%;
            background: white;
            pointer-events: none;
            z-index: 0;
            box-shadow:
                0 0 10px rgba(255,255,255,0.95),
                0 0 20px rgba(198,168,255,0.60);
            animation-name: twinkle;
            animation-timing-function: ease-in-out;
            animation-iteration-count: infinite;
        }

        .twinkle-star:nth-child(3n) {
            background: #C8A8FF;
            box-shadow:
                0 0 12px rgba(200,168,255,0.95),
                0 0 25px rgba(139,92,255,0.58);
        }

        .twinkle-star:nth-child(5n) {
            background: #FF9DF5;
            box-shadow:
                0 0 12px rgba(255,157,245,0.95),
                0 0 25px rgba(255,120,230,0.50);
        }

        @keyframes twinkle {
            0%, 100% {
                opacity: 0.16;
                transform: scale(0.65);
                filter: brightness(0.75);
            }
            45% {
                opacity: var(--max-opacity);
                transform: scale(1.50);
                filter: brightness(1.7);
            }
            65% {
                opacity: 0.45;
                transform: scale(0.95);
                filter: brightness(1.05);
            }
        }

        .orbit-bg {
            position: fixed;
            left: 300px;
            top: 0;
            right: 0;
            bottom: 0;
            z-index: 0;
            pointer-events: none;
            opacity: 0.42;
            background:
                linear-gradient(150deg, transparent 15%, rgba(157, 88, 255, 0.13) 15.4%, transparent 16.5%),
                linear-gradient(150deg, transparent 34%, rgba(157, 88, 255, 0.09) 34.4%, transparent 35.5%),
                linear-gradient(150deg, transparent 54%, rgba(238, 142, 255, 0.08) 54.4%, transparent 55.5%);
            animation: drift 9s ease-in-out infinite alternate;
        }

        @keyframes drift {
            from { transform: translateY(0px); opacity: 0.28; }
            to { transform: translateY(-18px); opacity: 0.48; }
        }

        [data-testid="stSidebar"] {
            background: #0A061E;
            border-right: 1px solid rgba(154, 98, 255, 0.45);
        }

        [data-testid="stSidebar"] > div:first-child {
            padding-top: 4.4rem;
        }

        .sidebar-title {
            font-size: 22px;
            font-weight: 900;
            letter-spacing: 1px;
            color: #FFF9FF;
            margin-bottom: 18px;
        }

        .sidebar-subtitle {
            font-size: 10px;
            font-weight: 800;
            letter-spacing: 1.2px;
            color: #D9C8FF;
            margin-bottom: 64px;
        }

        .sidebar-line {
            height: 1px;
            background: rgba(185, 147, 255, 0.28);
            margin: 0 0 24px 0;
        }

        section[data-testid="stSidebar"] .stButton > button {
            width: 100%;
            height: 43px;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 850;
            letter-spacing: -0.3px;
            margin-bottom: 8px;
            transition: all 0.18s ease;
        }

        section[data-testid="stSidebar"] .stButton > button[kind="primary"] {
            background: #7D42FF !important;
            color: white !important;
            border: 1px solid rgba(229,155,255,0.65) !important;
            box-shadow: 0 0 18px rgba(125,66,255,0.25);
        }

        section[data-testid="stSidebar"] .stButton > button[kind="secondary"] {
            background: rgba(255,255,255,0.93) !important;
            color: #251A42 !important;
            border: 1px solid rgba(184,165,217,0.42) !important;
        }

        section[data-testid="stSidebar"] .stButton > button:hover {
            transform: translateY(-1px);
            box-shadow: 0 0 18px rgba(125,66,255,0.32);
        }

        .main-wrap {
            position: relative;
            z-index: 2;
            text-align: center;
        }

        .hero-title {
            font-size: 58px;
            font-weight: 950;
            letter-spacing: 9px;
            line-height: 1;
            color: #FFF8FF;
            text-shadow: 0 0 22px rgba(230, 195, 255, 0.35);
            margin-top: 4px;
            margin-bottom: 14px;
        }

        .hero-subtitle {
            font-size: 19px;
            font-weight: 750;
            color: #C6BBD9;
            margin-bottom: 10px;
        }

        .planet-area {
            position: relative;
            height: 360px;
            display: flex;
            align-items: center;
            justify-content: center;
            margin-top: -10px;
            margin-bottom: 12px;
        }

        .planet-glow {
            position: absolute;
            width: 470px;
            height: 470px;
            border-radius: 50%;
            background: radial-gradient(circle, rgba(139,53,255,0.45) 0%, rgba(139,53,255,0.18) 34%, transparent 68%);
            filter: blur(14px);
            animation: planetPulse 4s ease-in-out infinite alternate;
        }

        @keyframes planetPulse {
            from { opacity: 0.78; transform: scale(0.98); }
            to { opacity: 1; transform: scale(1.03); }
        }

        .planet-orbit {
            position: absolute;
            width: 840px;
            height: 235px;
            border: 2px solid rgba(179,93,255,0.46);
            border-radius: 50%;
            transform: rotate(-2deg);
            box-shadow: 0 0 26px rgba(179,93,255,0.16);
        }

        .planet-orbit.orbit-2 {
            width: 660px;
            height: 185px;
            border-color: rgba(239,156,255,0.42);
            transform: rotate(1deg);
        }

        .planet-orbit.orbit-3 {
            width: 980px;
            height: 310px;
            border-color: rgba(125,66,255,0.20);
            transform: rotate(-4deg);
        }

        .planet {
            position: relative;
            width: 320px;
            height: 320px;
            border-radius: 50%;
            background:
                radial-gradient(circle at 72% 28%, rgba(246,166,255,0.55), transparent 20%),
                radial-gradient(circle at 58% 44%, rgba(147,55,255,0.95), transparent 38%),
                radial-gradient(circle at 42% 58%, rgba(42,8,110,0.95), transparent 48%),
                radial-gradient(circle at 50% 50%, #4812A7 0%, #270066 48%, #08011B 100%);
            box-shadow:
                0 0 34px rgba(246,166,255,0.62),
                0 0 100px rgba(139,53,255,0.55),
                inset 22px 18px 48px rgba(255,170,255,0.20),
                inset -48px -44px 78px rgba(0,0,0,0.55);
            overflow: hidden;
            animation: floatPlanet 5.4s ease-in-out infinite alternate;
        }

        @keyframes floatPlanet {
            from { transform: translateY(0px); }
            to { transform: translateY(-10px); }
        }

        .planet::before {
            content: "";
            position: absolute;
            inset: 0;
            border-radius: 50%;
            background:
                radial-gradient(ellipse at 32% 25%, rgba(20,0,70,0.70) 0 7%, transparent 14%),
                radial-gradient(ellipse at 62% 20%, rgba(25,0,72,0.68) 0 8%, transparent 15%),
                radial-gradient(ellipse at 45% 45%, rgba(105,32,205,0.35) 0 8%, transparent 18%),
                radial-gradient(ellipse at 70% 58%, rgba(12,0,38,0.54) 0 10%, transparent 19%),
                radial-gradient(ellipse at 31% 70%, rgba(96,24,190,0.32) 0 9%, transparent 18%),
                linear-gradient(178deg, transparent 0%, rgba(255,132,255,0.12) 45%, transparent 49%, rgba(0,0,0,0.22) 80%);
            filter: blur(0.4px);
            opacity: 0.9;
        }

        .planet::after {
            content: "";
            position: absolute;
            inset: 6px;
            border-radius: 50%;
            border-top: 5px solid rgba(246,166,255,0.72);
            border-right: 4px solid rgba(246,166,255,0.35);
            box-shadow: inset -48px -44px 70px rgba(0,0,0,0.35);
        }

        .planet-logo {
            position: absolute;
            inset: 0;
            z-index: 2;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 48px;
            font-weight: 950;
            letter-spacing: 5px;
            color: #FFF8FF;
            text-shadow:
                0 0 10px rgba(255,255,255,0.85),
                0 0 22px rgba(234,203,255,0.9),
                0 0 40px rgba(179,93,255,0.8);
        }

        .satellite {
            position: absolute;
            width: 16px;
            height: 16px;
            border-radius: 50%;
            box-shadow: 0 0 18px currentColor;
        }

        .sat-1 { color: #FF6BF1; background: #FF6BF1; transform: translate(365px, 8px); }
        .sat-2 { color: #FFD45D; background: #FFD45D; transform: translate(-350px, 62px); }
        .sat-3 { color: #95AFFF; background: #95AFFF; transform: translate(-240px, -66px); }
        .sat-4 { color: #C681FF; background: #C681FF; transform: translate(240px, -62px); }

        div[data-testid="column"] {
            position: relative;
            z-index: 4;
        }

        .mission-card {
            min-height: 255px;
            border-radius: 26px;
            background: rgba(21, 16, 47, 0.90);
            border: 1px solid rgba(255,255,255,0.08);
            box-shadow:
                0 0 28px rgba(112, 53, 255, 0.18),
                inset 0 0 28px rgba(255,255,255,0.025);
            padding: 28px 38px 76px;
            text-align: left;
            position: relative;
            overflow: hidden;
        }

        .mission-card::before {
            content: "";
            position: absolute;
            left: 28px;
            right: 28px;
            top: 22px;
            height: 3px;
            border-radius: 3px;
        }

        .trail-card { border-color: rgba(255,212,93,0.42); }
        .seed-card { border-color: rgba(152,255,171,0.38); }

        .trail-card::before {
            background: #FFD45D;
            box-shadow: 0 0 16px rgba(255,212,93,0.55);
        }

        .seed-card::before {
            background: #98FFAB;
            box-shadow: 0 0 16px rgba(152,255,171,0.45);
        }

        .card-head {
            display: flex;
            align-items: center;
            gap: 24px;
            margin-top: 20px;
            margin-bottom: 26px;
        }

        .icon-box {
            width: 66px;
            height: 66px;
            border-radius: 18px;
            display: flex;
            align-items: center;
            justify-content: center;
            overflow: hidden;
        }

        .trail-spark-icon {
            position: relative;
            width: 56px;
            height: 56px;
            color: #FFD45D;
        }

        .trail-line {
            position: absolute;
            left: 5px;
            height: 3px;
            border-radius: 999px;
            background: currentColor;
            box-shadow: 0 0 8px rgba(255,212,93,0.28);
        }

        .trail-line-1 { top: 22px; width: 23px; opacity: 0.95; }
        .trail-line-2 { top: 31px; width: 16px; opacity: 0.72; }
        .trail-line-3 { top: 27px; left: 13px; width: 18px; opacity: 0.48; }

        .trail-star {
            position: absolute;
            color: currentColor;
            line-height: 1;
            text-shadow: 0 0 10px rgba(255,212,93,0.40);
        }

        .trail-star-main { left: 30px; top: 15px; font-size: 30px; }
        .trail-star-small { left: 23px; top: 6px; font-size: 14px; opacity: 0.95; }
        .trail-star-tiny { left: 17px; top: 38px; font-size: 10px; opacity: 0.85; }

        .trail-dot {
            position: absolute;
            width: 3px;
            height: 3px;
            border-radius: 50%;
            background: currentColor;
            box-shadow: 0 0 6px rgba(255,212,93,0.35);
        }

        .trail-dot-1 { left: 44px; top: 11px; }
        .trail-dot-2 { left: 8px; top: 40px; opacity: 0.75; }

        .seed-search-icon {
            position: relative;
            width: 56px;
            height: 56px;
            color: #98FFAB;
        }

        .seed-lens {
            position: absolute;
            left: 7px;
            top: 7px;
            width: 30px;
            height: 30px;
            border: 4px solid currentColor;
            border-radius: 50%;
            box-sizing: border-box;
            box-shadow: 0 0 10px rgba(152,255,171,0.20);
        }

        .seed-handle {
            position: absolute;
            left: 33px;
            top: 35px;
            width: 18px;
            height: 4px;
            background: currentColor;
            border-radius: 999px;
            transform: rotate(45deg);
            transform-origin: left center;
            box-shadow: 0 0 8px rgba(152,255,171,0.20);
        }

        .seed-star-core {
            position: absolute;
            left: 15px;
            top: 12px;
            font-size: 18px;
            line-height: 1;
            font-weight: 900;
            text-shadow: 0 0 10px rgba(152,255,171,0.48);
        }

        .seed-sparkle-1 {
            position: absolute;
            left: 37px;
            top: 7px;
            font-size: 12px;
            line-height: 1;
            opacity: 0.95;
        }

        .seed-sparkle-2 {
            position: absolute;
            left: 4px;
            top: 35px;
            font-size: 9px;
            line-height: 1;
            opacity: 0.78;
        }

        .seed-dot-1,
        .seed-dot-2 {
            position: absolute;
            width: 3px;
            height: 3px;
            border-radius: 50%;
            background: currentColor;
            box-shadow: 0 0 6px rgba(152,255,171,0.35);
        }

        .seed-dot-1 { left: 44px; top: 18px; }
        .seed-dot-2 { left: 11px; top: 43px; opacity: 0.8; }

        .trail-icon-box {
            background: rgba(255,212,93,0.12);
            border: 1px solid rgba(255,212,93,0.34);
        }

        .seed-icon-box {
            background: rgba(152,255,171,0.10);
            border: 1px solid rgba(152,255,171,0.30);
        }

        .css-star {
            width: 0;
            height: 0;
            color: #FFD45D;
            position: relative;
            display: block;
            border-right: 16px solid transparent;
            border-bottom: 11px solid #FFD45D;
            border-left: 16px solid transparent;
            transform: rotate(35deg);
            filter: drop-shadow(0 0 8px rgba(255,212,93,0.7));
        }

        .css-star::before {
            border-bottom: 13px solid #FFD45D;
            border-left: 5px solid transparent;
            border-right: 5px solid transparent;
            position: absolute;
            height: 0;
            width: 0;
            top: -9px;
            left: -10px;
            display: block;
            content: "";
            transform: rotate(-35deg);
        }

        .css-star::after {
            position: absolute;
            display: block;
            color: #FFD45D;
            top: 1px;
            left: -17px;
            width: 0;
            height: 0;
            border-right: 16px solid transparent;
            border-bottom: 11px solid #FFD45D;
            border-left: 16px solid transparent;
            transform: rotate(-70deg);
            content: "";
        }

        .css-seed {
            position: relative;
            width: 42px;
            height: 50px;
        }

        .css-seed::before {
            content: "";
            position: absolute;
            left: 19px;
            top: 18px;
            width: 4px;
            height: 28px;
            background: #98FFAB;
            border-radius: 4px;
            box-shadow: 0 0 10px rgba(152,255,171,0.6);
        }

        .leaf-left, .leaf-right {
            position: absolute;
            background: #98FFAB;
            box-shadow: 0 0 10px rgba(152,255,171,0.55);
        }

        .leaf-left {
            width: 28px;
            height: 18px;
            left: 1px;
            top: 7px;
            border-radius: 28px 4px 28px 4px;
            transform: rotate(20deg);
        }

        .leaf-right {
            width: 30px;
            height: 19px;
            right: 0;
            top: 4px;
            border-radius: 4px 28px 4px 28px;
            transform: rotate(-20deg);
        }

        .seed-pot {
            position: absolute;
            left: 13px;
            top: 37px;
            width: 18px;
            height: 12px;
            background: #A97767;
            border-radius: 0 0 12px 12px;
        }

        .card-title {
            font-size: 40px;
            font-weight: 950;
            color: #FFF9FF;
            line-height: 1.05;
        }

        .card-en {
            font-size: 27px;
            font-weight: 900;
            margin-top: 6px;
        }

        .trail-en { color: #FFD45D; }
        .seed-en { color: #98FFAB; }

        .card-desc {
            font-size: 19px;
            line-height: 1.7;
            color: #D9CFE8;
            font-weight: 560;
        }

        .trail-point {
            color: #FFD45D;
            font-weight: 850;
        }

        .trail-soft-point {
            color: #F6D365;
            font-weight: 700;
        }

        .seed-point {
            color: #98FFAB;
            font-weight: 700;
        }

        .seed-soft-point {
            color: #98FFAB;
            font-weight: 750;
        }

        section.main .stButton > button {
            width: 100%;
            height: 44px;
            border-radius: 15px;
            background: rgba(255,255,255,0.035) !important;
            color: #FFF9FF !important;
            border: 1px solid rgba(255,255,255,0.13) !important;
            font-size: 16px;
            font-weight: 850;
            transition: all 0.18s ease;
            margin-top: -60px;
            position: relative;
            z-index: 20;
        }

        section.main .stButton > button:hover {
            transform: translateY(-2px);
            border-color: rgba(240,140,255,0.75) !important;
            background: rgba(125, 66, 255, 0.20) !important;
            box-shadow: 0 0 20px rgba(125, 66, 255, 0.25);
            color: white !important;
        }

        .detail-box {
            position: relative;
            z-index: 3;
            max-width: 1380px;
            margin: 42px auto 0 auto;
            border-radius: 26px;
            background:
                linear-gradient(135deg, rgba(21,16,47,0.94), rgba(16,12,34,0.94));
            border: 1px solid rgba(196, 143, 255, 0.34);
            box-shadow:
                0 0 36px rgba(125, 66, 255, 0.20),
                inset 0 0 30px rgba(255,255,255,0.025);
            padding: 42px 48px 48px;
            text-align: left;
            animation: detailOpen 0.32s ease-out;
        }

        @keyframes detailOpen {
            from { opacity: 0; transform: translateY(-10px); }
            to { opacity: 1; transform: translateY(0); }
        }


        .detail-phase-head {
            display: flex;
            align-items: center;
            gap: 18px;
            margin-bottom: 24px;
        }

        .detail-phase-icon {
            width: 54px;
            height: 54px;
            display: flex;
            align-items: center;
            justify-content: center;
            flex: 0 0 auto;
            overflow: visible;
        }

        .detail-phase-icon .trail-spark-icon,
        .detail-phase-icon .seed-search-icon {
            transform: scale(0.92);
            transform-origin: center center;
        }

        .detail-phase-title-row {
            display: flex;
            align-items: baseline;
            gap: 12px;
            line-height: 1.05;
        }

        .detail-phase-ko {
            font-size: 34px;
            font-weight: 950;
            letter-spacing: -1.1px;
        }

        .detail-phase-en {
            font-size: 22px;
            font-weight: 850;
            color: rgba(255,255,255,0.90);
            letter-spacing: -0.2px;
        }

        .detail-phase-trail .detail-phase-ko {
            color: #FFD45D;
            text-shadow: 0 0 14px rgba(255,212,93,0.22);
        }

        .detail-phase-seed .detail-phase-ko {
            color: #98FFAB;
            text-shadow: 0 0 14px rgba(152,255,171,0.20);
        }
        .detail-kicker {
            font-size: 14px;
            font-weight: 950;
            letter-spacing: 2px;
            color: #DDBBFF;
            margin-bottom: 18px;
        }

        .detail-title {
            font-size: 34px;
            line-height: 1.35;
            font-weight: 950;
            color: #FFF9FF;
            margin-bottom: 24px;
        }

        .detail-text {
            font-size: 19px;
            line-height: 1.9;
            color: #D9CFE8;
            font-weight: 520;
            margin-bottom: 34px;
            word-break: keep-all;
            overflow-wrap: normal;
            letter-spacing: -0.02em;
        }

        .segment-grid,
        .seed-grid {
            display: grid;
            gap: 18px;
            align-items: stretch;
        }

        .segment-grid {
            grid-template-columns: repeat(5, minmax(0, 1fr));
        }

        .seed-grid {
            grid-template-columns: repeat(5, minmax(0, 1fr));
        }

        .segment-card {
            border-radius: 17px;
            padding: 24px 20px;
            background: rgba(255,255,255,0.038);
            border: 1px solid rgba(255,255,255,0.12);
            min-height: 250px;
        }

        .seed-step-card {
            position: relative;
            overflow: hidden;
            border-radius: 18px;
            padding: 28px 20px 26px;
            background:
                radial-gradient(circle at 50% 0%, rgba(152,255,171,0.085), transparent 42%),
                rgba(255,255,255,0.038);
            border: 1px solid rgba(152,255,171,0.18);
            min-height: 258px;
            display: flex;
            flex-direction: column;
            align-items: center;
            text-align: center;
            box-shadow:
                inset 0 0 24px rgba(152,255,171,0.035),
                0 14px 36px rgba(0,0,0,0.18);
            transition: all 0.22s ease;
        }

        .seed-step-card:hover {
            transform: translateY(-4px);
            border-color: rgba(152,255,171,0.42);
            box-shadow:
                inset 0 0 28px rgba(152,255,171,0.06),
                0 18px 46px rgba(0,0,0,0.30),
                0 0 22px rgba(152,255,171,0.08);
        }

        .seed-step-card::before {
            content: "";
            position: absolute;
            left: 24px;
            right: 24px;
            top: 0;
            height: 1px;
            background: linear-gradient(90deg, transparent, rgba(152,255,171,0.55), transparent);
        }

        .segment-card {
            position: relative;
            overflow: hidden;
            padding: 30px 20px 26px;
            display: flex;
            flex-direction: column;
        }

        .segment-head {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: flex-start;
            text-align: center;
            min-height: 132px;
            margin-bottom: 8px;
        }

        .segment-icon-badge {
            width: 58px;
            height: 58px;
            border-radius: 18px;
            display: flex;
            align-items: center;
            justify-content: center;
            margin: 0 auto 15px auto;
            font-size: 27px;
            line-height: 1;
            border: 1px solid rgba(255,255,255,0.12);
            box-shadow: 0 0 18px rgba(240, 140, 255, 0.12);
            background: rgba(255,255,255,0.05);
        }

        .icon-cluster {
            color: #FFD45D;
            background: rgba(255, 212, 93, 0.10);
            border-color: rgba(255, 212, 93, 0.25);
        }

        .icon-protostar {
            color: #98FFAB;
            background: rgba(152, 255, 171, 0.10);
            border-color: rgba(152, 255, 171, 0.25);
        }

        .icon-satellite {
            color: #8FB8FF;
            background: rgba(143, 184, 255, 0.10);
            border-color: rgba(143, 184, 255, 0.25);
        }

        .icon-supernova {
            color: #FF7AC8;
            background: rgba(255, 122, 200, 0.10);
            border-color: rgba(255, 122, 200, 0.25);
        }

        .icon-comet {
            color: #FF9E5E;
            background: rgba(255, 158, 94, 0.10);
            border-color: rgba(255, 158, 94, 0.25);
        }

        .segment-card:hover .segment-icon-badge {
            transform: translateY(-2px) scale(1.04);
            box-shadow: 0 0 24px rgba(240, 140, 255, 0.24);
        }

        .segment-num {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            min-width: 34px;
            height: 26px;
            padding: 0 10px;
            border-radius: 999px;
            font-size: 12px;
            font-weight: 950;
            margin-bottom: 14px;
            color: #F7C2FF;
            background: rgba(240, 140, 255, 0.18);
            border: 1px solid rgba(240, 140, 255, 0.30);
        }

        .seed-icon-orbit {
            width: 82px;
            height: 82px;
            border-radius: 999px;
            display: flex;
            align-items: center;
            justify-content: center;
            margin: 0 auto 16px;
            background:
                radial-gradient(circle, rgba(152,255,171,0.18) 0%, rgba(152,255,171,0.06) 58%, transparent 72%);
            border: 1px solid rgba(152,255,171,0.28);
            box-shadow:
                0 0 24px rgba(152,255,171,0.08),
                inset 0 0 18px rgba(152,255,171,0.04);
        }

        .seed-icon-badge {
            width: 56px;
            height: 56px;
            display: flex;
            align-items: center;
            justify-content: center;
            position: relative;
            background: transparent;
            border: none;
            box-shadow: none;
            transform: scale(1.08);
            transform-origin: center center;
        }

        .seed-icon-badge::before,
        .seed-icon-badge::after {
            content: "";
            position: absolute;
            box-sizing: border-box;
            filter: drop-shadow(0 0 6px rgba(152,255,171,0.18));
        }

        /* 01 검색 */
        .seed-icon-search::before {
            width: 28px;
            height: 28px;
            border: 3.4px solid #98FFAB;
            border-radius: 50%;
            left: 10px;
            top: 9px;
        }

        .seed-icon-search::after {
            width: 20px;
            height: 3.4px;
            background: #98FFAB;
            border-radius: 999px;
            left: 33px;
            top: 35px;
            transform: rotate(45deg);
        }


/* 02 팬 반응 밀도 */
        .seed-icon-chat::before {
            width: 58px;
            height: 58px;
            left: 50%;
            top: 50%;
            transform: translate(-50%, -50%);
            background: url("data:image/svg+xml,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20viewBox%3D%220%200%2048%2048%22%20fill%3D%22none%22%20stroke%3D%22%2398FFAB%22%20stroke-width%3D%222.9%22%20stroke-linecap%3D%22round%22%20stroke-linejoin%3D%22round%22%3E%3Cpath%20d%3D%22M12%2012.5h24a3%203%200%200%201%203%203v12a3%203%200%200%201-3%203H22l-7%205v-5h-3a3%203%200%200%201-3-3v-12a3%203%200%200%201%203-3Z%22%2F%3E%3Cpath%20d%3D%22M24%2025.8s-4.8-2.7-4.8-5.9c0-1.6%201.3-2.9%202.9-2.9%201.2%200%202%20.7%202.6%201.6.6-.9%201.4-1.6%202.6-1.6%201.6%200%202.9%201.3%202.9%202.9%200%203.2-4.8%205.9-4.8%205.9Z%22%2F%3E%3C%2Fsvg%3E") center / contain no-repeat;
            border: none;
        }

        .seed-icon-chat::after {
            display: none;
        }

        /* 03 라이브 전환성 */
        .seed-icon-live::before {
            width: 56px;
            height: 56px;
            left: 50%;
            top: 50%;
            transform: translate(-50%, -50%);
            background: url("data:image/svg+xml,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20viewBox%3D%220%200%2048%2048%22%20fill%3D%22none%22%20stroke%3D%22%2398FFAB%22%20stroke-width%3D%223%22%20stroke-linecap%3D%22round%22%20stroke-linejoin%3D%22round%22%3E%3Crect%20x%3D%2214%22%20y%3D%2216%22%20width%3D%2216%22%20height%3D%2212%22%20rx%3D%222.5%22%2F%3E%3Cpath%20d%3D%22M30%2019l5-3v12l-5-3%22%2F%3E%3Cpath%20d%3D%22M10%2018c2-4.5%206.4-7.5%2011.4-7.8%22%2F%3E%3Cpath%20d%3D%22M18.2%207.6l3.9%202.2-3.7%202.4%22%2F%3E%3Cpath%20d%3D%22M38%2030c-2%204.5-6.4%207.5-11.4%207.8%22%2F%3E%3Cpath%20d%3D%22M29.8%2040.4l-3.9-2.2%203.7-2.4%22%2F%3E%3C%2Fsvg%3E") center / contain no-repeat;
            border: none;
        }

        .seed-icon-live::after {
            display: none;
        }

        /* 04 실전 리스크 */
        .seed-icon-filter::before {
            width: 44px;
            height: 44px;
            left: 50%;
            top: 50%;
            transform: translate(-50%, -50%);
            background: url("data:image/svg+xml,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20viewBox%3D%220%200%2048%2048%22%20fill%3D%22none%22%20stroke%3D%22%2398FFAB%22%20stroke-width%3D%223.4%22%20stroke-linecap%3D%22round%22%20stroke-linejoin%3D%22round%22%3E%3Ccircle%20cx%3D%2224%22%20cy%3D%2224%22%20r%3D%2211.5%22%2F%3E%3Cpath%20d%3D%22M17.5%2024h13%22%2F%3E%3C%2Fsvg%3E") center / contain no-repeat;
            border: none;
        }

        .seed-icon-filter::after {
            display: none;
        }

        /* 05 체크 */
        .seed-icon-check::before {
            width: 36px;
            height: 36px;
            border: 3.4px solid #98FFAB;
            border-radius: 10px;
            left: 10px;
            top: 10px;
        }

        .seed-icon-check::after {
            width: 21px;
            height: 12px;
            border-left: 4.5px solid #98FFAB;
            border-bottom: 4.5px solid #98FFAB;
            left: 18px;
            top: 21px;
            transform: rotate(-45deg);
        }

        .seed-mini-line {
            width: 28px;
            height: 2px;
            border-radius: 999px;
            background: rgba(152,255,171,0.92);
            margin: 0 auto 14px;
        }

        .segment-ko,
        .seed-title {
            color: #FFF9FF;
            font-size: 20px;
            line-height: 1.35;
            font-weight: 950;
            margin-bottom: 8px;
        }

        .segment-ko {
            text-align: center;
        }

        .segment-en {
            color: #F08CFF;
            font-size: 13px;
            font-weight: 950;
            margin-bottom: 0;
            text-align: center;
        }

        .segment-purpose {
            color: rgba(255,255,255,0.82);
            font-size: 14px;
            line-height: 1.55;
            font-weight: 760;
            padding: 12px 13px;
            margin-bottom: 20px;
            border-radius: 12px;
            background: rgba(240, 140, 255, 0.10);
            border: 1px solid rgba(240, 140, 255, 0.22);
            min-height: 74px;
            display: flex;
            align-items: center;
            justify-content: center;
            text-align: center;
            word-break: keep-all;
        }

        .purpose-key {
            display: inline-block;
            margin-top: 2px;
            color: #FFFFFF;
            font-size: 16px;
            font-weight: 950;
            letter-spacing: -0.2px;
            text-shadow: 0 0 10px rgba(240, 140, 255, 0.22);
        }

        .field-label {
            color: #F0B5FF;
            font-size: 12px;
            font-weight: 950;
            letter-spacing: 0.2px;
            margin-top: 12px;
            margin-bottom: 6px;
        }

        .field-value {
            color: rgba(255,255,255,0.76);
            font-size: 14px;
            line-height: 1.7;
            font-weight: 500;
            letter-spacing: -0.02em;
            word-break: keep-all;
            overflow-wrap: normal;
        }

        .seed-desc {
            color: rgba(255,255,255,0.76);
            font-size: 15px;
            line-height: 1.65;
            font-weight: 560;
            letter-spacing: -0.02em;
            word-break: keep-all;
            overflow-wrap: normal;
            min-height: 50px;
        }

        .seed-title {
            font-size: 21px;
            margin-bottom: 12px;
            margin-top: 2px;
            word-break: keep-all;
        }

        .empty-guide {
            position: relative;
            z-index: 3;
            margin-top: 34px;
            font-size: 15px;
            color: rgba(191,181,213,0.72);
            text-align: center;
        }

        .page-panel {
            position: relative;
            z-index: 3;
            border-radius: 22px;
            background: rgba(21, 16, 47, 0.86);
            border: 1px solid rgba(196, 143, 255, 0.26);
            padding: 36px 40px;
            margin-top: 30px;
            color: rgba(255,255,255,0.78);
            line-height: 1.8;
        }

        @media (max-width: 1200px) {
            .segment-grid,
            .seed-grid {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }

            .hero-title {
                font-size: 44px;
                letter-spacing: 5px;
            }

            .planet {
                width: 280px;
                height: 280px;
            }

            .planet-area {
                height: 330px;
            }
        }

        @media (max-width: 780px) {
            .segment-grid,
            .seed-grid {
                grid-template-columns: 1fr;
            }
        }
        </style>
        """
    ),
    unsafe_allow_html=True,
)

st.markdown(
    f'<div class="star-layer">{st.session_state.bg_html}</div><div class="orbit-bg"></div>',
    unsafe_allow_html=True,
)

with st.sidebar:
    html(
        """
        <div class="sidebar-title">CIME</div>
        <div class="sidebar-subtitle">MISSION CONTROL</div>
        <div class="sidebar-line"></div>
        """
    )

    NAV_ITEMS = {
        "대시보드 홈": {
            "label": "대시보드 홈",
            "icon": ":material/dashboard:",
        },
        "스타트레일": {
            "label": "스타트레일",
            "icon": ":material/auto_awesome:",
        },
        "스타시드": {
            "label": "스타시드",
            "icon": ":material/search:",
        },
    }

    for page, item in NAV_ITEMS.items():
        is_active = st.session_state.page == page

        if st.button(
            item["label"],
            key=f"nav_{page}",
            use_container_width=True,
            type="primary" if is_active else "secondary",
            icon=item["icon"],
        ):
            st.session_state.page = page
            st.session_state.card = None
            st.rerun()

def render_planet_home():
    html(
        """
        <div class="main-wrap">
        <div class="hero-title">CIME STREAM PLANET</div>
        <div class="hero-subtitle">데이터 우주에서 다음 플랫폼의 중심 별을 찾다</div>
        <div class="planet-area">
        <div class="planet-glow"></div>
        <div class="planet-orbit orbit-3"></div>
        <div class="planet-orbit"></div>
        <div class="planet-orbit orbit-2"></div>
        <div class="satellite sat-1"></div>
        <div class="satellite sat-2"></div>
        <div class="satellite sat-3"></div>
        <div class="satellite sat-4"></div>
        <div class="planet">
        <div class="planet-logo">CIME</div>
        </div>
        </div>
        </div>
        """
    )


def render_mission_cards():
    col1, col2 = st.columns(2, gap="large")

    with col1:
        html(
            f"""
            <div class="mission-card trail-card">
                <div class="card-head">
                    <div class="icon-box trail-icon-box">
                        {TRAIL_ICON_HTML}
                    </div>
                    <div>
                        <div class="card-title">스타트레일</div>
                        <div class="card-en trail-en">Star Trail</div>
                    </div>
                </div>

                <div class="card-desc">
                    기존 플랫폼에서 검증된 
                    <span class="trail-point">성과와 팬덤</span>을 기반으로,<br>
                    <span class="trail-point">CIME 영입 우선 후보군</span>을 탐색합니다.
                </div>
            </div>
            """
        )
        if st.button("스타트레일 자세히 보기", key="btn_startrail", use_container_width=True):
            st.session_state.card = None if st.session_state.card == "trail" else "trail"

    with col2:
        html(
            f"""
            <div class="mission-card seed-card">
                <div class="card-head">
                    <div class="icon-box seed-icon-box">
                        {SEED_ICON_HTML}
                    </div>
                    <div>
                        <div class="card-title">스타시드</div>
                        <div class="card-en seed-en">Star Seed</div>
                    </div>
                </div>

                <div class="card-desc">
                    유튜브 기반 
                    <span class="seed-point">성장 잠재력</span>과 
                    <span class="seed-point">라이브 전환 가능성</span>을 분석해,<br>
                    <span class="seed-point">차세대 후보군</span>을 발굴합니다.
                </div>
            </div>
            """
        )
        if st.button("스타시드 자세히 보기", key="btn_starseed", use_container_width=True):
            st.session_state.card = None if st.session_state.card == "seed" else "seed"


def render_startrail_detail():
    cards = "".join(
        [
            f'<div class="segment-card">'
            f'<div class="segment-head">'
            f'<div class="segment-icon-badge {seg["icon_class"]}">{seg["icon"]}</div>'
            f'<div class="segment-ko">{seg["ko"]}</div>'
            f'<div class="segment-en">{seg["en"]}</div>'
            f'</div>'
            f'<div class="segment-purpose">{seg["purpose"]}</div>'
            f'<div class="field-label">주요 판단 기준</div>'
            f'<div class="field-value">{seg["criteria"]}</div>'
            f'<div class="field-label">CIME 활용 포인트</div>'
            f'<div class="field-value">{seg["point"]}</div>'
            f'</div>'
            for seg in STARTRAIL_SEGMENTS
        ]
    )

    st.markdown(
        (
            '<div class="detail-box">'
            f'<div class="detail-phase-head detail-phase-trail"><div class="detail-phase-icon">{TRAIL_ICON_HTML}</div><div class="detail-phase-title-row"><span class="detail-phase-ko">스타트레일</span><span class="detail-phase-en">Star Trail</span></div></div>'
            '<div class="detail-title">기존 플랫폼 성과를 기준으로 CIME 영입 후보군을 선별하는 단계</div>'
            '<div class="detail-text">'
            '스타트레일은 <span class="trail-soft-point">기존 플랫폼에서 이미 활동 성과가 확인된 스트리머</span>를 분석합니다.<br>'
            '대중성, 방송화력, 팬덤결집력, 수익성, 외부유입가능성을 함께 비교해<br>'
            '<span class="trail-soft-point">CIME 영입 우선순위가 높은 후보군</span>을 찾습니다.'
            '</div>'
            f'<div class="segment-grid">{cards}</div>'
            '</div>'
        ),
        unsafe_allow_html=True,
    )


def render_starseed_detail():
    cards = "".join(
        [
            f'<div class="seed-step-card">'
            f'<div class="seed-icon-orbit"><div class="seed-icon-badge seed-icon-{step["icon"]}"></div></div>'
                        f'<div class="seed-title">{step["title"]}</div>'
            f'<div class="seed-mini-line"></div>'
            f'<div class="seed-desc">{step["desc"]}</div>'
            f'</div>'
            for step in STAR_SEED_CARDS
        ]
    )

    st.markdown(
        (
            '<div class="detail-box">'
            f'<div class="detail-phase-head detail-phase-seed"><div class="detail-phase-icon">{SEED_ICON_HTML}</div><div class="detail-phase-title-row"><span class="detail-phase-ko">스타시드</span><span class="detail-phase-en">Star Seed</span></div></div>'
            '<div class="detail-title">유튜브에서 CIME가 실제로 검토할 후보를 찾는 단계</div>'
            '<div class="detail-text">'
            '스타시드는 <span class="seed-soft-point">유튜브에서 활동 중인 크리에이터</span> 중 단순 인기 채널이 아니라 실제 영입 검토가 가능한 후보를 분석합니다.<br>'
            '팬 반응 밀도, 라이브 전환성, 실전 리스크, 액션버킷을 함께 확인해<br>'
            '<span class="seed-soft-point">CIME가 우선 검토할 예비 스트리머 후보군</span>을 정리합니다.'
            '</div>'
            f'<div class="seed-grid">{cards}</div>'
            '</div>'
        ),
        unsafe_allow_html=True,
    )

if st.session_state.page == "대시보드 홈":
    render_planet_home()
    render_mission_cards()

    if st.session_state.card == "trail":
        render_startrail_detail()
    elif st.session_state.card == "seed":
        render_starseed_detail()
    else:
        html(
            """
            <div class="empty-guide">
            스타트레일 또는 스타시드 카드를 선택하면 아래에 단계 설명이 표시됩니다.
            </div>
            """
        )

elif st.session_state.page == "스타트레일":
    html(
        """
        <div class="main-wrap">
        <div class="hero-title">STAR TRAIL</div>
        <div class="hero-subtitle">기존 플랫폼 기반 영입 후보군 대시보드 영역</div>
        </div>
        <div class="page-panel">
        이 영역에는 추후 스타트레일 분석 대시보드가 들어갈 예정입니다.
        홈 화면의 스타트레일 카드 설명과는 별도로 운영되는 페이지입니다.
        </div>
        """
    )

elif st.session_state.page == "스타시드":
    html(
        """
        <div class="main-wrap">
        <div class="hero-title">STAR SEED</div>
        <div class="hero-subtitle">유튜브 기반 잠재 후보군 대시보드 영역</div>
        </div>
        <div class="page-panel">
        이 영역에는 추후 스타시드 분석 대시보드가 들어갈 예정입니다.
        홈 화면의 스타시드 카드 설명과는 별도로 운영되는 페이지입니다.
        </div>
        """
    )
