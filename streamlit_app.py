"""
보험 설계사 인센티브 대시보드
Streamlit 메인 애플리케이션 (공개 스프레드시트 버전)
"""

import streamlit as st
import os
import sys

# [중요] GitHub/Streamlit Cloud 환경에서 로컬 파일들을 찾을 수 있도록 현재 디렉토리를 경로에 추가
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

import pandas as pd
import numpy as np
import altair as alt
import textwrap
import pickle
from datetime import datetime, timedelta

# 로컬 모듈 import (sys.path 작업 이후에 실행)
try:
    from data_loader import (
        load_contracts_from_url, load_rules_from_url,
        load_contracts_from_csv, load_rules_from_csv,
        validate_contracts, validate_rules, preprocess_contracts,
        get_unique_agents, get_unique_companies, get_period_dates,
        filter_by_period, load_consecutive_rules
    )
    import incentive_engine
    import analysis
    import ui_components
    
    # 리로드 처리 (캐싱 방지)
    import importlib
    importlib.reload(incentive_engine)
    importlib.reload(analysis)
    importlib.reload(ui_components)
except ImportError as e:
    st.error(f"⚠️ 모듈 로드 중 에러가 발생했습니다: {e}")
    st.info(f"현재 경로: {current_dir}")
    st.info(f"환경 변수 PATH: {sys.path}")
    st.info(f"디렉토리 내 파일 목록: {os.listdir(current_dir) if os.path.exists(current_dir) else '경로 없음'}")
    raise e
from incentive_engine import (
    calculate_all_awards, resolve_competing_awards, get_award_summary,
    calculate_all_agents_awards
)
from analysis import (
    regret_analysis, 
    pivot_analysis, 
    generate_daily_report, 
    get_product_statistics, 
    get_daily_trend, 
    analyze_weekly_performance,
    analyze_cross_company_optimization
)

# --- 캐싱 전용 함수 ---
@st.cache_data(show_spinner="전체 시상금 계산 중... (수 분이 소요될 수 있습니다)")
def get_batch_calculation(contracts_df, rules_df, period_start, period_end, company_filter, _v=7):
    """모든 설계사의 시상 내역을 한 번에 계산하여 캐싱 (_v: 캐시 갱신용 버전)"""
    # [CRITICAL] 실적 분류(분류 컬럼)를 위해 전처리 필수 수행
    processed_all, _ = preprocess_contracts(contracts_df, agent_name=None)
    
    consecutive_rules = load_consecutive_rules()
    results = calculate_all_agents_awards(
        processed_all, rules_df, period_start, period_end,
        company_filter=company_filter,
        consecutive_rules=consecutive_rules
    )
    
    # 컬럼명 공백 제거 (안정성 확보)
    if not results.empty:
        results.columns = [c.strip() for c in results.columns]
        
    return results

# 페이지 설정
st.set_page_config(
    page_title="더바다인슈 실적 현황",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 커스텀 CSS (Figma 디자인 기반 - 고대비 네이비 & 라이트 그레이)
st.markdown("""
<style>
    /* 폰트 및 기본 배경 */
    @import url('https://fonts.googleapis.com/css2?family=Pretendard+Variable:wght@400;500;600;700&display=swap');
    html, body, [data-testid="stAppViewContainer"] {
        font-family: 'Pretendard Variable', sans-serif;
        background-color: #F8F9FC; /* 배경은 다시 회색으로 */
    }
    
    /* [CRITICAL] 최상단 여백 완전 제거 및 헤더 강제 밀착 */
    .stApp {
        background-color: #F8F9FC;
    }
    header[data-testid="stHeader"], [data-testid="stDecoration"] {
        display: none !important;
        height: 0 !important;
    }
    .main .block-container {
        padding-top: 0 !important;
        margin-top: 54px !important; /* 헤더 높이만큼 컨텐츠만 내림 */
    }
    [data-testid="stAppViewContainer"] {
        padding-top: 0 !important;
    }
    
    /* 사이드바 스타일 및 가독성 개선 */
    [data-testid="stSidebar"] {
        background-color: #161622 !important;
        color: white !important;
    }
    
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] .stMarkdown p,
    [data-testid="stSidebar"] .stMarkdown h1,
    [data-testid="stSidebar"] .stMarkdown h2,
    [data-testid="stSidebar"] .stMarkdown h3,
    [data-testid="stSidebar"] .stCaption,
    [data-testid="stSidebar"] p {
        color: #F1F5F9 !important;
        font-weight: 500 !important;
    }

    [data-testid="stSidebar"] .stExpander {
        background-color: rgba(255, 255, 255, 0.05) !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        border-radius: 8px !important;
    }

    [data-testid="stSidebar"] .stExpander header div p {
        color: #FFFFFF !important;
        font-weight: 600 !important;
    }
    
    /* 사이드바 구분선 */
    [data-testid="stSidebar"] hr {
        border-color: rgba(255, 255, 255, 0.1) !important;
    }

    /* 사이드바 버튼 */
    [data-testid="stSidebar"] button[kind="primary"] {
        background-color: #6366F1 !important;
        border: none !important;
        color: white !important;
    }

    /* 🔥 가이드 전용 링크 스타일 버튼 (Streamlit Native CSS Override) */
    /* data-testid="stButton" 안의 button 태그 중, aria-label 등에 특정 텍스트가 있거나 key가 매칭되는 것을 찾기는 어렵지만,
       Streamlit은 위젯의 key를 DOM에 직접 노출하지 않으므로, 
       우리는 컨테이너 내의 버튼 스타일을 전역적으로 잡되, 
       특정 컨테이너(가이드 영역)에만 적용되도록 범위를 한정하는 전략을 씁니다. */
    
    /* 하지만, 가장 확실한 방법은 버튼 자체를 투명하게 만들고 텍스트만 남기는 것입니다. */
    div[data-testid="stVerticalBlock"] button[kind="secondary"] {
        /* 이 선택자는 너무 포괄적일 수 있으나, 현재 화면에서는 가이드 영역 버튼만 secondary로 쓸 예정이거나,
           특정 구역 안의 버튼만 타겟팅해야 합니다. 
           여기서는 '이동 →' 텍스트를 가진 버튼을 타겟팅할 수 없으므로,
           모든 secondary 버튼에 영향을 주지 않으려 조심해야 합니다.
           대신, Element 레벨에서 스타일을 주입할 수 없으니,
           가장 안전하게는 버튼 자체의 스타일을 강제로 덮어씌우는 클래스를 
           st.markdown으로 버튼 바로 위에 뿌려주는 방식을 쓸 수도 있습니다.
           하지만 여기서는 CSS selector의 :has() 가상 클래스를 활용해 봅니다. */
    }

    /* 메인 앱 컨테이너 여백 최적화 (고정 헤더 삭제) */
    .block-container {
        padding-top: 2rem !important;
        padding-bottom: 2rem !important;
        max-width: 1250px !important;
    }

    header[data-testid="stHeader"] {
        display: none !important;
    }

    /* 프리미엄 핀테크 디자인 시스템 */
    :root {
        --primary: #4F46E5;
        --primary-light: #EEF2FF;
        --success: #10B981;
        --warning: #F59E0B;
        --danger: #EF4444;
        --slate-50: #F8FAFC;
        --slate-100: #F1F5F9;
        --slate-200: #E2E8F0;
        --slate-700: #334155;
        --slate-900: #0F172A;
    }

    /* 사이드바 제거 및 고정 여백 적용 */
    [data-testid="stSidebar"] { display: none; }

    .header-settings-btn button {
        height: 36px !important;
        font-size: 0.85rem !important;
        font-weight: 600 !important;
        border: 1px solid #E2E8F0 !important;
        border-radius: 8px !important;
    }

    /* 설계사 정보 배지 */
    .agent-info-badge {
        margin-left: auto;
        display: flex;
        align-items: center;
        background: var(--slate-100);
        padding: 6px 16px;
        border-radius: 100px;
        border: 1px solid var(--slate-200);
        transition: all 0.2s;
    }
    .agent-info-badge:hover {
        background: white;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .badge-name { font-weight: 700; color: var(--slate-900); font-size: 0.85rem; }
    .badge-payout { font-weight: 700; color: var(--primary); font-size: 0.85rem; margin-left: 10px; }
    .badge-divider { color: var(--slate-200); margin: 0 10px; }

    /* 데이터 연결 설정 버튼 */
    .settings-trigger {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 8px 16px;
        background: white;
        border: 1px solid var(--slate-200);
        border-radius: 8px;
        color: var(--slate-700);
        font-weight: 600;
        font-size: 0.85rem;
        cursor: pointer;
        transition: all 0.2s;
        margin-left: 1.5rem;
    }
    .settings-trigger:hover {
        background: var(--slate-50);
        border-color: var(--primary);
        color: var(--primary);
    }
    .agent-info {
        margin-left: auto;
        display: flex;
        align-items: center;
        gap: 12px;
        background: #F8FAFC;
        padding: 4px 16px;
        border-radius: 99px;
        border: 1px solid #E2E8F0;
        font-size: 0.85rem;
        color: #475569;
    }
    .agent-name {
        font-weight: 700;
        color: #1E293B;
        display: flex;
        align-items: center;
        gap: 6px;
    }
    .agent-status-tag {
        font-weight: 600;
        color: #4F46E5;
    }
    
    /* 성과 최적화 가이드 커스텀 스타일 */
    .guide-card-active {
        background: #FFFFFF;
        border: 1px solid #E2E8F0 !important;
        border-radius: 12px !important;
        padding: 1rem !important;
        transition: border-color 0.2s;
    }
    .guide-card-active:hover { border-color: #CBD5E1 !important; }

    .guide-card-history {
        background: #F8FAFC;
        border: 1px solid #F1F5F9 !important;
        border-radius: 8px !important;
        padding: 0.85rem !important;
    }
    
    .guide-card-switch {
        background: #FFFFFF;
        border: 1px solid #E2E8F0 !important;
        border-radius: 12px !important;
        padding: 1.25rem !important;
        box-shadow: 0 1px 2px rgba(0,0,0,0.03);
    }

    .guide-badge-pill {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.65rem;
        font-weight: 600;
        margin-bottom: 6px;
        text-transform: uppercase;
        letter-spacing: 0.025em;
    }
    .badge-imm { background: #FFF7ED; color: #C2410C; border: 1px solid #FFEDD5; }
    .badge-history { background: #F8FAFC; color: #64748B; border: 1px solid #F1F5F9; }
    .badge-opt { background: #F5F3FF; color: #6D28D9; border: 1px solid #EDE9FE; }
    .badge-switch { background: #F0F9FF; color: #0369A1; border: 1px solid #E0F2FE; }
    
    .guide-title-main {
        font-size: 0.95rem;
        font-weight: 600;
        color: #334155;
        margin-bottom: 2px;
        letter-spacing: -0.01em;
    }
    .guide-company-sub {
        font-size: 0.75rem;
        color: #94A3B8;
        margin-bottom: 10px;
    }
    .guide-desc-text {
        font-size: 0.85rem;
        color: #475569;
        line-height: 1.6;
    }
    .switch-container {
        display: flex;
        align-items: stretch;
        gap: 8px;
        margin-top: 12px;
    }
    .switch-box {
        background: #F8FAFC;
        border-radius: 6px;
        padding: 10px;
        font-size: 0.8rem;
        border: 1px solid #F1F5F9;
        flex: 1;
    }
    .switch-arrow {
        display: flex;
        align-items: center;
        color: #CBD5E1;
        font-size: 1rem;
    }
    .switch-highlight {
        color: #0284C7;
        font-weight: 600;
    }
    .evidence-tag {
        font-size: 11px;
        color: #94A3B8;
        background: #F1F5F9;
        padding: 1px 5px;
        border-radius: 3px;
        margin-top: 4px;
        display: inline-block;
    }

    /* [추가] 시뮬레이션 전용 프리미엄 레이아웃 */
    .sim-card {
        background: white;
        border-radius: 16px;
        border: 1px solid #E2E8F0;
        overflow: hidden;
        margin-bottom: 24px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.04);
        width: 100%; /* 너비는 그리드에 맞춤 */
        margin-bottom: 16px;
    }
    .sim-header {
        padding: 12px 20px;
        background: #F8FAFC;
        display: flex;
        align-items: center;
        justify-content: space-between;
        border-bottom: 1px solid #F1F5F9;
    }
    .sim-row {
        display: flex;
        padding: 16px;
        gap: 12px;
        align-items: stretch;
    }
    .sim-box {
        flex: 1;
        padding: 12px;
        border-radius: 10px;
        border: 1px solid transparent;
        font-size: 0.85rem;
    }
    .sim-box-current { background: #FFF1F2; border-color: #FECDD3; }
    .sim-box-optimized { background: #F0F9FF; border-color: #BAE6FD; }
    
    .sim-award-name { font-size: 0.75rem; color: #64748B; margin-bottom: 8px; font-weight: 500; }
    .sim-comp-name { font-size: 1rem; font-weight: 700; color: #1E293B; margin-bottom: 12px; }
    
    .sim-metric-line { display: flex; justify-content: space-between; margin-bottom: 4px; color: #475569; }
    .sim-metric-label { color: #64748B; }
    .sim-metric-value { font-weight: 600; }
    .sim-metric-value.highlight { color: #E11D48; } /* 초과/부족 강조 */
    .sim-metric-value.gain { color: #0284C7; font-weight: 800; } /* 보상 강조 */

    .sim-arrow-divider {
        display: flex;
        justify-content: center;
        align-items: center;
        margin: -8px 0;
        position: relative;
        z-index: 2;
    }
    .sim-arrow-circle {
        width: 32px;
        height: 32px;
        background: white;
        border: 1px solid #E2E8F0;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        color: #4F46E5;
        font-weight: 800;
    }
    /* 화이트 카드 컨테이너 */
    .white-card {
        background: white;
        padding: 1.5rem;
        border-radius: 12px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
        border: 1px solid #E5E7EB;
        margin-bottom: 1.5rem;
    }
    
    /* 지표 카드 특정 스타일 (Minimalist) */
    .metric-card {
        padding: 0.8rem 1.2rem;
        border-radius: 12px;
        background: white;
        border: 1px solid #E5E7EB;
        box-shadow: 0 1px 2px rgba(0,0,0,0.03);
        display: flex;
        flex-direction: column;
        justify-content: center;
    }
    .metric-card .label {
        font-size: 0.7rem;
        color: #64748B;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.025em;
        margin-bottom: 2px;
    }
    .metric-card .value {
        font-size: 1.25rem;
        font-weight: 800;
        color: #111827;
        margin: 0;
        line-height: 1.2;
    }
    .metric-card .progress-info {
        font-size: 0.65rem;
        color: #10B981;
        margin-top: 2px;
    }

    /* 탭/익스팬더 디자인 */
    .stExpander {
        border-radius: 10px !important;
        border: 1px solid #E5E7EB !important;
        background-color: white !important;
        margin-bottom: 0.75rem !important;
    }

    /* 시상 테이블 전용 스타일 (순수 표 형태) */
    .award-table {
        width: 100%;
        border-collapse: collapse;
        border: 1px solid #E5E7EB;
        border-radius: 8px;
        overflow: hidden;
        background: white;
    }
    
    .award-table-header {
        display: grid;
        grid-template-columns: 40px 2fr 0.8fr 0.8fr 1.2fr 1fr 1.5fr 1fr;
        padding: 0.85rem 1rem;
        background-color: #F9FAFB;
        border-bottom: 2px solid #E5E7EB;
        font-size: 0.75rem;
        font-weight: 700;
        color: #4B5563;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    
    .award-item-row {
        border-bottom: 1px solid #F3F4F6;
    }
    
    .award-item-row:last-child {
        border-bottom: none;
    }
    
    .award-summary {
        display: grid;
        grid-template-columns: 40px 2fr 0.8fr 0.8fr 1.2fr 1fr 1.5fr 1fr;
        align-items: center;
        padding: 0.9rem 1rem;
        cursor: pointer;
        list-style: none;
        transition: background 0.2s;
    }
    
    .award-summary:hover {
        background-color: #F8FAFC;
    }
    
    .award-summary::-webkit-details-marker {
        display: none;
    }
    
    .award-detail-panel {
        background-color: #F9FAFB;
        padding: 1.5rem;
        border-top: 1px solid #F3F4F6;
        box-shadow: inset 0 2px 4px rgba(0,0,0,0.02);
    }
    
    .progress-container {
        width: 100%;
        height: 6px;
        background-color: #E5E7EB;
        border-radius: 999px;
        overflow: hidden;
        margin-top: 4px;
    }
    
    .progress-bar {
        height: 100%;
        border-radius: 999px;
        transition: width 0.5s ease;
    }
    
    .payout-text { text-align: right; font-weight: 700; font-size: 0.95rem; }
    .target-text { text-align: right; color: #374151; font-weight: 500; }
    .perf-text { text-align: right; color: #111827; font-weight: 600; }
</style>
""", unsafe_allow_html=True)


def update_selected_agent(agent_name):
    """설계사 선택 콜백 함수"""
    st.session_state['agent_name_input'] = agent_name
    st.session_state['auto_calculate'] = True
    st.session_state['active_menu'] = "대시보드" # 개인 화면을 보기 위해 대시보드 탭으로 전환

def init_session_state():
    """세션 상태 초기화"""
    if 'contracts_df' not in st.session_state:
        st.session_state.contracts_df = None
    if 'rules_df' not in st.session_state:
        st.session_state.rules_df = None
    if 'results_df' not in st.session_state:
        st.session_state.results_df = None
    if 'data_loaded' not in st.session_state:
        st.session_state.data_loaded = False
    
    # 캐시된 데이터가 있고 로드되지 않은 경우 자동 로드
    if not st.session_state.data_loaded:
        c_df, r_df = load_cache()
        if c_df is not None and r_df is not None:
            st.session_state.contracts_df = c_df
            st.session_state.rules_df = r_df
            st.session_state.data_loaded = True

    if 'agg_sort_col' not in st.session_state:
        st.session_state.agg_sort_col = "총지급액"
    if 'agg_sort_descending' not in st.session_state:
        st.session_state.agg_sort_descending = True
    if 'agg_search_query' not in st.session_state:
        st.session_state.agg_search_query = ""
    if 'agg_branch_filter' not in st.session_state:
        st.session_state.agg_branch_filter = []
    if 'selected_agent' not in st.session_state:
        st.session_state.selected_agent = None
    if 'selected_team' not in st.session_state:
        st.session_state.selected_team = None
    if 'active_menu' not in st.session_state:
        st.session_state.active_menu = "대시보드"

CACHE_DIR = ".cache"
CACHE_CONTRACTS = os.path.join(CACHE_DIR, "contracts_v5.pkl")
CACHE_RULES = os.path.join(CACHE_DIR, "rules_v5.pkl")

def save_cache(contracts_df, rules_df):
    """데이터를 로컬 캐시에 저장"""
    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR)
    try:
        with open(CACHE_CONTRACTS, 'wb') as f:
            pickle.dump(contracts_df, f)
        with open(CACHE_RULES, 'wb') as f:
            pickle.dump(rules_df, f)
        return True
    except Exception as e:
        print(f"Cache Save Failed: {e}")
        return False

