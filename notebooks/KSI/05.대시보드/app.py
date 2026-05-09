
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
        "purpose": "팬덤 단위 이동이 가능한 집단형 후보 발굴",
        "criteria": "그룹/아이돌성, 팬덤 결집, 멤버 단위 이동 가능성",
        "point": "팬덤 단위 유입으로 CIME의 초기 트래픽을 확보합니다.",
    },
    {
        "num": "02",
        "ko": "프로토스타",
        "en": "Protostar",
        "purpose": "외부 규모는 작지만 방송 반응이 좋은 성장형 후보 발굴",
        "criteria": "시청자 반응, 채팅, 뷰어십, 팔로워 대비 성과",
        "point": "성장 가능성이 높은 원석을 육성 타깃으로 확보합니다.",
    },
    {
        "num": "03",
        "ko": "위성",
        "en": "Satellite",
        "purpose": "후원·채팅·시청자 반응이 검증된 개인 후보 발굴",
        "criteria": "도네이션, 채팅화력, 평균 시청자, 솔로 여부",
        "point": "검증된 개인 화력으로 수익화와 방송 활력을 만듭니다.",
    },
    {
        "num": "04",
        "ko": "슈퍼노바",
        "en": "Supernova",
        "purpose": "대중성과 팬덤 체급이 큰 간판형 후보 발굴",
        "criteria": "팔로워, 최고 시청자, 유튜브 구독자, 팬덤지수, 방송화력",
        "point": "간판 스트리머로 인지도와 트래픽을 빠르게 끌어올립니다.",
    },
    {
        "num": "05",
        "ko": "코멧",
        "en": "Comet",
        "purpose": "외부 채널 기반 신규 유입 후보 발굴",
        "criteria": "유튜브 구독자, X 팔로워, 유튜브/X 유입지수, 플랫폼 대비 외부 체급",
        "point": "외부 채널 기반으로 신규 유저층을 CIME로 유입시킵니다.",
    },
]