def load_cache():
    """로컬 캐시에서 데이터 로드"""
    try:
        if os.path.exists(CACHE_CONTRACTS) and os.path.exists(CACHE_RULES):
            with open(CACHE_CONTRACTS, 'rb') as f:
                c_df = pickle.load(f)
            with open(CACHE_RULES, 'rb') as f:
                r_df = pickle.load(f)
            
            # 스키마 검증: '상품구분' 컬럼 필수
            if '상품구분' not in r_df.columns:
                print("Cache outdated: '상품구분' column missing. Initializing reload.")
                return None, None
                
            return c_df, r_df
        return None, None
    except Exception as e:
        print(f"Cache Load Failed: {e}")
        return None, None


@st.dialog("📊 데이터 연결 설정", width="large")
def data_settings_modal():
    """데이터 소스 설정을 모달로 렌더링"""
    data_source = st.radio(
        "데이터 소스 선택",
        options=["Google 스프레드시트", "CSV 파일 업로드"],
        horizontal=True
    )
    
    st.markdown("---")
    
    if data_source == "Google 스프레드시트":
        spreadsheet_url = st.text_input("📎 스프레드시트 URL", value="https://docs.google.com/spreadsheets/d/1W0eVca5rbpjXoiw65DaVkIY8793KRkoMH8oi8BHp-ow/edit")
        col1, col2 = st.columns(2)
        with col1:
            contracts_sheet = st.text_input("📄 계약 시트명", value="RAW_계약")
        with col2:
            rules_sheets = st.text_input("📜 규칙 시트명", value="KB, 삼성")
        
        if st.button("📥 데이터 동기화", type="primary", use_container_width=True):
            try:
                with st.spinner("데이터 동기화 중..."):
                    st.session_state.contracts_df = load_contracts_from_url(spreadsheet_url, contracts_sheet.strip())
                    sheet_names = [s.strip() for s in rules_sheets.split(',') if s.strip()]
                    rules_dfs = []
                    for sheet_name in sheet_names:
                        try:
                            df = load_rules_from_url(spreadsheet_url, sheet_name)
                            if '회사' not in df.columns: df['회사'] = sheet_name
                            rules_dfs.append(df)
                        except Exception as e: st.warning(f"⚠️ {sheet_name}: {str(e)}")
                    if rules_dfs:
                        st.session_state.rules_df = pd.concat(rules_dfs, ignore_index=True)
                        st.session_state.data_loaded = True
                        save_cache(st.session_state.contracts_df, st.session_state.rules_df)
                        st.success("✅ 동기화 완료!")
                        st.rerun()
            except Exception as e: st.error(f"❌ 실패: {str(e)}")
    else:
        col1, col2 = st.columns(2)
        with col1:
            contracts_file = st.file_uploader("📄 계약데이터 CSV", type=['csv'])
        with col2:
            rules_file = st.file_uploader("📄 시상규칙 CSV", type=['csv'])
            
        if st.button("📥 데이터 업로드", type="primary", use_container_width=True):
            if contracts_file and rules_file:
                try:
                    st.session_state.contracts_df = load_contracts_from_csv(contracts_file)
                    st.session_state.rules_df = load_rules_from_csv(rules_file)
                    st.session_state.data_loaded = True
                    save_cache(st.session_state.contracts_df, st.session_state.rules_df)
                    st.success("✅ 업로드 완료!")
                    st.rerun()
                except Exception as e: st.error(f"❌ 실패: {str(e)}")

def render_main_controls():
    """상단 조회 컨트롤 (바디 영역 렌더링)"""
    current_agent = st.session_state.get('selected_agent')
    current_team = st.session_state.get('selected_team')
    
    # 상단 컨트롤 데이터 준비
    if 'shadow_year' not in st.session_state: st.session_state.shadow_year = 2026
    if 'shadow_month' not in st.session_state: st.session_state.shadow_month = datetime.now().month
    
    yrs = [2024, 2025, 2026]
    yr_idx = yrs.index(st.session_state.shadow_year) if st.session_state.shadow_year in yrs else 2
    m_idx = st.session_state.shadow_month - 1
    if m_idx < 0 or m_idx > 11: m_idx = 0

    # [CRITICAL] 고정 헤더 영역 정의 (최종 디자인: 그림자 구분선 + 마진 축소)
    st.markdown("""
        <style>
        /* 1. 기본 헤더 및 불필요 요소 제거 */
        header[data-testid="stHeader"], [data-testid="stDecoration"], footer { display: none !important; }
        [data-testid="stAppViewContainer"] { padding-top: 0 !important; }
        
        /* 2. 본문 상단 여백 최소화 (헤더 바로 아래 시작) */
        .main .block-container {
            padding-top: 65px !important; /* 헤더 높이(60px) + 여백(5px) */
            margin-top: 0 !important;
            max-width: 100% !important;
        }

        /* 3. 상단 고정 헤더 (그림자 효과 추가) */
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.fixed-header-anchor) {
            position: fixed !important;
            top: 0 !important;
            left: 0 !important;
            width: 100vw !important;
            background-color: #FFFFFF !important;
            z-index: 999999 !important;
            border-bottom: 1px solid #E2E8F0;
            padding: 0 40px !important;
            height: 60px !important;
            display: flex !important;
            align-items: center !important;
            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.08) !important; /* 그림자 강도 증가 */
            margin: 0 !important;
            transform: none !important;
        }
        
        /* 내부 컨텐츠 배치 */
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.fixed-header-anchor) div[data-testid="stHorizontalBlock"] {
            align-items: center !important;
            gap: 1.5rem !important;
            width: 100% !important;
            flex-wrap: nowrap !important;
        }

        /* 위젯 라벨 숨김 */
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.fixed-header-anchor) label { display: none !important; }
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.fixed-header-anchor) div[data-testid="stSelectbox"] {
            margin: 0 !important;
            min-width: 100px !important;
        }
        
        /* 네비게이션 버튼 */
        .nav-link {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 4px 14px;
            border-radius: 8px;
            font-size: 0.88rem;
            font-weight: 600;
            color: #64748B;
            text-decoration: none;
            border: 1px solid #E2E8F0;
            background: #FFFFFF;
            transition: all 0.2s;
            height: 34px;
            white-space: nowrap !important;
        }
        .nav-link:hover { color: #4F46E5; background: #F8FAFC; border-color: #CBD5E1; }
        
        /* 타이틀 */
        .header-title-text {
            font-weight: 800;
            font-size: 1.2rem;
            color: #1E293B;
            display: flex;
            align-items: center;
            gap: 10px;
            white-space: nowrap !important;
            flex-shrink: 0;
        }

        /* [추가] 뒤로가기 버튼 래퍼 및 스타일 (깔끔한 정렬용) */
        .header-back-wrapper {
            display: flex;
            align-items: center;
            justify-content: center;
            height: 100%;
        }
        .header-back-wrapper button {
            background: transparent !important;
            border: none !important;
            padding: 0 !important;
            width: 32px !important;
            height: 32px !important;
            font-size: 1.2rem !important;
            color: #4F46E5 !important;
            box-shadow: none !important;
            transition: all 0.2s ease;
        }
        .header-back-wrapper button:hover {
            background: #F1F5F9 !important;
            border-radius: 8px !important;
        }
        </style>
    """, unsafe_allow_html=True)

    # --- Header Render ---
    from ui_components import render_sticky_header
    
    header_right_col = None

    if current_agent:
        # Agent Detail Header
        def back_to_main():
            st.session_state.selected_agent = None
            
        nav_items = [
            {'label': '통계', 'anchor': '#stats-section'},
            {'label': '추이', 'anchor': '#trend-section'},
            {'label': '시상내역', 'anchor': '#history-section'}
        ]
        header_right_col = render_sticky_header(
            title=f"<span style='color:#4F46E5;'>{current_agent}</span>님 명세",
            is_detail=True,
            back_callback=back_to_main,
            nav_items=nav_items
        )
    elif current_team:
        # Branch Detail Header
        def back_to_main_team():
            st.session_state.selected_team = None

        nav_items = [
            {'label': '통계', 'anchor': '#stats-section'},
            {'label': '추이', 'anchor': '#trend-section'},
            {'label': '설계사별', 'anchor': '#agent-section'}
        ]
        header_right_col = render_sticky_header(
            title=f"<span style='color:#4F46E5;'>{current_team}</span> 현황",
            is_detail=True,
            back_callback=back_to_main_team,
            nav_items=nav_items
        )
    else:
        # Main Dashboard Header
        nav_items = [
            {'label': '통계', 'anchor': '#stats-section'},
            {'label': '추이', 'anchor': '#trend-section'},
            {'label': '팀별', 'anchor': '#team-section'},
            {'label': '설계사별', 'anchor': '#agent-section'}
        ]
        header_right_col = render_sticky_header(
            title="더바다인슈 실적 현황",
            is_detail=False,
            nav_items=nav_items
        )

    # --- Global Filters (In Header) ---
    with header_right_col:
        # Use columns inside the header's right container for alignment
        # r1: Year, r2: Month, r3: Settings
        r1, r2, r3 = st.columns([1.2, 1.2, 1], gap="small")
        with r1:
            target_year = st.selectbox(
                "년도", 
                yrs, 
                index=yr_idx, 
                key="year_sel_header", 
                label_visibility="collapsed"
            )
        with r2:
            target_month = st.selectbox(
                "월", 
                list(range(1, 13)), 
                index=m_idx, 
                key="month_sel_header", 
                format_func=lambda x: f"{x}월", 
                label_visibility="collapsed"
            )
        with r3:
            if st.button("⚙️ 설정", key="btn_open_settings_header_fixed", use_container_width=True):
                data_settings_modal()
        
        # Sync date text below controls (compact) - Explicit KST (UTC+9)
        kst_now = datetime.utcnow() + timedelta(hours=9)
        sync_date_str = kst_now.strftime("%Y-%m-%d %H:%M")
        st.markdown(f'<div style="text-align:right; font-size:0.6rem; color:#94A3B8; margin-top:-32px; letter-spacing:-0.02em;">연동: {sync_date_str} (KST)</div>', unsafe_allow_html=True)

    st.session_state.shadow_year = target_year
    st.session_state.shadow_month = target_month

    # 본문 시작 전 간격
    pass

    # 본문 시작 전 간격
    pass

    # 기본값 계산
    target_month_date = datetime(target_year, target_month, 1)
    base_date = datetime.combine(target_month_date, datetime.min.time())
    period_start, period_end = get_period_dates("월간", base_date)
    
    return {
        'agent_name': current_agent, 
        'company': None,
        'period_start': period_start,
        'period_end': period_end,
        'product_filter': None,
        'type_filter': None, # 필터링 로직 수정으로 여기서는 제거, 딜레이 렌더링으로 처리
        'target_date': target_month_date
    }

# Placeholder for format_currency if not defined elsewhere
def format_currency(value):
    return f"{int(value):,}"

def render_metrics(summary: dict):
    """종합 현황 렌더링 (디자인 고도화 버전)"""
    total_incentive = summary.get('총지급예상금액', 0)
    total_performance = summary.get('총실적', 0)
    pct_incentive = (total_incentive / total_performance * 100) if total_performance > 0 else 0
    co_perf = summary.get('company_performance', {})
    
    st.markdown("""
        <style>
        .metric-card {
            background-color: #FFFFFF;
            border-radius: 12px;
            padding: 1.5rem;
            height: 125px;
            display: flex;
            flex-direction: column;
            justify-content: center;
            transition: all 0.2s ease;
            position: relative;
            border: 1px solid #E2E8F0;
        }
        .metric-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        }
        
        /* 카드별 연한 테두리 색상 */
        .card-incentive { border: 1.5px solid #F3E8FF; }
        .card-total { border: 1px solid #F1F5F9; }
        .card-kb { border: 1.5px solid #FEF3C7; }
        .card-others { border: 1.5px solid #D1FAE5; }

        .metric-title {
            font-size: 0.82rem;
            font-weight: 600;
            color: #64748B;
            display: flex;
            align-items: center;
            gap: 6px;
            margin-bottom: 12px;
        }
        .metric-value {
            font-size: 1.4rem;
            font-weight: 600;
            color: #1E293B;
            letter-spacing: -0.02em;
        }
        .metric-sub {
            font-size: 0.75rem;
            font-weight: 500;
            margin-top: 6px;
        }
        </style>
    """, unsafe_allow_html=True)

    m_col1, m_col2, m_col3, m_col4, m_col5 = st.columns(5)
    
    with m_col1:
        st.markdown(f"""
            <div class="metric-card card-incentive">
                <div class="metric-title">🏢 총 지급 인센티브</div>
                <div class="metric-value" style="color: #6D28D9;">{format_currency(total_incentive)}원</div>
                <div class="metric-sub" style="color: #10B981;">
                    ▲ 전체 실적 대비 {pct_incentive:.1f}% 지출
                </div>
            </div>
        """, unsafe_allow_html=True)
        
    with m_col2:
        st.markdown(f"""
            <div class="metric-card card-total">
                <div class="metric-title">📊 전체 실적 합계</div>
                <div class="metric-value" style="color: #1E293B;">{format_currency(total_performance)}원</div>
                <div class="metric-sub" style="color: transparent;">-</div>
            </div>
        """, unsafe_allow_html=True)
        
    with m_col3:
        samsung_val = co_perf.get('삼성', 0)
        st.markdown(f"""
            <div class="metric-card card-samsung">
                <div class="metric-title">🔵 삼성화재 실적</div>
                <div class="metric-value" style="color: #1D4ED8;">{format_currency(samsung_val)}원</div>
                <div class="metric-sub" style="color: transparent;">-</div>
            </div>
        """, unsafe_allow_html=True)
        
    with m_col4:
        kb_val = co_perf.get('KB', 0)
        st.markdown(f"""
            <div class="metric-card card-kb">
                <div class="metric-title">🟡 KB손해보험 실적</div>
                <div class="metric-value" style="color: #D97706;">{format_currency(kb_val)}원</div>
                <div class="metric-sub" style="color: transparent;">-</div>
            </div>
        """, unsafe_allow_html=True)
        
    with m_col5:
        others_val = co_perf.get('기타', 0)
        st.markdown(f"""
            <div class="metric-card card-others">
                <div class="metric-title"> 기타 보험사 실적</div>
                <div class="metric-value" style="color: #059669;">{format_currency(others_val)}원</div>
                <div class="metric-sub" style="color: transparent;">-</div>
            </div>
        """, unsafe_allow_html=True)
        
    st.markdown('<div class="metrics-bottom-margin" style="margin-bottom: 24px;"></div>', unsafe_allow_html=True)


def render_regret_analysis(regrets_df: pd.DataFrame):
    """놓친 기회 분석 렌더링"""
    st.header("⚠️ 놓친 기회 (달성률 80-99%)")
    
    if regrets_df.empty:
        st.success("✅ **놓친 기회 없음!** 모든 시상을 잘 달성하고 있습니다.")
        return
    
    for idx, row in regrets_df.head(3).iterrows():
        with st.expander(
            f"🎯 [{row['회사']}] {row['시상명']} (ROI {row['ROI']:.0f}%)",
            expanded=(idx == regrets_df.index[0])
        ):
            col1, col2 = st.columns(2)
            
            with col1:
                st.metric("📈 현재 실적", f"{row['실적']:,.0f}원")
                st.metric("🎯 목표 실적", f"{row['목표실적']:,.0f}원")
                st.metric("💸 부족 금액", f"{row['부족금액']:,.0f}원")
            
            with col2:
                st.metric("🎁 추가 보상", f"{row['추가보상']:,.0f}원")
                st.metric("📊 달성률", f"{row['달성률']:.1f}%")
                st.progress(row['달성률'] / 100)
            
            st.success(row['조언'])



def clean_html(html_str):
    """HTML 문자열에서 줄바꿈, 불필요한 공백, 주석을 제거하여 한 줄로 만듭니다."""
    import re
    # 주석 제거
    html_str = re.sub(r'<!--.*?-->', '', html_str, flags=re.DOTALL)
    # 줄바꿈을 공백으로 변경
    no_newlines = html_str.replace("\n", " ").replace("\r", " ")
    # 연속된 공백을 하나로 축소
    cleaned = re.sub(r'\s+', ' ', no_newlines)
    return cleaned.strip()

def get_award_card_html(group, period_str, status_color, status_icon, type_style, payout_display, is_imminent=False, is_past_missed=False):
    """시상 내역 카드 HTML 생성"""
    imminent_badge = ""
    if is_imminent:
        imminent_badge = "<span style='background-color: #FEF2F2; color: #E11D48; font-size: 0.7rem; font-weight: 700; padding: 2px 6px; border-radius: 4px; margin-left: 6px; vertical-align: middle;'>⚠️ 달성임박</span>"
    elif is_past_missed:
        imminent_badge = "<span style='background-color: #F1F5F9; color: #475569; font-size: 0.7rem; font-weight: 700; padding: 2px 6px; border-radius: 4px; margin-left: 6px; vertical-align: middle; border: 1px solid #CBD5E1;'>😢 아쉬운 미달성</span>"
        
    progress_pct = min(group['achievement'], 100)
    
    # Status icon HTML based on type
    icon_html = f'<div style="display: flex; align-items: center; justify-content: center; height: 100%;">{status_icon}</div>'
    
    # Target text formatting
    if '정률' in group['type']:
        # 정률형의 경우 목표 금액 대신 지급률(%) 표시
        rate_val = 0
        
        # 1. Scenarios에서 명시적 rate 탐색
        scens = group.get('scenarios', [])
        if isinstance(scens, list) and scens:
             # 첫번째 시나리오의 rate 확인
             rate_val = scens[0].get('rate', 0) * 100
        
        # 2. 만약 rate를 못 찾았다면, 실적과 지급금액으로 역산
        if rate_val == 0 and group.get('performance', 0) > 0:
             rate_val = (group.get('payout', 0) / group['performance']) * 100
             
        target_display = f"{rate_val:.0f}%" if rate_val > 0 else "-"
    else:
        # 일반형 (정액, 구간 등)
        target_val = group['target']
        target_display = f"{target_val:,.0f}" if pd.notna(target_val) and target_val > 0 else "-"
    
    html = f"""
    <!-- Status Icon -->
    <div style="display: flex; justify-content: center;">
        {icon_html}
    </div>
    
    <!-- Award Name & Company -->
    <div style="padding-right: 1rem;">
        <div style="font-weight: 700; font-size: 0.9rem; color: #111827; margin-bottom: 2px;">{group['name']} {imminent_badge}</div>
        <div style="font-size: 0.75rem; color: #9CA3AF;">{group['company']}</div>
    </div>
    
    <!-- Type -->
    <div>
        <span style="background: {type_style['bg']}; color: {type_style['color']}; padding: 2px 8px; border-radius: 4px; font-size: 0.7rem; font-weight: 600;">
            {group['type']}
        </span>
    </div>
    
    <!-- Category (Target) -->
    <div>
        <span style="background: #F8FAFC; color: #475569; border: 1px solid #E2E8F0; padding: 2px 8px; border-radius: 4px; font-size: 0.7rem; font-weight: 500;">
            {group.get('product_category', '-')}
        </span>
    </div>
    
    <!-- Period -->
    <div style="font-size: 0.8rem; color: #6B7280; font-family: monospace;">
        {period_str}
    </div>
    
    <!-- Target -->
    <div class="target-text">
        {target_display}
    </div>
    
    <!-- Performance & Progress -->
    <div style="padding: 0 1rem;">
        <div style="display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 2px;">
            <span class="perf-text" style="font-size: 0.85rem;">{group['performance']:,.0f}</span>
            <span style="font-size: 0.75rem; color: #6B7280; font-weight: 500;">{group['achievement']:.0f}%</span>
        </div>
        <div class="progress-container">
            <div class="progress-bar" style="width: {progress_pct}%; background-color: {status_color}; shadow: 0 0 4px {status_color}44;"></div>
        </div>
    </div>
    
    <!-- Payout -->
    <div class="payout-text">
        {payout_display}
    </div>
"""
    return clean_html(html)

def get_award_detail_html(group, period_stats, rows_df):
    """시상 상세 내역 HTML 생성 (Minified)"""
    
    # Container for details
    detail_container_style = """
        background: #F9FAFB; 
        padding: 1rem; 
        border-radius: 8px;
        margin-top: 0.5rem;
        margin-bottom: 1rem;
    """
    
    html_parts = []
    
    if '연속' in group['type'] and period_stats:
        # Container start
        html_parts.append(f'<div style="{detail_container_style}">')
        
        # 1. Period Summary Cards (Minimal)
        cards_html = """
        <div style="display: flex; gap: 1rem; overflow-x: auto; padding-bottom: 1rem; margin-bottom: 0.5rem; border-bottom: 1px solid #E5E7EB;">
        """
        
        sorted_p_keys = sorted(period_stats.keys(), key=lambda x: int(x))
        for p_num in sorted_p_keys:
            s = period_stats[p_num]
            s_start = pd.to_datetime(s.get('start')).strftime('%m.%d') if pd.notna(s.get('start')) else '-'
            s_end = pd.to_datetime(s.get('end')).strftime('%m.%d') if pd.notna(s.get('end')) else '-'
            perf = s.get('perf', 0)
            
            cards_html += f"""
            <div style="min_width: 140px; padding: 0.75rem; background: white; border: 1px solid #E5E7EB; border-radius: 8px;">
                <div style="font-size: 0.75rem; color: #6B7280; margin-bottom: 2px;">{p_num}구간 ({s_start}~{s_end})</div>
                <div style="font-size: 0.7rem; color: #9CA3AF;">누적 실적</div>
                <div style="font-size: 1rem; font-weight: 600; color: #374151;">{perf:,.0f}</div>
            </div>
            """
        cards_html += "</div>"
        html_parts.append(cards_html)
        
        # 2. Condition Matrix (Scenario-based Rows)
        
        # Check if we have 'scenarios' from backend (New Logic)
        scenarios = group.get('scenarios', [])
        
        if scenarios:
            # --- New Matrix View ---
            table_html = """
            <div style="font-size: 0.8rem; font-weight: 600; color: #374151; margin-bottom: 0.5rem;">📋 시상 상세조건 (조건별 시나리오)</div>
            <table style="width: 100%; border-collapse: collapse; font-size: 0.8rem;">
                <thead>
                    <tr style="text-align: right; color: #9CA3AF; border-bottom: 1px solid #E5E7EB;">
                        <th style="padding: 0.5rem; text-align: left; font-weight: 500;">구분</th>
            """
            
            # Header Columns for Periods
            for p_num in sorted_p_keys:
                perf = period_stats[p_num].get('perf', 0)
                table_html += f'<th style="padding: 0.5rem; font-weight: 500; text-align: right;">{p_num}구간<br><span style="font-size: 0.7rem; color: #6366F1;">실적: {perf:,.0f}</span></th>'
            
            table_html += """
                        <th style="padding: 0.5rem; font-weight: 500;">최종 시상금</th>
                    </tr>
                </thead>
                <tbody>
            """
            
            for idx, scen in enumerate(scenarios):
                row_html = f'<tr style="border-bottom: 1px dashed #F3F4F6; color: #4B5563;">'
                row_html += f'<td style="padding: 0.6rem 0.5rem; text-align: left;">Scenario {idx+1}</td>'
                
                # Check achievement for this scenario
                # We need to check if EACH period's target was met
                # But 'period_stats' only has AGGREGATED performance
                
                all_met = True
                
                for p_num in sorted_p_keys:
                    target = scen['targets'].get(p_num, 0)
                    perf = period_stats[p_num].get('perf', 0)
                    
                    is_met = (perf >= target) if target > 0 else True
                    if not is_met: all_met = False
                    
                    style = "color: #374151;"
                    if target > 0 and is_met:
                        style = "color: #10B981; font-weight: 600;" # Green if met
                    elif target > 0:
                        style = "color: #D1D5DB;" # Grey if not met
                        
                    val_str = f"{target:,.0f}" if target > 0 else "-"
                    row_html += f'<td style="padding: 0.6rem 0.5rem; text-align: right; {style}">{val_str}</td>'
                
                reward = scen.get('reward', 0)
                # Highlight reward if this scenario is fully met
                # Note: multiple scenarios might be met, but usually we take the highest.
                # Here we just highlight all met rows?
                # Or better, check if this reward matches the final payout?
                # Let's just use 'all_met' for now to highlight.
                
                r_style = "color: #4F46E5; font-weight: 600;"
                if all_met:
                     r_style = "color: #10B981; font-weight: 700; background: #ECFDF5; border-radius: 4px;"
                
                row_html += f'<td style="padding: 0.6rem 0.5rem; text-align: right;"><span style="{r_style}">{reward:,.0f}</span></td>'
                row_html += "</tr>"
                table_html += row_html
            
            table_html += "</tbody></table>"
            html_parts.append(table_html)
            
        else:
            # --- Old Fallback Logic (Independent Tiers) ---
            max_tiers = 0
            for s in period_stats.values():
                max_tiers = max(max_tiers, len(s.get('possible_targets', [])))
            
            table_html = """
            <div style="font-size: 0.8rem; font-weight: 600; color: #374151; margin-bottom: 0.5rem;">📋 시상 상세조건 (구간별 기준)</div>
            <table style="width: 100%; border-collapse: collapse; font-size: 0.8rem;">
                <thead>
                    <tr style="text-align: right; color: #9CA3AF; border-bottom: 1px solid #E5E7EB;">
                        <th style="padding: 0.5rem; text-align: left; font-weight: 500;">조건</th>
            """
            
            for p_num in sorted_p_keys:
                perf = period_stats[p_num].get('perf', 0)
                table_html += f'<th style="padding: 0.5rem; font-weight: 500; text-align: right;">{p_num}구간<br><span style="font-size: 0.7rem; color: #6366F1;">실적: {perf:,.0f}</span></th>'
            
            table_html += """
                        <th style="padding: 0.5rem; font-weight: 500;">시상금</th>
                    </tr>
                </thead>
                <tbody>
            """
            
            for i in range(max_tiers):
                tier_name = f"{i+1}차"
                row_html = f'<tr style="border-bottom: 1px dashed #F3F4F6; color: #4B5563;">'
                row_html += f'<td style="padding: 0.6rem 0.5rem;">{tier_name}</td>'
                
                final_reward = 0
                
                for p_num in sorted_p_keys:
                    s = period_stats[p_num]
                    targets = s.get('possible_targets', [])
                    
                    target_val = 0
                    if i < len(targets):
                        t_item = targets[i]
                        if isinstance(t_item, dict):
                            target_val = t_item.get('target', 0)
                            r = t_item.get('reward', 0)
                            if r > final_reward:
                                final_reward = r
                        else:
                            target_val = t_item
                    
                    perf = s.get('perf', 0)
                    # Highlight if achieved
                    style = "color: #D1D5DB;" if target_val == 0 else ""
                    if target_val > 0 and perf >= target_val:
                        style = "color: #10B981; font-weight: 600;" # Achieved
                    elif target > 0:
                        style = "color: #374151;"
                        
                    val_str = f"{target_val:,.0f}" if target_val > 0 else "-"
                    row_html += f'<td style="padding: 0.6rem 0.5rem; text-align: right; {style}">{val_str}</td>'
                
                row_html += f'<td style="padding: 0.6rem 0.5rem; text-align: right; font-weight: 600; color: #4F46E5;">{final_reward:,.0f}</td>'
                row_html += "</tr>"
                table_html += row_html
            
            table_html += "</tbody></table>"
            html_parts.append(table_html)
        
        html_parts.append("</div>") # Close container
        
    else:
        # 일반 시상용 리스트형 테이블 (Minimal)
        html_parts.append(f'<div style="{detail_container_style}">')
        html_parts.append("""
            <div style="font-size: 0.8rem; font-weight: 600; color: #374151; margin-bottom: 0.5rem;">📋 시상 상세조건</div>
            <table style="width: 100%; border-collapse: collapse; font-size: 0.8rem;">
                <thead>
                    <tr style="text-align: left; color: #9CA3AF; border-bottom: 1px solid #E5E7EB;">
                        <th style="padding: 0.5rem;">기간</th>
                        <th style="padding: 0.5rem; text-align: right;">목표</th>
                        <th style="padding: 0.5rem; text-align: right;">실적</th>
                        <th style="padding: 0.5rem; text-align: right;">지급액</th>
                        <th style="padding: 0.5rem; text-align: center;">달성률</th>
                        <th style="padding: 0.5rem; text-align: center;">상태</th>
                    </tr>
                </thead>
                <tbody>
        """)
    
        # [BugFix] 중복 행 제거: 데이터 처리 과정에서 발생한 중복 제거
        # 표시할 주요 컬럼 기준으로 중복 제거
        filtered_rows = rows_df.drop_duplicates(subset=['시작일', '종료일', '목표실적', '실적', '지급금액'])
        
        # 정렬: 날짜순 -> 목표금액 오름차순
        if not filtered_rows.empty:
            if '시작일' in filtered_rows.columns:
                filtered_rows = filtered_rows.sort_values(by=['시작일', '목표실적'])
            else:
                filtered_rows = filtered_rows.sort_values(by=['목표실적'])

        for row_idx, row in filtered_rows.iterrows():
            start_dt = pd.to_datetime(row.get('시작일', '')).strftime('%m.%d') if pd.notna(row.get('시작일')) else '-'
            end_dt = pd.to_datetime(row.get('종료일', '')).strftime('%m.%d') if pd.notna(row.get('종료일')) else '-'
            target = row.get('목표실적', 0)
            perf = row.get('실적', 0)
            payout = row.get('지급금액', 0)
            exp_pay = row.get('expected_payout', 0)
            achievement = row.get('달성률', 0)
            
            is_over = perf > target and target > 0
            is_achieved = payout > 0 or exp_pay > 0 or achievement >= 100
            
            # Payout Display
            payout_html = f"{payout:,.0f}"
            if payout == 0 and exp_pay > 0:
                payout_html = f"<span style='color:#F59E0B; font-size:0.75rem;'>(예상 {exp_pay:,.0f})</span>"
            
            # Status Badge
            if is_over:
                status_badge = "<span style='color: #8B5CF6; font-weight: 500;'>초과</span>"
                row_style = "background: #F5F3FF;"
            elif is_achieved:
                status_badge = "<span style='color: #10B981; font-weight: 500;'>달성</span>"
                row_style = ""
            else:
                status_badge = "<span style='color: #9CA3AF;'>미달</span>"
                row_style = ""
            
            html_parts.append(f"""
                <tr style="border-bottom: 1px dashed #F3F4F6; {row_style}">
                    <td style="padding: 0.6rem 0.5rem; color: #6B7280;">{start_dt}~{end_dt}</td>
                    <td style="padding: 0.6rem 0.5rem; text-align: right; color: #374151;">{target:,.0f}</td>
                    <td style="padding: 0.6rem 0.5rem; text-align: right; color: #6366F1; font-weight: 500;">{perf:,.0f}</td>
                    <td style="padding: 0.6rem 0.5rem; text-align: right; font-weight: 600; color: #111827;">{payout_html}</td>
                    <td style="padding: 0.6rem 0.5rem; text-align: center;">{achievement:.0f}%</td>
                    <td style="padding: 0.6rem 0.5rem; text-align: center;">{status_badge}</td>
                </tr>
            """)
        
        html_parts.append("</tbody></table></div>")
    
    # --- 추가: 인정 계약 (근거 데이터) 섹션 ---
    # rows_df에서 contracts_info 추출 (모든 행의 계약을 합쳐서 보여줌)
    all_contracts = []
    # 단순 rows뿐만 아니라 group 전체에서 가져올 수도 있지만 구조상 rows 안에 박혀있음
    # (calculate_single_award에서 contracts_info는 result의 최상위에 있지만, 
    #  get_award_detail_html에는 group 전체가 넘어오므로 group['contracts_info']를 쓰는게 맞음)
    
    source_contracts = group.get('contracts_info', [])
    if not source_contracts and 'rows' in group:
        # Fallback to rows if group level is missing (rare case with old logic)
         if 'contracts_info' in rows_df.columns:
            for idx, row in rows_df.iterrows():
                c_list = row.get('contracts_info', [])
                if isinstance(c_list, list): all_contracts.extend(c_list)
    else:
        all_contracts = source_contracts

    # 중복 제거 (dict list to unique)
    unique_contracts = []
    seen = set()
    for c in all_contracts:
        # 키: 접수일 + 상품명 + 보험료 + 계약자
        key = f"{c.get('접수일')}_{c.get('상품명')}_{c.get('보험료')}_{c.get('계약자')}"
        if key not in seen:
            seen.add(key)
            unique_contracts.append(c)
    
    if unique_contracts:
        html_parts.append(f"""
            <div style="font-size: 0.8rem; font-weight: 600; color: #374151; margin-top: 1.5rem; margin-bottom: 0.5rem; border-top: 1px solid #E5E7EB; padding-top: 1rem;">
                📄 인정 계약 (근거 데이터)
            </div>
            <table style="width: 100%; border-collapse: collapse; font-size: 0.75rem; color: #4B5563;">
                <thead>
                    <tr style="text-align: left; border-bottom: 1px solid #F3F4F6;">
                        <th style="padding: 0.5rem;">접수일</th>
                        <th style="padding: 0.5rem;">보험사</th>
                        <th style="padding: 0.5rem;">분류</th>
                        <th style="padding: 0.5rem;">상품명</th>
                        <th style="padding: 0.5rem;">계약자</th>
                        <th style="padding: 0.5rem; text-align: right;">보험료</th>
                    </tr>
                </thead>
                <tbody>
        """)
        
        # 최신순 정렬
        unique_contracts.sort(key=lambda x: str(x.get('접수일', '')), reverse=True)
        
        for c in unique_contracts[:50]: # 상위 50개
            date_str = pd.to_datetime(c.get('접수일')).strftime('%Y-%m-%d') if c.get('접수일') else '-'
            html_parts.append(f"""
                <tr style="border-bottom: 1px solid #F9FAFB;">
                    <td style="padding: 0.4rem 0.5rem;">{date_str}</td>
                    <td style="padding: 0.4rem 0.5rem;">{c.get('회사', c.get('원수사', '-'))}</td>
                    <td style="padding: 0.4rem 0.5rem;">{c.get('분류', '-')}</td>
                    <td style="padding: 0.4rem 0.5rem;">{c.get('상품명', '-')}</td>
                    <td style="padding: 0.4rem 0.5rem;">{c.get('계약자', '-')}</td>
                    <td style="padding: 0.4rem 0.5rem; text-align: right;">{c.get('보험료', 0):,.0f}</td>
                </tr>
            """)
        
        if len(unique_contracts) > 50:
             html_parts.append(f'<tr><td colspan="6" style="text-align: center; padding: 0.5rem; color: #9CA3AF;">... 외 {len(unique_contracts)-50}건 더 있음</td></tr>')
             
        html_parts.append("</tbody></table>")
    
    return clean_html("".join(html_parts))