STARSEED_STEPS = [
    {
        "num": "01",
        "title": "유튜브 기반 후보 발굴",
        "desc": "YouTube Data API를 활용해 CIME의 타깃 세그먼트와 맞는 채널과 영상을 수집합니다.",
    },
    {
        "num": "02",
        "title": "팬덤 반응 분석",
        "desc": "조회수 대비 좋아요·댓글 반응을 확인하여 단순 노출이 아닌 팬덤 밀도를 판단합니다.",
    },
    {
        "num": "03",
        "title": "라이브 전환 가능성 검토",
        "desc": "게임, 노래, ASMR, 토크 등 실시간 방송으로 확장 가능한 콘텐츠인지 확인합니다.",
    },
    {
        "num": "04",
        "title": "영입 실전성 검증",
        "desc": "방송사, 기관, 팬클립, 아카이브, 리믹스 채널 등 실제 영입 대상이 아닌 채널을 제외합니다.",
    },
    {
        "num": "05",
        "title": "Shortlist 생성",
        "desc": "최종점수, 액션버킷, 리스크 플래그를 함께 확인해 사람이 검토할 후보 리스트로 정리합니다.",
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
        }

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
            font-weight: 560;
            margin-bottom: 34px;
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

        .segment-card,
        .seed-step-card {
            border-radius: 17px;
            padding: 24px 20px;
            background: rgba(255,255,255,0.038);
            border: 1px solid rgba(255,255,255,0.12);
            min-height: 250px;
        }

        .segment-num,
        .seed-num {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            min-width: 34px;
            height: 26px;
            padding: 0 10px;
            border-radius: 999px;
            font-size: 12px;
            font-weight: 950;
            margin-bottom: 22px;
        }

        .segment-num {
            color: #F7C2FF;
            background: rgba(240, 140, 255, 0.18);
            border: 1px solid rgba(240, 140, 255, 0.30);
        }

        .seed-num {
            color: #A8FFB7;
            background: rgba(152, 255, 171, 0.13);
            border: 1px solid rgba(152, 255, 171, 0.28);
        }

        .segment-ko,
        .seed-title {
            color: #FFF9FF;
            font-size: 20px;
            line-height: 1.35;
            font-weight: 950;
            margin-bottom: 8px;
        }

        .segment-en {
            color: #F08CFF;
            font-size: 13px;
            font-weight: 950;
            margin-bottom: 20px;
        }

        .segment-purpose {
            color: #FFF9FF;
            font-size: 15px;
            line-height: 1.65;
            font-weight: 900;
            padding: 12px 13px;
            margin-bottom: 20px;
            border-radius: 12px;
            background: rgba(240, 140, 255, 0.10);
            border: 1px solid rgba(240, 140, 255, 0.22);
        }

        .field-label {
            color: #F0B5FF;
            font-size: 12px;
            font-weight: 950;
            letter-spacing: 0.2px;
            margin-top: 14px;
            margin-bottom: 6px;
        }

        .field-value,
        .seed-desc {
            color: rgba(255,255,255,0.76);
            font-size: 14px;
            line-height: 1.65;
            font-weight: 560;
            word-break: keep-all;
        }

        .seed-title {
            margin-bottom: 16px;
        }

        .seed-desc {
            font-size: 15px;
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

    for page in ["대시보드 홈", "스타트레일", "스타시드"]:
        is_active = st.session_state.page == page
        if st.button(
            page,
            key=f"nav_{page}",
            use_container_width=True,
            type="primary" if is_active else "secondary",
        ):
            st.session_state.page = page
            st.session_state.card = None


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
            """
            <div class="mission-card trail-card">
            <div class="card-head">
            <div class="icon-box trail-icon-box">
            <div class="css-star"></div>
            </div>
            <div>
            <div class="card-title">스타트레일</div>
            <div class="card-en trail-en">Star Trail</div>
            </div>
            </div>
            <div class="card-desc">
            기존 플랫폼에서 활동성과 팬덤이 확인된<br>
            스트리머 영입 후보군을 발굴합니다.
            </div>
            </div>
            """
        )
        if st.button("스타트레일 설명 보기", key="btn_startrail", use_container_width=True):
            st.session_state.card = None if st.session_state.card == "trail" else "trail"

    with col2:
        html(
            """
            <div class="mission-card seed-card">
            <div class="card-head">
            <div class="icon-box seed-icon-box">
            <div class="css-seed">
            <div class="leaf-left"></div>
            <div class="leaf-right"></div>
            <div class="seed-pot"></div>
            </div>
            </div>
            <div>
            <div class="card-title">스타시드</div>
            <div class="card-en seed-en">Star Seed</div>
            </div>
            </div>
            <div class="card-desc">
            유튜브 기반 잠재 후보의 팬덤 반응과<br>
            라이브 전환 가능성을 분석합니다.
            </div>
            </div>
            """
        )
        if st.button("스타시드 설명 보기", key="btn_starseed", use_container_width=True):
            st.session_state.card = None if st.session_state.card == "seed" else "seed"


def render_startrail_detail():
    cards = "".join(
        [
            f'<div class="segment-card">'
            f'<div class="segment-num">{seg["num"]}</div>'
            f'<div class="segment-ko">{seg["ko"]}</div>'
            f'<div class="segment-en">{seg["en"]}</div>'
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
            '<div class="detail-kicker">PHASE 01 · STAR TRAIL</div>'
            '<div class="detail-title">기존 플랫폼의 데이터 궤적을 따라 영입 후보군을 찾는 단계</div>'
            '<div class="detail-text">'
            '스타트레일은 기존 플랫폼에서 이미 빛을 내고 있는 스트리머들의 데이터 흐름을 따라, '
            'CIME로 유입 가능한 영입 후보군을 발굴하는 1단계 분석입니다. '
            '단순 인지도만 보는 것이 아니라 유입력, 방송화력, 팬덤 결집력, 수익성, 플랫폼 적합성을 함께 검토합니다.'
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
            f'<div class="seed-num">{step["num"]}</div>'
            f'<div class="seed-title">{step["title"]}</div>'
            f'<div class="seed-desc">{step["desc"]}</div>'
            f'</div>'
            for step in STARSEED_STEPS
        ]
    )

    st.markdown(
        (
            '<div class="detail-box">'
            '<div class="detail-kicker">PHASE 02 · STAR SEED</div>'
            '<div class="detail-title">유튜브 기반 잠재 후보를 발굴해 라이브 전환 가능성을 보는 단계</div>'
            '<div class="detail-text">'
            '스타시드는 유튜브에서 활동 중인 크리에이터 중 CIME에서 라이브 스트리머로 성장할 가능성이 있는 '
            '잠재 후보를 발굴하는 2단계 분석입니다. 팬덤 반응, 성장성, 라이브 전환 가능성, 영입 실전성을 함께 검토해 '
            '실제 검토 가능한 후보 리스트를 만듭니다.'
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