def render_results_table(results_df: pd.DataFrame):
    """전체 시상 테이블 렌더링 (Figma 디자인 정확히 따라하기)"""
    
    # 헤더 및 범례
    st.markdown(textwrap.dedent("""
        <div style="margin-bottom: 0.5rem; display: flex; justify-content: space-between; align-items: flex-end;">
            <h3 style="margin: 0; font-size: 1.125rem; font-weight: 700; color: #111827;">📋 전체 시상 내역</h3>
            <div style="display: flex; gap: 1rem; font-size: 0.75rem; color: #6B7280; font-weight: 500;">
                <span style="display: flex; align-items: center; gap: 4px;"><span style="color: #4F46E5;">●</span> 초과 달성</span>
                <span style="display: flex; align-items: center; gap: 4px;"><span style="color: #10B981;">●</span> 달성 완료</span>
                <span style="display: flex; align-items: center; gap: 4px;"><span style="color: #F59E0B;">○</span> 진행중</span>
                <span style="display: flex; align-items: center; gap: 4px;"><span style="color: #EF4444;">●</span> 실패</span>
            </div>
        </div>
    """), unsafe_allow_html=True)
    
    if results_df.empty:
        st.info("표시할 시상 데이터가 없습니다.")
        return

    # --- 상단 컨트롤 패널 (심플 모드) ---
    c1, c2, b3, c3, c4, c5 = st.columns([1, 0.8, 0.8, 0.8, 0.7, 0.4])
    with c1:
        search_query = st.text_input("🔍 검색", placeholder="시상명 입력...", label_visibility="collapsed")
    with c2:
        all_companies = ["전체 보험사"] + sorted(results_df['회사'].unique().tolist())
        company_filter = st.selectbox("🏢 보험사", all_companies, label_visibility="collapsed")
    with b3:
        all_types = ["전체 유형"] + sorted(results_df['유형'].unique().tolist()) if '유형' in results_df.columns else ["전체 유형"]
        type_filter = st.selectbox("📝 유형", all_types, index=0, label_visibility="collapsed")
    with c3:
        status_filter = st.selectbox("🎯 상태", ["전체 상태", "초과달성", "달성완료", "진행중", "실패"], label_visibility="collapsed")
    with c4:
        sort_by = st.selectbox("🔃 정렬", ["달성률순", "지급금액순", "시작일순"], label_visibility="collapsed")
    with c5:
        expand_all = st.checkbox("펼치기", value=False)

    # 시상명 및 회사별로 그룹화
    award_groups = []
    grouped = results_df.groupby(['회사', '시상명'])
    
    for (company, award_name), group_df in grouped:
        # 1. 보험사 필터
        if company_filter != "전체 보험사" and company != company_filter: continue
        
        # 2. 검색 필터
        if search_query and search_query.lower() not in award_name.lower(): continue
        
        # 3. 데이터 중복 제거 및 정제 (핵심 수정)
        deduped_df = group_df.copy()
        # 중복 의심 컬럼들을 기준으로 중복 제거
        dedup_cols = ['시작일', '종료일', '목표실적', '실적', '지급금액', '최종지급금액']
        # 실제 존재하는 컬럼만 선택
        existing_dedup_cols = [c for c in dedup_cols if c in group_df.columns]
        if existing_dedup_cols:
             deduped_df = deduped_df.drop_duplicates(subset=existing_dedup_cols)

        # 목표실적 보정 (연속형 대응)
        total_target = deduped_df['목표실적'].max() if '목표실적' in deduped_df.columns else 0
        if (pd.isna(total_target) or total_target == 0) and not deduped_df.empty:
            # 연속형의 경우 period_stats에서 첫 구간 목표 추출
            if 'period_stats' in deduped_df.columns:
                stats = deduped_df['period_stats'].iloc[0]
                if isinstance(stats, dict) and (1 in stats or '1' in stats):
                    first_p = stats.get(1) or stats.get('1')
                    p_targets = first_p.get('possible_targets', [])
                    if p_targets:
                        target_val = p_targets[0].get('target', 0) if isinstance(p_targets[0], dict) else p_targets[0]
                        total_target = target_val
        
        # 최종 NaN 처리
        total_target = total_target if pd.notna(total_target) else 0
        
        # 지급금액 합산 (주의: 단순 합산시 중복 데이터 문제 발생 가능 -> deduped_df 사용)
        # 만약 '최종지급금액' 컬럼이 각 행마다 "전체 지급액"을 반복하고 있다면 max를 써야 함.
        # 하지만 통상적으로 각 row(단계)별 지급액의 합이라면 sum이 맞음.
        # 앞서 deduped_df로 중복 행(완전 동일)은 제거했으므로, 
        # 남은 행들이 "다른 조건"들이라면 sum, "동일 시상에 대한 단순 반복"이라면 max여야 함.
        # 현재 구조상 'Tiered'는 각 tier row가 있고, 'Consecutive'는 scenario row가 있을 수 있음.
        # 안전하게: 만약 award_type이 '전체'가 아니라면, 그리고 지급금액 컬럼 데이터가 모두 동일하다면 max를 취하는게 안전할 수 있으나,
        # 일단 deduped sum으로 접근. (User case implies 16x duplicates of the same row)
        
        # 유형 정의 (계산 로직에서 사용하기 위해 미리 정의)
        award_type = deduped_df['유형'].iloc[0] if '유형' in deduped_df.columns else ''

        # 지급금액 합산
        if '최종지급금액' in deduped_df.columns:
             # 기본적으로 합산
             total_payout = deduped_df['최종지급금액'].sum()

             # 연속형은 구조상 metadata row 반복일 수 있으므로 max 처리 (Double Counting 방지)
             if '연속' in award_type:
                 total_payout = deduped_df['최종지급금액'].max()
        else:
             total_payout = 0

        total_perf = deduped_df['실적'].max() if '실적' in deduped_df.columns else 0
        max_achievement = deduped_df['달성률'].max() if '달성률' in deduped_df.columns else 0
        
        # detail row로 사용할 때는 deduped_df 사용
        group_df = deduped_df 

        # 달성률 보정
        if total_target > 0 and '연속' not in award_type:
            max_achievement = (total_perf / total_target * 100.0)
            
        is_over_achieved = False
        is_achieved = total_payout > 0 or max_achievement >= 100

        if '연속' in award_type and total_payout == 0:
             max_achievement = 0
             is_achieved = False
             is_over_achieved = False
        
        if max_achievement > 100 and total_payout > 0:
             is_over_achieved = True

        # 상태 필터
        if status_filter == "달성완료" and not is_achieved: continue
        if status_filter == "초과달성" and not is_over_achieved: continue
        if status_filter == "실패" and not is_failed: continue
        if status_filter == "진행중":
            # 달성도 아니고 실패도 아닌 것
            if is_achieved or is_failed: continue

        # 유형 필터
        if type_filter != "전체 유형" and award_type != type_filter: continue

        # 최고 가능한 보상금액 추출 (Figma 요청사항)
        max_possible = 0
        if 'scenarios' in group_df.columns and not group_df['scenarios'].dropna().empty:
            scens = group_df['scenarios'].dropna().iloc[0]
            if isinstance(scens, list) and scens:
                max_possible = max([s.get('reward', 0) for s in scens])
        elif '보상금액' in group_df.columns:
            max_possible = group_df['보상금액'].max()
        elif '지급금액' in group_df.columns:
            max_possible = group_df['지급금액'].max()
            
        # 상품구분 추출 (사용자 요청: C열 '상품구분'만 엄격하게 사용, 유추 로직 제거)
        raw_cat = group_df['상품구분'].dropna().iloc[0] if '상품구분' in group_df.columns and not group_df['상품구분'].dropna().empty else '-'

        award_groups.append({
            'name': award_name,
            'company': company,
            'type': award_type,
            'payout': total_payout,
            'max_payout': max_possible,
            'achievement': max_achievement,
            'performance': total_perf,
            'target': total_target,
            'is_over_achieved': is_over_achieved,
            'is_achieved': is_achieved,
            'rows': group_df,
            'start_date': group_df['시작일'].min() if '시작일' in group_df.columns else pd.NaT,
            'end_date': group_df['종료일'].max() if '종료일' in group_df.columns else pd.NaT,
            'period_stats': group_df['period_stats'].dropna().iloc[0] if 'period_stats' in group_df.columns and not group_df['period_stats'].dropna().empty else None,
            'scenarios': group_df['scenarios'].dropna().iloc[0] if 'scenarios' in group_df.columns and not group_df['scenarios'].dropna().empty else [],
            'product_category': raw_cat if raw_cat else '-',
            'original_index': group_df.index.min(), # 원본 데이터 순서 추적용
            'expected_payout': group_df['예상지급금액'].max() if '예상지급금액' in group_df.columns else 0
        })
    
    # --- 정렬 적용 ---
    if sort_by == "지급금액순":
        award_groups.sort(key=lambda x: x['payout'], reverse=True)
    elif sort_by == "달성률순":
        award_groups.sort(key=lambda x: x['achievement'], reverse=True)
    else: # 시작일순
        # NaT values handles safely by sort
        award_groups.sort(key=lambda x: x['start_date'] if pd.notna(x['start_date']) else pd.Timestamp.min)
    
    # 테이블 본체 HTML 생성
    
    # 테이블 본체 HTML 생성
    table_rows_html = []
    open_attr = "open" if expand_all else ""
    
    for idx, group in enumerate(award_groups):
        # 상태 결정 및 스타일
        is_imminent = False
        is_past_missed = False
        
        current_date = pd.Timestamp.now().normalize()
        e_date = pd.to_datetime(group.get('end_date', pd.NaT))
        
        if group['is_over_achieved']:
            status_color, status_icon = "#8B5CF6", "🎯" # Indigo
        elif group['is_achieved']:
            status_color, status_icon = "#10B981", "✅" # Emerald
        elif group['achievement'] >= 80 and group['achievement'] < 100:
             # 임박 혹은 아까운 미달성
             if pd.notna(e_date) and e_date < current_date:
                 status_color, status_icon = "#EF4444", "❌"
                 is_past_missed = True
             else:
                 status_color, status_icon = "#F59E0B", "⏳" # Orange
                 is_imminent = True
        else:
            # 진행중 or 실패 판별
            s_date = pd.to_datetime(group.get('start_date', pd.NaT))
            
            is_expired = False
            if pd.notna(e_date) and current_date > e_date + pd.Timedelta(days=1): 
                 is_expired = True

            if is_expired:
                status_color, status_icon = "#EF4444", "❌" # Red (실패)
            else:
                # 진행중 아이콘
                status_color, status_icon = "#F59E0B", """
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" style="vertical-align: middle;">
                    <circle cx="12" cy="12" r="9" stroke="#F59E0B" stroke-width="2.5" />
                </svg>
                """

        # 유형 스타일
        type_styles = {'연속': {'bg': '#EEF2FF', 'color': '#4F46E5'}, '정률': {'bg': '#FEF3C7', 'color': '#B45309'}, '구간': {'bg': '#DBEAFE', 'color': '#1E40AF'}}
        type_style = type_styles.get(group['type'], {'bg': '#F3F4F6', 'color': '#374151'})
        
        s_date = group.get('start_date')
        e_date = group.get('end_date')
        if pd.notna(s_date) and pd.notna(e_date):
            period_str = f"{pd.to_datetime(s_date).strftime('%m.%d')}~{pd.to_datetime(e_date).strftime('%m.%d')}"
        else:
            period_str = "기간 정보 없음"
        
        exp_pay = group.get('expected_payout', 0)
        
        if group['payout'] > 0:
            payout_display = f"<span style='color: #10B981; font-weight: 700;'>{group['payout']:,.0f}원</span>"
        elif exp_pay > 0:
            # 지급 시기 미도래 (예상 금액 표시)
            payout_display = f"<span style='color: #F59E0B; font-weight: 600;'>0원</span><br><span style='font-size: 0.65rem; color: #F59E0B; font-weight: 500;'>(예상 {exp_pay:,.0f}원)</span>"
        else:
            payout_display = f"<span style='color: #6B7280; font-weight: 400;'>0원</span>"
            
        # Max amount always visible (small)
        if group['max_payout'] > 0:
            payout_display += f"<div style='font-size: 0.65rem; color: #94A3B8; font-weight: 400; margin-top: 2px;'>(최고 {group['max_payout']:,.0f}원)</div>"
        
        # Row HTML generation
        row_content = get_award_card_html(group, period_str, status_color, status_icon, type_style, payout_display, is_imminent, is_past_missed)
        detail_content = get_award_detail_html(group, group.get('period_stats'), group['rows'])
        
        # 고유 ID 생성 (스크롤용)
        safe_id = f"award-{group['company']}-{group['name']}".replace(" ", "-").replace("_", "-")
        
        # Auto-Expand Logic
        is_targeted = st.session_state.get('expanded_award') == group['name']
        current_open_attr = "open" if (expand_all or is_targeted) else ""
        
        item_html = f'<div class="award-item-row" id="{safe_id}"><details {current_open_attr}><summary class="award-summary">{row_content}</summary><div class="award-detail-panel">{detail_content}</div></details></div>'
        table_rows_html.append(item_html)
        
    full_table_html = f'<div class="award-table"><div class="award-table-header"><div style="text-align: center;">상태</div><div>시상명</div><div>유형</div><div>대상</div><div>기간</div><div style="text-align: right;">목표실적</div><div style="text-align: center;">실적 / 달성률</div><div style="text-align: right;">지급금액</div></div>{"".join(table_rows_html)}</div>'
    
    st.write(full_table_html, unsafe_allow_html=True)

    
    # 푸터
    st.markdown(textwrap.dedent(f"""
        <div style="display: flex; justify-content: space-between; align-items: center; padding: 0.75rem 0; font-size: 0.75rem; color: #6B7280;">
            <span>{len(award_groups)}개 시상 ({len(results_df)}행)</span>
        </div>
    """), unsafe_allow_html=True)



def render_product_statistics(contracts_df: pd.DataFrame):
    """2. 상품별/보험사별 통계 (표 형태)"""
    # Header moved to caller to allow injecting metrics between header and table
    
    if not contracts_df.empty:
        # 1. 원본 데이터 계산
        pivot_df = contracts_df.pivot_table(
            index='분류', 
            columns='회사', 
            values='보험료', 
            aggfunc='sum', 
            fill_value=0
        )
        
        # 2. 보험사별 합계 계산 및 정렬 (금액 높은 순)
        company_totals = pivot_df.sum().sort_values(ascending=False)
        sorted_companies = company_totals.index.tolist()
        
        # 3. 정렬된 컬럼 순서로 재배치
        pivot_df = pivot_df[sorted_companies]
        
        # 4. '합계' 열을 맨 앞에 추가
        pivot_df.insert(0, '합계', pivot_df.sum(axis=1))
        
        # 5. 행 정렬 ('합계' 열 기준 내림차순)
        pivot_df = pivot_df.sort_values(by='합계', ascending=False)
        
        # 6. '합계' 행을 맨 위에 추가
        total_row = pivot_df.sum().to_frame().T
        total_row.index = ['합계']
        pivot_df = pd.concat([total_row, pivot_df])
        
        # 스타일링 및 출력
        st.dataframe(
            pivot_df.style.format("{:,.0f}원"),
            use_container_width=True
        )
    else:
        st.info("통계 데이터가 없습니다.")

def render_performance_charts(contracts_df: pd.DataFrame, results_df: pd.DataFrame = None, display_period_start: datetime = None, display_period_end: datetime = None):
    """3. 실적 분석 추이 및 상세 내역 (차트)"""
    st.markdown('<div id="trend-section"></div>', unsafe_allow_html=True)
    
    # 조회 기간이 명시된 경우 해당 기간으로 먼저 타이트하게 필터링
    if display_period_start and display_period_end:
        from data_loader import filter_by_period
        contracts_df = filter_by_period(contracts_df, display_period_start, display_period_end)
    
    # 헤더
    st.subheader("📈 실적 분석 추이 및 상세 내역")
    chart_view = "모두 보기" # 고정값으로 설정 (버튼 제거)
    
    # 데이터 준비 및 필터링
    start_date = display_period_start
    end_date = display_period_end
    if (not start_date or not end_date) and results_df is not None and not results_df.empty:
        start_date = results_df['시작일'].min()
        end_date = results_df['종료일'].max()

    daily_df = get_daily_trend(contracts_df)
    if not daily_df.empty:
        # Convert to datetime and ensure it's at midnight to avoid timezone shifts in Altair
        daily_df['날짜'] = pd.to_datetime(daily_df['날짜'])
        
        filtered_daily = daily_df
        if start_date and end_date:
            filtered_daily = daily_df[(daily_df['날짜'] >= pd.to_datetime(start_date)) & 
                                     (daily_df['날짜'] <= pd.to_datetime(end_date))]
        
        if not filtered_daily.empty:
            # [CRITICAL] Full month expansion: Ensure chart shows all days from start to end
            # This makes the chart look consistent (1st to 28/30/31st)
            if start_date and end_date:
                # Target dates for the whole month
                full_range = pd.date_range(start=start_date, end=end_date, freq='D')
                full_df = pd.DataFrame({'날짜': full_range})
                
                # Normalize data to datetime for robust merging
                daily_to_merge = filtered_daily.copy()
                daily_to_merge['날짜'] = pd.to_datetime(daily_to_merge['날짜'])
                
                # Left join ensures every day of the month exists
                merged_df = pd.merge(full_df, daily_to_merge, on='날짜', how='left').fillna(0)
                
                # Cumulative logic: Carry forward previous value on empty days
                merged_df['누적실적'] = merged_df['누적실적'].replace(0, np.nan).ffill().fillna(0)
                
                # [NEW] Filter cumulative data to cut off at the last actual sale date
                # Finds the last date where '일실적' > 0
                actual_sales = merged_df[merged_df['일실적'] > 0]
                if not actual_sales.empty:
                    last_sale_date = actual_sales['날짜'].max()
                    # We keep one extra day if available to make the line look complete up to the last point
                    cumulative_df = merged_df[merged_df['날짜'] <= last_sale_date].copy()
                else:
                    cumulative_df = merged_df.copy()

                # Domain for X-axis (Explicitly forced to full month)
                x_domain = [start_date.isoformat(), end_date.isoformat()]
            else:
                merged_df = filtered_daily
                cumulative_df = filtered_daily
                x_domain = None

            # 그래프 영역 (비율 조정: 7:3)
            main_col, side_col = st.columns([7, 3])
            
            with main_col:
                import altair as alt
                # timeFormat uses local time, matching the browser's day() function
                axis_label_expr = "timeFormat(datum.value, '%m/%d') + ' ' + (['(일)', '(월)', '(화)', '(수)', '(목)', '(금)', '(토)'][day(datum.value)])"

                # Shared X axis configuration
                x_axis_config = alt.X('yearmonthdate(날짜):T', 
                    title=None, 
                    scale=alt.Scale(domain=x_domain, paddingInner=0.2) if x_domain else alt.Undefined,
                    axis=alt.Axis(
                        labelExpr=axis_label_expr, 
                        grid=False,
                        tickCount={'interval': 'day', 'step': 4}, # Adjust tick density for readability
                        labelOverlap=True,
                        labelAngle=-45
                    )
                )

                # [1] 누적 추이 차트 레이어 구성
                cumulative_base = alt.Chart(cumulative_df).transform_calculate(
                    label_text="format(round(datum.누적실적 / 10000), ',d') + '만'"
                ).encode(x=x_axis_config)
                
                # 면적/선 그래프
                cumulative_area = cumulative_base.mark_area(
                    line={'color': '#6366F1', 'strokeWidth': 2},
                    color=alt.Gradient(
                        gradient='linear',
                        stops=[alt.GradientStop(color='#6366F1', offset=0),
                               alt.GradientStop(color='rgba(99, 102, 241, 0.05)', offset=1)],
                        x1=1, x2=1, y1=1, y2=0
                    ),
                    interpolate='monotone'
                ).encode(
                    y=alt.Y('누적실적:Q', title="누적 보험료", axis=alt.Axis(grid=True, gridDash=[2,2], format=',.0f')),
                    tooltip=[
                        alt.Tooltip('날짜:T', title="날짜", format='%Y-%m-%d'), 
                        alt.Tooltip('누적실적:Q', format=',.0f', title="누적실적")
                    ]
                )

                # 마지막 지점 강조 (포인트 + 라벨)
                last_point_df = cumulative_df.tail(1)
                # Terminal base to ensure X-axis alignment
                terminal_base = alt.Chart(last_point_df).transform_calculate(
                    label_text="format(round(datum.누적실적 / 10000), ',d') + '만'"
                ).encode(
                    x=x_axis_config,
                    y=alt.Y('누적실적:Q')
                )

                cumulative_last_mark = terminal_base.mark_point(
                    size=60, color='#6366F1', fill='white', strokeWidth=2
                )
                
                cumulative_label = terminal_base.mark_text(
                    align='left', dx=8, fontSize=11, fontWeight='bold', color='#4F46E5', baseline='middle'
                ).encode(
                    text=alt.Text('label_text:N')
                )

                cumulative_final = alt.layer(cumulative_area, cumulative_last_mark, cumulative_label).properties(
                    height=280 if chart_view == "모두 보기" else 350
                )

                # [2] 일별 실적 차트 레이어 구성
                daily_base = alt.Chart(merged_df).transform_calculate(
                    label_text="format(round(datum.일실적 / 10000), ',d') + '만'"
                ).encode(x=x_axis_config)
                
                # 막대 그래프
                daily_bar = daily_base.mark_bar(
                    color='#6366F1',
                    cornerRadiusTopLeft=2,
                    cornerRadiusTopRight=2,
                    size=10
                ).encode(
                    y=alt.Y('일실적:Q', title="일일 보험료", axis=alt.Axis(grid=True, gridDash=[2,2], format=',.0f')),
                    tooltip=[
                        alt.Tooltip('날짜:T', title="날짜", format='%Y-%m-%d'), 
                        alt.Tooltip('일실적:Q', format=',.0f', title="일일실적")
                    ]
                )

                # 데이터 라벨 (막대 상단 - '만' 단위)
                daily_label = daily_base.mark_text(
                    align='center', baseline='bottom', dy=-2, dx=12, fontSize=9, color='#4F46E5', fontWeight='bold'
                ).encode(
                    y=alt.Y('일실적:Q'),
                    text=alt.Text('label_text:N')
                ).transform_filter(alt.datum.일실적 >= 5000) # 0.5만 이상인 경우만 표시

                daily_final = alt.layer(daily_bar, daily_label).properties(
                    height=280 if chart_view == "모두 보기" else 350
                )

                # 차트 출력
                if chart_view == "누적 추이":
                    st.altair_chart(cumulative_final, use_container_width=True)
                elif chart_view == "일별 실적":
                    st.altair_chart(daily_final, use_container_width=True)
                else:
                    st.altair_chart(cumulative_final, use_container_width=True)
                    st.altair_chart(daily_final, use_container_width=True)

            with side_col:
                
                weekday_map = {0: '월', 1: '화', 2: '수', 3: '목', 4: '금', 5: '토', 6: '일'}
                table_df = merged_df.copy()
                table_df['날짜_dt'] = pd.to_datetime(table_df['날짜'])
                table_df['표시날짜'] = table_df['날짜_dt'].apply(lambda x: f"{x.strftime('%m/%d')} ({weekday_map[x.weekday()]})")
                table_df = table_df.rename(columns={'일실적': '일일', '누적실적': '누적'})
                
                st.dataframe(
                    table_df[['날짜_dt', '표시날짜', '일일', '누적']].sort_values('날짜_dt', ascending=True).style.format({
                        '일일': '{:,.0f}원',
                        '누적': '{:,.0f}원'
                    }),
                    column_config={
                        "날짜_dt": None,
                        "표시날짜": st.column_config.TextColumn("날짜", width="small"),
                        "일일": st.column_config.TextColumn("일일", width="small"),
                        "누적": st.column_config.TextColumn("누적", width="small")
                    },
                    use_container_width=True,
                    hide_index=True,
                    column_order=("표시날짜", "일일", "누적"),
                    height=600 if chart_view == "모두 보기" else 350
                )
        else:
            st.info("해당 기간 내 실적이 없습니다.")
    else:
        st.info("데이터가 없습니다.")
    # st.markdown('</div>', unsafe_allow_html=True)


def render_footer_report(results_df: pd.DataFrame, contracts_df: pd.DataFrame, summary: dict, target_date: datetime):
    """성과 최적화 가이드 (제언 중심)"""
    # 중복되는 타이틀과 지표 카드는 제거하고 가이드 내용만 렌더링
    
    # 🎯 성과 최적화 가이드 로직 고도화
    current_time = pd.Timestamp.now().normalize()
    
    # 80~100% 사이인 항목들 (중복 제거)
    potential_df = results_df[(results_df['달성률'] >= 80) & (results_df['달성률'] < 100)].copy()
    potential_df = potential_df.drop_duplicates(subset=['시상명'])
    potential_df['end_date_dt'] = pd.to_datetime(potential_df['종료일'])
    
    ongoing_imminent = potential_df[potential_df['end_date_dt'] >= current_time]
    past_missed = potential_df[potential_df['end_date_dt'] < current_time]
    
    # [신규] 교차 최적화 분석 (Strategic Optimization)
    # 이미 만렙을 찍은 시상 -> 기회비용이 있는 시상으로 전환 추천
    try:
        optimization_recos = analyze_cross_company_optimization(results_df)
    except Exception as e:
        # print(f"Optimization Analysis Error: {e}")
        optimization_recos = []

    # 가이드 리스트업
    active_items = []
    history_items = []
    switch_items = [] # New list for strategic switches

    # 안전한 값 추출 함수 (스코프 복구)
    def get_v(row, keys, default=0):
        for k in keys:
            if k in row:
                val = row[k]
                if pd.notna(val): return val
        for k in keys:
            k_lower = k.lower().strip()
            for actual_k in row.index:
                if actual_k.lower().strip() == k_lower:
                    val = row[actual_k]
                    if pd.notna(val): return val
        return default

    # 0. 전략적 전환 (Priority 0)
    for reco in optimization_recos:
        sat = reco['saturated_item']
        opp = reco['opportunity_item']
        
        # 메시지 포매팅
        goal_text = "최고구간 도전 가능" if opp.get('is_max_tier') else "상위구간 달성 가능"
        switch_items.append({
            'type': 'SWITCH_STRATEGY',
            'title': f'🚀 {goal_text} 전략 발견!',
            'company': '전략 제안', # Badge용
            'sub': f"이미 만점인 <b>[{sat['company']}]</b> 대신<br/><b>[{opp['company']}]</b>에 집중하여 <span style='color:#0284C7; font-weight:700;'>+{opp['marginal_gain']:,.0f}원</span>을 더 챙기세요!",
            'badge': '✨ 전략적 집중 이동',
            'badge_class': 'badge-switch',
            'sat_info': sat,
            'opp_info': opp
        })

    # 1. 현재 진행중인 임박 시상 (액티브 가이드)
    for _, r in ongoing_imminent.head(3).iterrows():
        m_target = get_v(r, ['목표실적', 'target'])
        m_perf = get_v(r, ['실적', 'perf'])
        missing_amt = m_target - m_perf
        if missing_amt < 0: missing_amt = 0
        
        award_name = r.get('시상명', '')
        company = get_v(r, ['회사', '원수사', '보험사'], '')
        solidified = results_df[(results_df['시상명'] == award_name) & (results_df['회사'] == company)]['최종지급금액'].max()
        solidified = solidified if pd.notna(solidified) else 0
        
        potential_reward = get_v(r, ['기준보상', '보상금액', '지급금액'])
        diff_payout = potential_reward - solidified
        if diff_payout < 0: diff_payout = 0
        
        active_items.append({
            'type': 'IMMINENT',
            'title': award_name,
            'company': company,
            'target': m_target,
            'perf': m_perf,
            'missing': missing_amt,
            'reward': diff_payout,
            'sub': f"다음 단계까지 <span class='guide-amount-red'>{missing_amt:,.0f}원</span> (달성 시 <span style='color:#059669; font-weight:700;'>+{diff_payout:,.0f}원</span>)",
            'badge': '⚠️ 달성임박',
            'badge_class': 'badge-imm'
        })

    # 2. 과거의 아쉬운 결과 (복기용)
    for _, r in past_missed.head(3).iterrows():
        m_target = get_v(r, ['목표실적', 'target'])
        m_perf = get_v(r, ['실적', 'perf'])
        missing_amt = m_target - m_perf
        if missing_amt < 0: missing_amt = 0
        
        award_name = r.get('시상명', '')
        company = get_v(r, ['회사', '원수사', '보험사'], '')
        solidified = results_df[(results_df['시상명'] == award_name) & (results_df['회사'] == company)]['최종지급금액'].max()
        solidified = solidified if pd.notna(solidified) else 0
        
        potential_reward = get_v(r, ['기준보상', '보상금액', '지급금액'])
        loss_amt = potential_reward - solidified
        if loss_amt < 0: loss_amt = 0
        
        history_items.append({
            'title': award_name,
            'company': company,
            'target': m_target,
            'perf': m_perf,
            'missing': missing_amt,
            'reward': loss_amt,
            'sub': f"<span style='color:#EF4444; font-weight:600;'>{missing_amt:,.0f}원</span> 부족해서 <span style='color:#EF4444; font-weight:700;'>{loss_amt:,.0f}원</span>을 놓쳤습니다.",
            'badge': '😢 아쉬운 결과',
            'badge_class': 'badge-history'
        })

    # 가이드 표시 (Collapsible Expander + 2-Column Grid)
    if active_items or history_items or switch_items:
        with st.expander("🎯 AI 성과 최적화 가이드 (수익 극대화 전략 분석)", expanded=True):
            # 표시할 항목들을 하나의 리스트로 통합
            render_items = []
            for item in switch_items: render_items.append(('switch', item))
            for item in active_items: render_items.append(('active', item))
            for item in history_items: render_items.append(('history', item))
            
            # 2열 그리드 출력
            for i in range(0, len(render_items), 2):
                cols = st.columns(2)
                for j in range(2):
                    if i + j < len(render_items):
                        type, item = render_items[i + j]
                        with cols[j]:
                            if type == 'switch':
                                sat = item['sat_info']
                                opp = item['opp_info']
                                transfer_needed = opp['gap_to_best']
                                kb_optimized_perf = sat['perf'] - transfer_needed
                                
                                # Payout 정보 추출
                                sat_reward = sat.get('current_reward', 0)
                                opp_current_reward = opp.get('current_reward', 0)
                                opp_optimized_reward = opp.get('optimized_reward', 0)
                                
                                st.markdown(clean_html(f"""
<div class="sim-card">
    <div class="sim-header">
        <div style="display:flex; align-items:center; justify-content:space-between; width:100%;">
            <div style="display:flex; align-items:center; gap:8px;">
                <span style="background:#4F46E5; color:white; padding:2px 6px; border-radius:4px; font-size:0.65rem; font-weight:700;">전략 제안</span>
                <span style="font-size:0.9rem; font-weight:800; color:#1E293B;">이동 시 보상: <span style="color:#4F46E5;">+{opp['marginal_gain']:,.0f}원</span></span>
            </div>
            <div style="background:#F1F5F9; color:#64748B; padding:2px 8px; border-radius:12px; font-size:0.6rem; font-weight:600;">
                ⏱ {sat.get('period', '동일 기간')}
            </div>
        </div>
    </div>
    
    <!-- [현재] -->
    <div style="padding: 10px 15px 0 15px; font-size: 0.75rem; font-weight: 700; color: #E11D48;">[현재] 실적 불균형 상태</div>
    <div class="sim-row" style="padding:8px; gap:8px;">
        <div class="sim-box sim-box-current" style="padding:8px; border-color: #FECACA; background:#FFF1F2;">
            <div class="sim-comp-name" style="font-size:0.85rem; margin-bottom:2px;">{sat['company']}</div>
            <div style="font-size:0.65rem; color:#64748B; margin-bottom:5px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">{sat['award_name']}</div>
            <div class="sim-metric-line" style="font-size:0.7rem; margin-bottom:2px;"><span>목표:</span><span>{sat['max_target']:,.0f}</span></div>
            <div class="sim-metric-line" style="font-size:0.7rem; margin-bottom:2px;"><span>현재실적:</span><span>{sat['perf']:,.0f}</span></div>
            <div style="font-size:0.75rem; font-weight:700; color:#E11D48; border-top:1px dashed #FECACA; padding-top:4px; margin-top:4px; display:flex; justify-content:space-between;">
                <span>현재 보상:</span><span>{sat_reward:,.0f}원</span>
            </div>
        </div>
        <div class="sim-box sim-box-current" style="padding:8px;">
            <div class="sim-comp-name" style="font-size:0.85rem; margin-bottom:2px;">{opp['company']}</div>
            <div style="font-size:0.65rem; color:#64748B; margin-bottom:5px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">{opp['award_name']}</div>
            <div class="sim-metric-line" style="font-size:0.7rem; margin-bottom:2px;"><span>목표:</span><span>{opp['best_tier_target']:,.0f}</span></div>
            <div class="sim-metric-line" style="font-size:0.7rem; margin-bottom:2px;"><span>현재실적:</span><span>{opp['current_perf']:,.0f}</span></div>
            <div style="font-size:0.75rem; font-weight:700; color:#64748B; border-top:1px dashed #E2E8F0; padding-top:4px; margin-top:4px; display:flex; justify-content:space-between;">
                <span>현재 보상:</span><span>{opp_current_reward:,.0f}원</span>
            </div>
        </div>
    </div>

    <div class="sim-arrow-divider"><div class="sim-arrow-circle" style="width:20px; height:20px; font-size:0.55rem;">↓</div></div>

    <!-- [최적화] -->
    <div style="padding: 5px 15px 0 15px; font-size: 0.75rem; font-weight: 700; color: #0284C7;">[최적화] 전략적 실적 이동 결과</div>
    <div class="sim-row" style="padding:8px; gap:8px;">
        <div class="sim-box sim-box-optimized" style="padding:8px; border-color: #BAE6FD;">
            <div class="sim-comp-name" style="font-size:0.85rem; margin-bottom:2px;">{sat['company']}</div>
            <div style="font-size:0.65rem; color:#0284C7; font-weight:600; margin-bottom:4px;">최고구간 유지</div>
            <div class="sim-metric-line" style="font-size:0.7rem; margin-bottom:2px;"><span>목표:</span><span>{sat['max_target']:,.0f}</span></div>
            <div class="sim-metric-line" style="font-size:0.7rem; margin-bottom:2px;"><span>예상실적:</span><span>{kb_optimized_perf:,.0f}</span></div>
            <div style="font-size:0.75rem; font-weight:700; color:#059669; border-top:1px dashed #BAE6FD; padding-top:4px; margin-top:4px; display:flex; justify-content:space-between;">
                <span>보상 유지:</span><span>{sat_reward:,.0f}원</span>
            </div>
        </div>
        <div class="sim-box sim-box-optimized" style="border: 2px solid #0284C7; padding:8px; background:#F0F9FF;">
            <div class="sim-comp-name" style="font-size:0.85rem; margin-bottom:2px;">{opp['company']}</div>
            <div style="font-size:0.65rem; color:#0284C7; font-weight:600; margin-bottom:4px;">보상 획득 성공!</div>
            <div class="sim-metric-line" style="font-size:0.7rem; margin-bottom:2px;"><span>목표:</span><span>{opp['best_tier_target']:,.0f}</span></div>
            <div class="sim-metric-line" style="font-size:0.7rem; margin-bottom:2px;"><span>최종실적:</span><span>{opp['best_tier_target']:,.0f}</span></div>
            <div style="font-size:0.75rem; font-weight:800; color:#0284C7; border-top:1px dashed #BAE6FD; padding-top:4px; margin-top:4px; display:flex; justify-content:space-between;">
                <span>최종 보상:</span><span>{opp_optimized_reward:,.0f}원</span>
            </div>
        </div>
    </div>
    <div style="background: #F8FAFC; padding: 8px 15px; font-size: 0.65rem; color: #475569; border-top: 1px solid #F1F5F9; line-height:1.4;">
        💡 <b>코칭:</b> {sat['company']}의 여유 실적을 {opp['company']}로 전환하여 기존 시상금은 지키고 <b>{opp['marginal_gain']:,.0f}원</b>을 추가로 획득하세요.
    </div>
</div>
"""), unsafe_allow_html=True)

                            elif type == 'active':
                                st.markdown(clean_html(f"""
                                <div class="guide-card-active" style="margin-bottom:16px; padding:12px !important;">
                                    <div style="display:flex; justify-content:space-between; align-items:start; margin-bottom:6px;">
                                        <div>
                                            <div class="guide-badge-pill {item['badge_class']}">{item['badge']}</div>
                                            <div class="guide-title-main" style="font-size:1rem; line-height:1.2;">{item['title']}</div>
                                            <div class="guide-company-sub" style="margin-bottom:0;">{item['company']}</div>
                                        </div>
                                        <div style="text-align:right;">
                                            <div style="font-size:0.65rem; color:#94A3B8; font-weight:600;">추가 보상액</div>
                                            <div style="font-size:1.1rem; font-weight:800; color:#059669;">+{item['reward']:,.0f}원</div>
                                        </div>
                                    </div>
                                    <div style="display:grid; grid-template-columns: 1fr 1fr 1fr; gap:8px; background:#F8FAFC; padding:10px; border-radius:8px; border:1px solid #F1F5F9;">
                                        <div>
                                            <div style="font-size:0.6rem; color:#94A3B8; margin-bottom:2px;">다음 목표</div>
                                            <div style="font-size:0.85rem; font-weight:700; color:#1E293B;">{item['target']:,.0f}</div>
                                        </div>
                                        <div>
                                            <div style="font-size:0.6rem; color:#94A3B8; margin-bottom:2px;">현재 실적</div>
                                            <div style="font-size:0.85rem; font-weight:700; color:#1E293B;">{item['perf']:,.0f}</div>
                                        </div>
                                        <div style="border-left:1px solid #E2E8F0; padding-left:8px;">
                                            <div style="font-size:0.6rem; color:#E11D48; margin-bottom:2px; font-weight:600;">부족분</div>
                                            <div style="font-size:0.85rem; font-weight:800; color:#E11D48;">-{item['missing']:,.0f}</div>
                                        </div>
                                    </div>
                                </div>
                                """), unsafe_allow_html=True)

                            elif type == 'history':
                                st.markdown(clean_html(f"""
                                <div class="guide-card-active" style="border-color:#F1F5F9; background:#FAFAFA; margin-bottom:16px; padding:12px !important;">
                                    <div style="display:flex; justify-content:space-between; align-items:start; margin-bottom:6px;">
                                        <div>
                                            <div class="guide-badge-pill {item['badge_class']}">{item['badge']}</div>
                                            <div class="guide-title-main" style="color:#64748B; font-size:1rem; line-height:1.2;">{item['title']}</div>
                                            <div class="guide-company-sub" style="margin-bottom:0;">{item['company']}</div>
                                        </div>
                                        <div style="text-align:right;">
                                            <div style="font-size:0.65rem; color:#94A3B8; font-weight:600;">실수령 손실</div>
                                            <div style="font-size:1.1rem; font-weight:700; color:#EF4444;">-{item['reward']:,.0f}원</div>
                                        </div>
                                    </div>
                                    <div style="display:grid; grid-template-columns: 1fr 1fr 1fr; gap:8px; background:white; padding:10px; border-radius:8px; border:1px solid #F1F5F9;">
                                        <div><div style="font-size:0.6rem; color:#94A3B8;">목표</div><div style="font-size:0.85rem; font-weight:600;">{item['target']:,.0f}</div></div>
                                        <div><div style="font-size:0.6rem; color:#94A3B8;">마감</div><div style="font-size:0.85rem; font-weight:600;">{item['perf']:,.0f}</div></div>
                                        <div style="border-left:1px solid #F1F5F9; padding-left:8px;"><div style="font-size:0.6rem; color:#64748B;">미달</div><div style="font-size:0.85rem; font-weight:600; color:#64748B;">{item['missing']:,.0f}</div></div>
                                    </div>
                                </div>
                                """), unsafe_allow_html=True)




def render_pivot_analysis(contracts_df: pd.DataFrame):
    """전략 전환 시점 분석"""
    pivot = pivot_analysis(contracts_df)
    
    if pivot:
        st.header("💡 전략 전환 제안")
        st.warning(pivot['메시지'])
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("전환 전 일평균", f"{pivot['전환전평균']:,.0f}원")
        with col2:
            st.metric("전환 후 일평균", f"{pivot['전환후평균']:,.0f}원", 
                      delta=f"{pivot['전환후평균'] - pivot['전환전평균']:,.0f}원")



def main():
    """메인 함수"""
    from data_loader import filter_by_period
    init_session_state()
    
    # 1. 데이터 로드 여부에 따라 컨트롤 및 매개변수 준비
    if st.session_state.data_loaded:
        calc_params = render_main_controls()
    else:
        calc_params = None
    
    # 데이터가 로드되지 않은 경우 초기 안내 화면
    if not st.session_state.data_loaded:
        st.markdown('<div style="margin-top: 100px;"></div>', unsafe_allow_html=True)
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.info("""
            👋 **반갑습니다! 인센티브 대시보드입니다.**
            
            시작하려면 구글 스프레드시트를 연결하거나 CSV 파일을 업로드해야 합니다.
            아래 버튼을 눌러 데이터 설정을 완료해 주세요.
            """)
            if st.button("⚙️ 데이터 연결 및 설정하기", type="primary", use_container_width=True):
                data_settings_modal()
        return

    # 데이터 검증 (생략 - 기존 로직 유지)

    # 2. 계산 및 렌더링 실행
    if calc_params:
        with st.spinner("인센티브 계산 중..."):
            try:
                if calc_params['agent_name']:
                    # [Scroll to Top]
                    st.components.v1.html("<script>window.parent.window.scrollTo(0,0);</script>", height=0)
                    
                    # --- 설계사별 상세 대시보드 ---
                    
                    summary = {}
                    processed_df, _ = preprocess_contracts(
                        st.session_state.contracts_df,
                        agent_name=calc_params['agent_name']
                    )
                    if calc_params['product_filter']:
                        processed_df = processed_df[processed_df['분류'].isin(calc_params['product_filter'])]
                    
                    # 캐싱된 배치 계산에서 해당 설계사 데이터만 추출
                    with st.spinner(f"{calc_params['agent_name']}님 시상 내역 로드 중..."):
                        all_results_df = get_batch_calculation(
                            st.session_state.contracts_df,
                            st.session_state.rules_df,
                            calc_params['period_start'],
                            calc_params['period_end'],
                            calc_params['company']
                        )
                        
                        if not all_results_df.empty:
                            results = all_results_df[all_results_df['설계사'] == calc_params['agent_name']].copy()
                            
                            # 중복 제거된 시상명-인덱스 맵 생성 및 정렬
                            rule_order_map = st.session_state.rules_df[['시상명']].reset_index().drop_duplicates(subset=['시상명'])
                            temp_results = pd.merge(results, rule_order_map, on='시상명', how='left')
                            temp_results.rename(columns={'index': 'rule_order'}, inplace=True)
                            results = temp_results.sort_values('rule_order').drop(columns=['rule_order'])
                            
                            st.session_state.results_df = results
                            summary = get_award_summary(results)
                            
                            results = resolve_competing_awards(results)
                            st.session_state.results_df = results
                            summary = get_award_summary(results)
                        else:
                            results = pd.DataFrame()
                            summary = {'총지급예상금액': 0, '시상개수': 0, '선택된시상개수': 0, '평균달성률': 0}

                    # 총실적 및 회사별 실적 계산 (월간 기준 엄격 필터링)
                    month_filtered_df = filter_by_period(processed_df, calc_params['period_start'], calc_params['period_end'])
                    summary['총실적'] = month_filtered_df['보험료'].sum()
                    summary['당월계약건수'] = len(month_filtered_df)
                    
                    # 회사별 실적 집계 (지표 카드용)
                    kb_perf = 0
                    sam_perf = 0
                    if '회사' in month_filtered_df.columns:
                        kb_perf = month_filtered_df[month_filtered_df['회사'].str.contains('KB', case=False, na=False)]['보험료'].sum()
                        sam_perf = month_filtered_df[month_filtered_df['회사'].str.contains('삼성', case=False, na=False)]['보험료'].sum()
                    
                    summary['company_performance'] = {
                        'KB': kb_perf,
                        '삼성': sam_perf,
                        '기타': max(0, summary['총실적'] - kb_perf - sam_perf)
                    }
                    
                    summary['period_start'] = calc_params['period_start']
                    summary['period_end'] = calc_params['period_end']
                    
                    # 1. 메인 통계 지표 카드 + 2. 보험사별/상품별 실적 통계
                    st.markdown('<div id="stats-section"></div>', unsafe_allow_html=True)
                    st.subheader("📊 보험사별/상품별 실적 통계")
                    
                    render_metrics(summary)
                    render_product_statistics(month_filtered_df)
                    
                    # 3. 월간 계약 데이터 상세 보기 (Expander)
                    with st.expander(f"📅 {calc_params['target_date'].strftime('%Y년 %m월')} {calc_params['agent_name']}님 상세 계약 내역", expanded=False):
                        if not month_filtered_df.empty:
                            rename_map = {'설계사': '사원명', '모집인명': '사원명', '회사': '보험사', '원수사': '보험사'}
                            display_contracts = month_filtered_df.rename(columns=rename_map)
                            display_contracts = display_contracts.loc[:, ~display_contracts.columns.duplicated()]
                            
                            target_cols = ['접수일', '보험사', '분류', '상품명', '보험료', '계약자']
                            valid_cols = [c for c in target_cols if c in display_contracts.columns]
                            display_contracts = display_contracts[valid_cols].sort_values('접수일', ascending=False)
                            
                            st.dataframe(
                                display_contracts.style.format({'보험료': '{:,.0f}원'}),
                                column_config={"접수일": st.column_config.DateColumn("접수일", format="YYYY-MM-DD")},
                                use_container_width=True, hide_index=True
                            )
                        else:
                            st.info("해당 기간의 계약 내역이 없습니다.")
                    
                    # 4. 실적 분석 추이 및 상세 내역 그래프
                    st.markdown('<div id="trend-section"></div>', unsafe_allow_html=True)
                    render_performance_charts(processed_df, results, calc_params['period_start'], calc_params['period_end'])
                    
                    # 5. 성과 분석 및 전략 가이드
                    if not results.empty:
                         render_footer_report(results, processed_df, summary, calc_params['target_date'])

                    # 6. 시상 상세 내역 테이블 (하단 배치)
                    if not results.empty:
                        st.markdown('<div id="history-section"></div>', unsafe_allow_html=True)
                        st.subheader("🏆 달성 시상 상세 내역")
                        render_results_table(results)
                elif st.session_state.get('selected_team'):
                    # [Scroll to Top]
                    st.components.v1.html("<script>window.parent.window.scrollTo(0,0);</script>", height=0)
                    
                    # --- 팀별 상세 대시보드 ---
                    team_name = st.session_state.selected_team
                    
                    # (상단 네비게이션이 헤더로 이동함)

                    # 데이터 준비 (캐시 또는 재계산)

                    # 데이터 준비 (캐시 또는 재계산)
                    current_period = (calc_params['period_start'], calc_params['period_end'])
                    
                    if 'last_all_results' not in st.session_state or st.session_state.last_all_results is None:
                         # 데이터가 없으면 계산
                         with st.spinner("데이터 로드 중..."):
                            all_results_df = get_batch_calculation(
                                st.session_state.contracts_df, st.session_state.rules_df,
                                calc_params['period_start'], calc_params['period_end'], calc_params['company']
                            )
                            st.session_state.last_all_results = all_results_df
                    else:
                        all_results_df = st.session_state.last_all_results
                    
                    # 팀별 데이터 필터링
                    processed_all, _ = preprocess_contracts(st.session_state.contracts_df, agent_name=None)
                    team_agents = processed_all[processed_all['지점'] == team_name]['사원명'].unique()
                    
                    # 1. 계약 데이터 필터링
                    team_contracts = filter_by_period(processed_all[processed_all['지점'] == team_name], 
                                                      calc_params['period_start'], calc_params['period_end'])
                    # 2. 결과 데이터 필터링
                    team_results = all_results_df[all_results_df['설계사'].isin(team_agents)].copy()
                    
                    # 요약 통계 생성
                    # agg_df (설계사별 집계)가 있으면 재활용, 없으면 생성
                    agg_df = st.session_state.get('agg_result_df', pd.DataFrame())
                    if agg_df.empty and not team_results.empty:
                        # (Main logic logic duplicated simplistically if needed, or rely on agg_df being present from main)
                        # Main dashboard usually runs first, so agg_df should be there. 
                        pass

                    team_agg = agg_df[agg_df['소속'] == team_name] if not agg_df.empty else pd.DataFrame()
                    
                    summary = {
                        '총지급예상금액': team_results[team_results['선택여부'] == True]['최종지급금액'].sum() if not team_results.empty else 0,
                        '총실적': team_contracts['보험료'].sum(),
                        'company_performance': {
                            'KB': team_agg['KB실적'].sum() if not team_agg.empty else 0,
                            '삼성': team_agg['삼성실적'].sum() if not team_agg.empty else 0,
                            '기타': team_agg['기타실적'].sum() if not team_agg.empty else 0
                        },
                        '당월계약건수': len(team_contracts),
                        'period_start': calc_params['period_start'],
                        'period_end': calc_params['period_end']
                    }
                    
                    # 1. 메인 통계 지표 + 2. 상품 통계 (순서 변경 및 헤더 통합)
                    st.markdown('<div id="stats-section"></div>', unsafe_allow_html=True)
                    st.subheader("📊 보험사별/상품별 실적 통계")
                    
                    render_metrics(summary)
                    render_product_statistics(team_contracts)
                    
                    # 3. 추이 차트 (Team Scope)
                    # render_performance_charts expects filtered processed_df? No, it takes full processed_df and filters inside? 
                    # Actually it filters by agent if single agent. Here we pass team-filtered processed_df?
                    # Let's verify render_performance_charts signature. 
                    # It takes (contracts_df, results_df, start, end). 
                    # We pass team filtered contracts.
                    st.markdown('<div id="trend-section"></div>', unsafe_allow_html=True)
                    render_performance_charts(processed_all[processed_all['지점'] == team_name], 
                                              team_results, calc_params['period_start'], calc_params['period_end'])
                    
                    # 4. 팀원 리스트 (테이블형)
                    st.markdown('<div id="agent-section"></div>', unsafe_allow_html=True)
                    st.markdown("### 👥 팀원 현황")
                    if not team_agg.empty:
                        # 정렬 컨트롤
                        s_col1, s_col2 = st.columns([2, 3])
                        with s_col1:
                            sort_by = st.selectbox("정렬 기준", ["실적 높은 순", "인센티브 높은 순", "지급률 높은 순", "이름순"], key="team_member_sort_key")
                        
                        # 데이터 정렬
                        sorted_team_agg = team_agg.copy()
                        if sort_by == "실적 높은 순": sorted_team_agg = sorted_team_agg.sort_values('총실적', ascending=False)
                        elif sort_by == "인센티브 높은 순": sorted_team_agg = sorted_team_agg.sort_values('총지급액', ascending=False)
                        elif sort_by == "지급률 높은 순": sorted_team_agg = sorted_team_agg.sort_values('지급률', ascending=False)
                        elif sort_by == "이름순": sorted_team_agg = sorted_team_agg.sort_values('설계사', ascending=True)

                        # [Agent Table] 헤더
                        st.markdown("""
                        <div style="display:flex; align-items:center; padding:0.8rem 1rem; background:#F9FAFB; border-top:1px solid #E5E7EB; border-bottom:1px solid #E5E7EB; font-weight:600; color:#4B5563; font-size:0.9rem;">
                            <div style="flex:1.2; text-align:left;">설계사 / 지점</div>
                            <div style="flex:1.2; text-align:right;">총 예상 인센티브</div>
                            <div style="flex:0.8; text-align:right;">지급률</div>
                            <div style="flex:1.2; text-align:right;">전체 실적</div>
                            <div style="flex:1; text-align:right; color:#2563EB;">🔵 삼성</div>
                            <div style="flex:1; text-align:right; color:#D97706;">🟡 KB</div>
                            <div style="flex:1; text-align:right; color:#059669;">🟢 기타</div>
                            <div style="flex:0.8; text-align:center;">상세</div>
                        </div>
                        """, unsafe_allow_html=True)

                        for idx, row in sorted_team_agg.iterrows():
                             with st.container():
                                 cols = st.columns([1.2, 1.2, 0.8, 1.2, 1, 1, 1, 0.8])
                                 with cols[0]:
                                     st.markdown(f"""
                                     <div style='padding-top:10px;'>
                                         <span style='font-weight:600; color:#1F2937;'>{row['설계사']}</span>
                                         <span style='font-size:0.8em; color:#6B7280; display:block;'>{team_name}</span>
                                     </div>
                                     """, unsafe_allow_html=True)
                                 
                                 with cols[1]:
                                     st.markdown(f"<div style='text-align:right; font-weight:700; color:#4F46E5; padding-top:10px;'>{row['총지급액']:,.0f}</div>", unsafe_allow_html=True)
                                 with cols[2]:
                                     st.markdown(f"<div style='text-align:right; color:#4B5563; padding-top:10px;'>{row['지급률']:.1f}%</div>", unsafe_allow_html=True)
                                 with cols[3]:
                                     st.markdown(f"<div style='text-align:right; font-weight:600; color:#111827; padding-top:10px;'>{row['총실적']:,.0f}</div>", unsafe_allow_html=True)
                                 with cols[4]:
                                     st.markdown(f"<div style='text-align:right; color:#6B7280; font-size:0.9rem; padding-top:10px;'>{row['삼성실적']:,.0f}</div>", unsafe_allow_html=True)
                                 with cols[5]:
                                     st.markdown(f"<div style='text-align:right; color:#6B7280; font-size:0.9rem; padding-top:10px;'>{row['KB실적']:,.0f}</div>", unsafe_allow_html=True)
                                 with cols[6]:
                                     st.markdown(f"<div style='text-align:right; color:#6B7280; font-size:0.9rem; padding-top:10px;'>{row['기타실적']:,.0f}</div>", unsafe_allow_html=True)
                                 with cols[7]:
                                     if st.button("조회", key=f"btn_team_detail_member_{idx}", use_container_width=True):
                                         st.session_state.selected_agent = row['설계사']
                                         st.session_state.selected_team = None
                                         st.rerun()
                                 st.markdown("<div style='border-bottom:1px solid #F3F4F6; margin-bottom:5px;'></div>", unsafe_allow_html=True)



                else:
                    # [Scroll to Top] (Only if we were in detailed view before)
                    if st.session_state.get('last_view') != 'main':
                        st.components.v1.html("<script>window.parent.window.scrollTo(0,0);</script>", height=0)
                        st.session_state.last_view = 'main'
                            
                    # 전체 보기 (메인 대시보드)
                    current_period = (calc_params['period_start'], calc_params['period_end'])
                    
                    # 렌더링용 집계 데이터 초기화 (세션에서 복구 또는 빈 객체)
                    agg_df = st.session_state.get('agg_result_df', pd.DataFrame())
                    summary = st.session_state.get('dashboard_summary', {})
                    
                    # 1. 계산이 필요한 경우: 기간이 변경됨 OR 캐시된 데이터가 없음
                    need_recalc = (
                        'last_dashboard_period' not in st.session_state or 
                        st.session_state.last_dashboard_period != current_period or 
                        'last_all_results' not in st.session_state
                    )
                    
                    if need_recalc:
                        with st.spinner("전체 실적 집계 및 시상 계산 중..."):
                            all_results_df = get_batch_calculation(
                                st.session_state.contracts_df,
                                st.session_state.rules_df,
                                calc_params['period_start'],
                                calc_params['period_end'],
                                calc_params['company']
                            )
                            st.session_state.last_all_results = all_results_df
                            st.session_state.last_dashboard_period = current_period
                    else:
                        all_results_df = st.session_state.last_all_results

                    # 2. 결과 가공 및 요약 (결과가 있을 때만)
                    if not all_results_df.empty:
                        processed_df, _ = preprocess_contracts(st.session_state.contracts_df, agent_name=None)
                        if calc_params['product_filter']:
                            processed_df = processed_df[processed_df['분류'].isin(calc_params['product_filter'])]
                        
                        filtered_all = all_results_df.copy()
                        if calc_params['type_filter']:
                            filtered_all = filtered_all[filtered_all['유형'].isin(calc_params['type_filter'])]

                        # 설계사별 요약 집계
                        agent_payouts = []
                        agent_groups = filtered_all.groupby('설계사')
                        
                        for agent, group in agent_groups:
                            p_df = processed_df[processed_df['사원명'] == agent]
                            month_filtered_p_df = filter_by_period(p_df, calc_params['period_start'], calc_params['period_end'])
                            t_perf = month_filtered_p_df['보험료'].sum()
                            
                            total_payout = group[group['선택여부'] == True]['최종지급금액'].sum()
                            
                            # 회사별 지표
                            kb_pay = group[(group['회사'].str.contains('KB', case=False, na=False)) & (group['선택여부'] == True)]['최종지급금액'].sum()
                            sam_pay = group[(group['회사'].str.contains('삼성', case=False, na=False)) & (group['선택여부'] == True)]['최종지급금액'].sum()
                            kb_perf = 0
                            sam_perf = 0
                            if '회사' in month_filtered_p_df.columns:
                                kb_perf = month_filtered_p_df[month_filtered_p_df['회사'].str.contains('KB', case=False, na=False)]['보험료'].sum()
                                sam_perf = month_filtered_p_df[month_filtered_p_df['회사'].str.contains('삼성', case=False, na=False)]['보험료'].sum()

                            others_perf = max(0, t_perf - kb_perf - sam_perf)

                            if total_payout > 0 or t_perf > 0:
                                agent_payouts.append({
                                    '설계사': agent,
                                    '소속': p_df['지점'].iloc[0] if not p_df.empty and '지점' in p_df.columns else '-',
                                    '총지급액': total_payout,
                                    '지급률': (total_payout / t_perf * 100) if t_perf > 0 else 0,
                                    '총실적': t_perf,
                                    'KB실적': kb_perf,
                                    '삼성실적': sam_perf,
                                    '기타실적': others_perf,
                                    '코칭필요': any(80 <= r.get('달성률', 0) < 100 for _, r in group.iterrows()),
                                    '놓친기회금액': sum(max(0, r.get('지급금액', 0) - r.get('최종지급금액', 0)) for _, r in group.iterrows() if 80 <= r.get('달성률', 0) < 100)
                                })
                        
                        agg_df = pd.DataFrame(agent_payouts)
                        summary = {
                            '총지급예상금액': filtered_all[filtered_all['선택여부'] == True]['최종지급금액'].sum(),
                            '총실적': processed_df[(processed_df['접수일'] >= pd.Timestamp(calc_params['period_start'])) & (processed_df['접수일'] <= pd.Timestamp(calc_params['period_end']))]['보험료'].sum(),
                            'company_performance': {
                                'KB': agg_df['KB실적'].sum() if not agg_df.empty else 0,
                                '삼성': agg_df['삼성실적'].sum() if not agg_df.empty else 0,
                                '기타': agg_df['기타실적'].sum() if not agg_df.empty else 0
                            },
                            '당월계약건수': len(processed_df[(processed_df['접수일'] >= pd.Timestamp(calc_params['period_start'])) & (processed_df['접수일'] <= pd.Timestamp(calc_params['period_end']))])
                        }
                        
                        # 지표 업데이트
                        st.session_state.agg_result_df = agg_df
                        st.session_state.dashboard_summary = summary

                    if not agg_df.empty:
                        # 화면 렌더링에 사용할 월별 필터링 데이터 준비
                        monthly_stats_df = filter_by_period(processed_df, calc_params['period_start'], calc_params['period_end'])

                        # 1. 메인 통계 지표 + 2. 보험사별/상품별 실적 통계 (순서 변경 및 헤더 통합)
                        st.markdown('<div id="stats-section"></div>', unsafe_allow_html=True)
                        st.subheader("📊 보험사별/상품별 실적 통계")
                        
                        render_metrics(summary)
                        render_product_statistics(monthly_stats_df)
                        
                        # 월간 계약 데이터 상세 보기 (위치 이동: 통계 바로 아래)
                        with st.expander(f"📅 {calc_params['target_date'].strftime('%Y년 %m월')} 전체 계약 내역 상세보기", expanded=False):
                            if not monthly_stats_df.empty:
                                # 컬럼명 표준화 및 가공 로직
                                rename_map = {'설계사': '사원명', '모집인명': '사원명', '회사': '보험사', '원수사': '보험사'}
                                display_contracts = monthly_stats_df.rename(columns=rename_map)
                                display_contracts = display_contracts.loc[:, ~display_contracts.columns.duplicated()]
                                
                                target_cols = ['접수일', '사원명', '보험사', '분류', '상품명', '보험료', '계약자']
                                valid_cols = [c for c in target_cols if c in display_contracts.columns]
                                display_contracts = display_contracts[valid_cols].sort_values('접수일', ascending=False)
                                
                                st.dataframe(
                                    display_contracts.style.format({'보험료': '{:,.0f}원'}),
                                    column_config={"접수일": st.column_config.DateColumn("접수일", format="YYYY-MM-DD")},
                                    use_container_width=True, hide_index=True
                                )
                                st.caption(f"* 총 {len(display_contracts)}건의 계약이 조회되었습니다.")
                            else:
                                st.info("해당 기간의 계약 내역이 없습니다.")
                        
                        # 3. 📈 실적 분석 추이 및 상세 내역
                        st.markdown('<div id="trend-section"></div>', unsafe_allow_html=True)
                        render_performance_charts(processed_df, display_period_start=calc_params['period_start'], display_period_end=calc_params['period_end'])

                        # 4. 현황 섹션 (팀별 / 설계사별 상하 구분)
                        if not agg_df.empty:
                            st.markdown('<div id="status-section" style="height: 20px;"></div>', unsafe_allow_html=True)
                            
                            # --- A) 🏢 팀별 현황 섹션 ---
                            st.markdown('<div id="team-section"></div>', unsafe_allow_html=True)
                            st.markdown("### 🏢 팀별 현황", unsafe_allow_html=True)
                            
                            # 팀별 집계
                            team_agg = agg_df.groupby('소속').agg({
                                '설계사': 'count',
                                '총실적': 'sum',
                                '총지급액': 'sum',
                                'KB실적': 'sum',
                                '삼성실적': 'sum',
                                '기타실적': 'sum',
                                '코칭필요': 'sum'
                            }).reset_index()
                            
                            team_agg['지급률'] = (team_agg['총지급액'] / team_agg['총실적'] * 100).fillna(0)
                            team_agg = team_agg.sort_values('총실적', ascending=False)
                            
                            if not team_agg.empty:
                                # 정렬 컨트롤
                                st.markdown('<div style="margin-top: 1rem; margin-bottom: 0.5rem; font-weight: 600; color: #475569; font-size: 0.9rem;">📊 지점 정렬 옵션</div>', unsafe_allow_html=True)
                                sort_team_by = st.selectbox("정렬 기준", ["실적 높은 순", "인센티브 높은 순", "지급률 높은 순", "지점명순"], key="team_list_sort_key", label_visibility="collapsed")
                                
                                # 데이터 정렬
                                sorted_team_summary = team_agg.copy()
                                if sort_team_by == "실적 높은 순": sorted_team_summary = sorted_team_summary.sort_values('총실적', ascending=False)
                                elif sort_team_by == "인센티브 높은 순": sorted_team_summary = sorted_team_summary.sort_values('총지급액', ascending=False)
                                elif sort_team_by == "지급률 높은 순": sorted_team_summary = sorted_team_summary.sort_values('지급률', ascending=False)
                                elif sort_team_by == "지점명순": sorted_team_summary = sorted_team_summary.sort_values('소속', ascending=True)

                                # [Team Table] 헤더
                                st.markdown("""
                                <div style="display:flex; align-items:center; padding:0.8rem 1rem; background:#F9FAFB; border-top:1px solid #E5E7EB; border-bottom:1px solid #E5E7EB; font-weight:600; color:#4B5563; font-size:0.9rem;">
                                    <div style="flex:1.2; text-align:left;">지점</div>
                                    <div style="flex:1.2; text-align:right;">총 예상 인센티브</div>
                                    <div style="flex:0.8; text-align:right;">지급률</div>
                                    <div style="flex:1.2; text-align:right;">전체 실적</div>
                                    <div style="flex:1; text-align:right; color:#2563EB;">🔵 삼성</div>
                                    <div style="flex:1; text-align:right; color:#D97706;">🟡 KB</div>
                                    <div style="flex:1; text-align:right; color:#059669;">🟢 기타</div>
                                    <div style="flex:0.8; text-align:center;">상세</div>
                                </div>
                                """, unsafe_allow_html=True)
                                
                                # 팀별 행 렌더링
                                for t_idx, t_row in sorted_team_summary.iterrows():
                                    with st.container():
                                        cols = st.columns([1.2, 1.2, 0.8, 1.2, 1, 1, 1, 0.8])
                                        with cols[0]:
                                            st.markdown(f"<div style='font-weight:600; color:#1F2937; padding-top:10px;'>{t_row['소속']} <span style='font-size:0.8em; color:#9CA3AF; font-weight:400;'>({t_row['설계사']}명)</span></div>", unsafe_allow_html=True)
                                        with cols[1]:
                                            st.markdown(f"<div style='text-align:right; font-weight:700; color:#2563EB; padding-top:10px;'>{t_row['총지급액']:,.0f}</div>", unsafe_allow_html=True)
                                        with cols[2]:
                                            st.markdown(f"<div style='text-align:right; color:#4B5563; padding-top:10px;'>{t_row['지급률']:.1f}%</div>", unsafe_allow_html=True)
                                        with cols[3]:
                                            st.markdown(f"<div style='text-align:right; font-weight:600; color:#111827; padding-top:10px;'>{t_row['총실적']:,.0f}</div>", unsafe_allow_html=True)
                                        with cols[4]:
                                            st.markdown(f"<div style='text-align:right; color:#6B7280; font-size:0.9rem; padding-top:10px;'>{t_row['삼성실적']:,.0f}</div>", unsafe_allow_html=True)
                                        with cols[5]:
                                            st.markdown(f"<div style='text-align:right; color:#6B7280; font-size:0.9rem; padding-top:10px;'>{t_row['KB실적']:,.0f}</div>", unsafe_allow_html=True)
                                        with cols[6]:
                                            st.markdown(f"<div style='text-align:right; color:#6B7280; font-size:0.9rem; padding-top:10px;'>{t_row['기타실적']:,.0f}</div>", unsafe_allow_html=True)
                                        with cols[7]:
                                            if st.button("상세", key=f"team_list_btn_{t_idx}", use_container_width=True):
                                                st.session_state.selected_team = t_row['소속']
                                                st.rerun()
                                        st.markdown("<div style='border-bottom:1px solid #F3F4F6; margin-bottom:5px;'></div>", unsafe_allow_html=True)

                            st.markdown("<br><br>", unsafe_allow_html=True)

                            # --- B) 👥 설계사별 현황 섹션 ---
                            st.markdown('<div id="agent-section"></div>', unsafe_allow_html=True)
                            st.markdown(f"### 👥 설계사별 현황 ({len(agg_df)}명)", unsafe_allow_html=True)
                            
                            # 검색 및 필터 UI
                            st.markdown('<div style="margin-top: 1rem; margin-bottom: 0.5rem; font-weight: 600; color: #475569; font-size: 0.9rem;">🔍 설계사 검색 및 필터</div>', unsafe_allow_html=True)
                            f_col1, f_col2, f_col3 = st.columns([2, 1.5, 1.5])
                            with f_col1:
                                search_q = st.text_input("설계사 또는 지점 검색", placeholder="이름 또는 지점명 입력...", key="agent_search_box", label_visibility="collapsed")
                            with f_col2:
                                unique_branches = sorted(agg_df['소속'].unique()) if '소속' in agg_df.columns else []
                                branch_f = st.multiselect("지점 필터", options=unique_branches, placeholder="지점 선택", key="branch_filter_box", label_visibility="collapsed")
                            with f_col3:
                                coaching_filter_opt = st.selectbox("성과 관리 필터", ["전체 설계사 보기", "코칭 대상자만 보기"], index=0, key="coaching_filter_select", label_visibility="collapsed")
                            
                            # 데이터 필터링 가공
                            display_df = agg_df.copy()
                            if branch_f:
                                display_df = display_df[display_df['소속'].isin(branch_f)]
                            if search_q:
                                q = search_q.strip().lower()
                                display_df = display_df[
                                    (display_df['설계사'].str.lower().str.contains(q, na=False)) | 
                                    (display_df['소속'].str.lower().str.contains(q, na=False))
                                ]
                            if coaching_filter_opt == "코칭 대상자만 보기":
                                display_df = display_df[display_df['코칭필요'] == True]
                            
                            display_df = display_df.sort_values('총실적', ascending=False)

                            if not display_df.empty:
                                # 정렬 컨트롤
                                st.markdown('<div style="margin-top: 1rem; margin-bottom: 0.5rem; font-weight: 600; color: #475569; font-size: 0.9rem;">📊 설계사 정렬 옵션</div>', unsafe_allow_html=True)
                                sort_agent_by = st.selectbox("정렬 기준", ["실적 높은 순", "인센티브 높은 순", "지급률 높은 순", "이름순"], key="agent_list_sort_key", label_visibility="collapsed")
                                
                                # 데이터 정렬
                                sorted_agent_df = display_df.copy()
                                if sort_agent_by == "실적 높은 순": sorted_agent_df = sorted_agent_df.sort_values('총실적', ascending=False)
                                elif sort_agent_by == "인센티브 높은 순": sorted_agent_df = sorted_agent_df.sort_values('총지급액', ascending=False)
                                elif sort_agent_by == "지급률 높은 순": sorted_agent_df = sorted_agent_df.sort_values('지급률', ascending=False)
                                elif sort_agent_by == "이름순": sorted_agent_df = sorted_agent_df.sort_values('설계사', ascending=True)

                                # [Agent Table] 헤더
                                st.markdown("""
                                <div style="display:flex; align-items:center; padding:0.8rem 1rem; background:#F9FAFB; border-top:1px solid #E5E7EB; border-bottom:1px solid #E5E7EB; font-weight:600; color:#4B5563; font-size:0.9rem;">
                                    <div style="flex:1.2; text-align:left;">설계사 / 지점</div>
                                    <div style="flex:1.2; text-align:right;">총 예상 인센티브</div>
                                    <div style="flex:0.8; text-align:right;">지급률</div>
                                    <div style="flex:1.2; text-align:right;">전체 실적</div>
                                    <div style="flex:1; text-align:right; color:#2563EB;">🔵 삼성</div>
                                    <div style="flex:1; text-align:right; color:#D97706;">🟡 KB</div>
                                    <div style="flex:1; text-align:right; color:#059669;">🟢 기타</div>
                                    <div style="flex:0.8; text-align:center;">상세</div>
                                </div>
                                """, unsafe_allow_html=True)

                                # 설계사별 행 렌더링
                                for idx, row in sorted_agent_df.iterrows():
                                    with st.container():
                                        cols = st.columns([1.2, 1.2, 0.8, 1.2, 1, 1, 1, 0.8])
                                        
                                        # [설계사 / 지점]
                                        with cols[0]:
                                            st.markdown(f"""
                                            <div style='padding-top:10px;'>
                                                <span style='font-weight:600; color:#1F2937;'>{row['설계사']}</span>
                                                <span style='font-size:0.8em; color:#6B7280; display:block;'>{row['소속']}</span>
                                            </div>
                                            """, unsafe_allow_html=True)
                                            
                                        # 수수료/인센티브
                                        with cols[1]:
                                            st.markdown(f"<div style='text-align:right; font-weight:700; color:#4F46E5; padding-top:10px;'>{row['총지급액']:,.0f}</div>", unsafe_allow_html=True)
                                        with cols[2]:
                                            st.markdown(f"<div style='text-align:right; color:#4B5563; padding-top:10px;'>{row['지급률']:.1f}%</div>", unsafe_allow_html=True)
                                        with cols[3]:
                                            st.markdown(f"<div style='text-align:right; font-weight:600; color:#111827; padding-top:10px;'>{row['총실적']:,.0f}</div>", unsafe_allow_html=True)
                                        with cols[4]:
                                            st.markdown(f"<div style='text-align:right; color:#6B7280; font-size:0.9rem; padding-top:10px;'>{row['삼성실적']:,.0f}</div>", unsafe_allow_html=True)
                                        with cols[5]:
                                            st.markdown(f"<div style='text-align:right; color:#6B7280; font-size:0.9rem; padding-top:10px;'>{row['KB실적']:,.0f}</div>", unsafe_allow_html=True)
                                        with cols[6]:
                                            st.markdown(f"<div style='text-align:right; color:#6B7280; font-size:0.9rem; padding-top:10px;'>{row['기타실적']:,.0f}</div>", unsafe_allow_html=True)
                                        with cols[7]:
                                            if st.button("조회", key=f"agent_list_btn_{idx}", use_container_width=True):
                                                st.session_state.selected_agent = row['설계사']
                                                st.rerun()
                                        
                                        st.markdown("<div style='border-bottom:1px solid #F3F4F6; margin-bottom:5px;'></div>", unsafe_allow_html=True)
                        
                        # 기존 데이터프레임 코드 제거됨
                        

                    else:
                        st.warning("집계된 실적 데이터가 없습니다.")
                
                # render_analytics_section(processed_df, display_period_start=calc_params['period_start'], display_period_end=calc_params['period_end'])
                pass
                
            except Exception as e:
                st.error(f"❌ 계산 중 오류 발생: {str(e)}")
                st.exception(e)
    
    elif st.session_state.results_df is not None:
        results = st.session_state.results_df
        summary = get_award_summary(results)
        render_metrics(summary)
        st.markdown("---")
        render_results_table(results)
    
    else:
        st.info("👈 사이드바에서 설정을 완료하고 **[인센티브 계산]** 버튼을 클릭하세요.")


if __name__ == "__main__":
    main()
