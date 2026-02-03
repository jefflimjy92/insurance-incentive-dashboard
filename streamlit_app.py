"""
보험 설계사 인센티브 대시보드
Streamlit 메인 애플리케이션 (공개 스프레드시트 버전)
"""

import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
import textwrap
import os
import pickle
from datetime import datetime, timedelta
import streamlit.components.v1 as components

# 로컬 모듈 import
from data_loader import (
    load_contracts_from_url, load_rules_from_url,
    load_contracts_from_csv, load_rules_from_csv,
    validate_contracts, validate_rules, preprocess_contracts,
    get_unique_agents, get_unique_companies, get_period_dates,
    filter_by_period, load_consecutive_rules
)
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
    page_title="더바다 실적관리",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# [UX Improvement] Scroll to top on initial load (Refresh/F5)
# This logic ensures the page starts at the top when reloaded, but maintains scroll position on interactive reruns.
# [UX Improvement] Scroll to top logic
# 1. On initial load (Refresh/F5)
# 2. When explicitly triggered by navigation actions (trigger_scroll_top)
should_scroll = False
if 'init_scroll_done' not in st.session_state:
    st.session_state['init_scroll_done'] = True
    should_scroll = True

if st.session_state.get('trigger_scroll_top', False):
    st.session_state['trigger_scroll_top'] = False
    should_scroll = True

if should_scroll:
    components.html(
        """
        <script>
            // 1. Remove hash to prevent anchor jumping
            if (window.parent.location.hash) {
                window.parent.history.replaceState(null, null, window.parent.location.pathname + window.parent.location.search);
            }

            // 2. Persistent scroll to top (repeatedly force for 300ms to handle dynamic content loading)
            function forceScrollTop() {
                var doc = window.parent.document;
                
                // Window
                window.parent.scrollTo(0, 0);
                
                // Streamlit containers
                var containers = doc.querySelectorAll('[data-testid="stAppViewContainer"], .main, .block-container');
                containers.forEach(function(c) { 
                    c.scrollTo(0, 0); 
                    c.scrollTop = 0;
                });
            }

            // Execute immediately
            forceScrollTop();

            // Repeat for a short duration to override layout shifts
            var intervalId = setInterval(forceScrollTop, 10);
            setTimeout(function() { clearInterval(intervalId); }, 300);
        </script>
        """,
        height=0
    )

# 커스텀 CSS (Figma 디자인 기반 - 고대비 네이비 & 라이트 그레이)
st.markdown("""
<style>
    /* 폰트 및 기본 배경 */
    @import url('https://fonts.googleapis.com/css2?family=Pretendard+Variable:wght@400;500;600;700&display=swap');
    
    html, body, [data-testid="stAppViewContainer"] {
        font-family: 'Pretendard Variable', sans-serif;
        background-color: #F8F9FC;
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

    /* 메인 앱 컨테이너 여백 최적화 */
    .block-container {
        padding-top: 0px !important;
        padding-bottom: 2rem !important;
        max-width: 1250px !important;
        margin-top: 0px !important;
    }

    [data-testid="stAppViewContainer"] {
        padding-top: 0px !important;
    }
    
    [data-testid="stMain"] {
        margin-top: 0px !important;
        padding-top: 0px !important;
    }

    div[data-testid="stVerticalBlock"] > div:has(div.header-anchor) {
        position: sticky;
        top: 0px;
        z-index: 1000;
        background-color: #F8F9FC;
        padding-top: 0px !important;
        padding-bottom: 0.75rem;
        border-bottom: 1px solid #E2E8F0 !important;
        margin-top: 0px !important;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.02) !important;
    }

    /* 헤더 컨트롤 요소 크기 축소 */
    div[data-testid="stVerticalBlock"] > div:has(div.header-anchor) [data-testid="stSelectbox"] > div[data-baseweb="select"] {
        height: 30px !important;
        min-height: 30px !important;
    }
    div[data-testid="stVerticalBlock"] > div:has(div.header-anchor) [data-testid="stSelectbox"] [data-baseweb="select"] * {
        font-size: 0.8rem !important;
    }
    div[data-testid="stVerticalBlock"] > div:has(div.header-anchor) button[kind="secondary"], 
    div[data-testid="stVerticalBlock"] > div:has(div.header-anchor) button[kind="primary"] {
        height: 30px !important;
        min-height: 30px !important;
        padding: 0 10px !important;
        font-size: 0.9rem !important;
        line-height: 30px !important;
        padding-bottom: 2px !important;
    }
    div[data-testid="stVerticalBlock"] > div:has(div.header-anchor) .stMarkdown div p {
        font-size: 0.8rem !important;
    }
    
    .header-anchor {
        display: none;
    }
    
    /* 스크롤 시 앵커 위치 보정 - 헤더 크기에 맞게 재조정 */
    [id^="stats-section"], [id^="charts-section"], [id^="agents-section"] {
        scroll-margin-top: 10rem;
    }

    header[data-testid="stHeader"], [data-testid="stDecoration"] {
        display: none !important;
        visibility: hidden !important;
        height: 0 !important;
        width: 0 !important;
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
    
    /* [NEW] 강제 통일 네비게이션 버튼 스타일 */
    .nav-btn-fixed {
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        height: 28px !important;
        min-height: 28px !important;
        max-height: 28px !important;
        padding: 0 10px !important;
        font-size: 13px !important;
        font-weight: 600 !important;
        background-color: #F1F5F9 !important;
        color: #475569 !important;
        border-radius: 6px !important;
        text-decoration: none !important;
        white-space: nowrap !important;
        border: 1px solid transparent !important;
        line-height: normal !important; 
        box-sizing: border-box !important;
    }
    .nav-btn-fixed:hover {
        background-color: #E2E8F0 !important;
        color: #1E293B !important;
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
    /* 화이트 카드 컨테이너 */
    .white-card {
        background: white;
        padding: 1.25rem;
        border-radius: 12px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
        border: 1px solid #E5E7EB;
        margin-bottom: 1rem;
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
        grid-template-columns: 40px 2fr 0.8fr 1.2fr 1fr 1.5fr 1fr;
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
        grid-template-columns: 40px 2fr 0.8fr 1.2fr 1fr 1.5fr 1fr;
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
    if 'active_menu' not in st.session_state:
        st.session_state.active_menu = "대시보드"

CACHE_DIR = ".cache"
CACHE_CONTRACTS = os.path.join(CACHE_DIR, "contracts.pkl")
CACHE_RULES = os.path.join(CACHE_DIR, "rules.pkl")

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
    
def render_main_controls():
    """상단 조회 컨트롤 및 책갈피 (고정 헤더 영역)"""
    current_agent = st.session_state.get('selected_agent')
    
    # --- 고정 헤더 영역 시작 ---
    with st.container():
        st.markdown('<div class="header-anchor"></div>', unsafe_allow_html=True)
        
        # 1. 상단 컨트롤 행 (타이틀 + 네비 + 컨트롤)
        # 타이틀을 좌측으로 최대한 당기고, 네비게이션을 그 바로 옆에 서브메뉴처럼 밀착
        # 1. 상단 컨트롤 행 (타이틀 + 네비 + 컨트롤)
        # 타이틀을 좌측으로 최대한 당기고, 네비게이션을 그 바로 옆에 서브메뉴처럼 밀착
        # [Adjusted Widths] Year column increased (0.8 -> 1.1) to prevent "20..." truncation
        col_title, col_nav, col_year, col_month, col_set = st.columns([1.8, 4.4, 1.1, 0.9, 0.8], gap="small")
        
        with col_title:
            current_agent = st.session_state.get('selected_agent')
            selected_branch = st.session_state.get('selected_branch_filter')
            
            if current_agent or selected_branch:
                c1, c2 = st.columns([0.15, 0.85]) 
                with c1:
                    if st.button("‹", key="body_back_btn"):
                        st.session_state.selected_agent = None
                        st.session_state.selected_branch_filter = None
                        st.rerun()
                with c2:
                    if current_agent:
                        st.markdown(f'<div style="display:flex; align-items:center; height: 32px;"><span style="font-size:1.3rem; font-weight:700; color:#1E293B; white-space:nowrap;">{current_agent}님 명세</span></div>', unsafe_allow_html=True)
                    else:
                        st.markdown(f'<div style="display:flex; align-items:center; height: 32px;"><span style="font-size:1.3rem; font-weight:700; color:#1E293B; white-space:nowrap;">🏢 {selected_branch} 현황</span></div>', unsafe_allow_html=True)
            else:
                st.markdown('<div style="display:flex; align-items:center; height: 32px;"><h1 style="margin:0; font-size:1.5rem; white-space: nowrap; color: #1E293B;">🎯 더바다 실적관리</h1></div>', unsafe_allow_html=True)

        with col_nav:
            # Common style for all navigation buttons to ensure absolute consistency
            # Using the gray (inactive) style for ALL buttons to create a uniform look
            nav_btn_style = "display: inline-flex; align-items: center; justify-content: center; text-decoration: none; padding: 0 0.7rem; border-radius: 6px; font-size: 0.75rem; font-weight: 600; white-space: nowrap; height: 26px; background: #F1F5F9; color: #475569;"
            
            # 설계사 상세나 지점 상세일 때는 '팀별' 메뉴 숨기기
            is_detail_view = current_agent is not None or selected_branch is not None
            teams_link = f'<a href="#teams-section" class="nav-btn-fixed">🏢 팀별</a>' if not is_detail_view else ""
            
            awards_label = "📋 시상" if current_agent else "👥 설계사"
            awards_href = "#awards-section" if current_agent else "#agents-section"
            
            # Create single-line HTML to prevent Markdown parser from adding <p> tags
            nav_html = f'<div style="display: flex; gap: 0.4rem; align-items: center; height: 32px; overflow-x: auto; scrollbar-width: none; margin-top: 4px;">'
            nav_html += f'<a href="#stats-section" class="nav-btn-fixed">📊 실적</a>'
            nav_html += f'<a href="#charts-section" class="nav-btn-fixed">📈 추이</a>'
            if teams_link:
                nav_html += teams_link
            nav_html += f'<a href="{awards_href}" class="nav-btn-fixed">{awards_label}</a>'
            nav_html += '</div>'
            
            st.markdown(nav_html, unsafe_allow_html=True)

        # [Dynamic Date Logic]
        # Determine available years/months from loaded data if possible
        c_df = st.session_state.get('contracts_df')
        valid_years = [2024, 2025, 2026]
        valid_months_map = {} # year -> list of months
        
        if c_df is not None and not c_df.empty and '접수일' in c_df.columns:
            try:
                # Ensure datetime
                if not pd.api.types.is_datetime64_any_dtype(c_df['접수일']):
                     c_df['접수일'] = pd.to_datetime(c_df['접수일'], errors='coerce')
                
                # Extract years
                extracted_years = sorted(c_df['접수일'].dt.year.dropna().unique().astype(int).tolist())
                if extracted_years:
                    valid_years = extracted_years
                    
                    # Extract months for each year
                    for y in valid_years:
                        months = sorted(c_df[c_df['접수일'].dt.year == y]['접수일'].dt.month.dropna().unique().astype(int).tolist())
                        if months:
                            valid_months_map[y] = months
            except Exception as e:
                pass # Use defaults on error

        with col_year:
            if 'shadow_year' not in st.session_state:
                st.session_state.shadow_year = 2026
            
            # Fallback if shadow_year is not in valid_years (e.g. data changed)
            if st.session_state.shadow_year not in valid_years:
                st.session_state.shadow_year = valid_years[-1] if valid_years else 2026

            yr_idx = valid_years.index(st.session_state.shadow_year)
            target_year = st.selectbox("년도", valid_years, index=yr_idx, key="year_sel_body", label_visibility="collapsed")
            
            if target_year != st.session_state.shadow_year:
                st.session_state.shadow_year = target_year
                if 'cached_data' in st.session_state: del st.session_state['cached_data']
                st.rerun()
                
        with col_month:
            if 'shadow_month' not in st.session_state:
                 st.session_state.shadow_month = datetime.now().month
            
            # Determine available months for the selected year
            available_months = valid_months_map.get(st.session_state.shadow_year, list(range(1, 13)))
            
            # Ensure current shadow_month is valid
            if st.session_state.shadow_month not in available_months:
                 # Default to latest available month or first
                 st.session_state.shadow_month = available_months[-1] if available_months else 1

            if not available_months: # Fallback
                available_months = list(range(1, 13))

            m_idx = available_months.index(st.session_state.shadow_month) if st.session_state.shadow_month in available_months else 0
            
            target_month = st.selectbox("월", available_months, index=m_idx, key="month_sel_body", 
                                        format_func=lambda x: f"{x}월", label_visibility="collapsed")
            if target_month != st.session_state.shadow_month:
                st.session_state.shadow_month = target_month
                if 'cached_data' in st.session_state: del st.session_state['cached_data']
                st.rerun()

        with col_set:
            if st.button("⚙️ 설정", key="btn_open_settings_header", use_container_width=True):
                data_settings_modal()
            try:
                if os.path.exists(CACHE_CONTRACTS):
                    mod_time = os.path.getmtime(CACHE_CONTRACTS)
                    last_update = datetime.fromtimestamp(mod_time).strftime('%y.%m.%d %H:%M')
                    st.markdown(f'<div style="font-size: 0.6rem; color: #94A3B8; text-align: center; margin-top: -14px; font-family: monospace;">{last_update}</div>', unsafe_allow_html=True)
            except: pass

    # 기본값 계산 및 반환
    target_month_date = datetime(target_year, target_month, 1)
    base_date = datetime.combine(target_month_date, datetime.min.time())
    period_start, period_end = get_period_dates("월간", base_date)
    return {
        'agent_name': current_agent, 'company': None,
        'period_start': period_start, 'period_end': period_end,
        'product_filter': ["인보험", "펫보험", "단체보험", "재물보험", "실손보험", "자동차보험", "본인계약", "기타"],
        'target_date': target_month_date, 'type_filter': []
    }


def render_metrics(summary: dict):
    """종합 현황 렌더링 (Figma 스타일)"""
    # st.header("📊 종합 현황") # 메인 헤더가 상단에 있으므로 중복 제거 가능
    
    payout_pct = 0
    if summary.get('총실적', 0) > 0:
        payout_pct = (summary['총지급예상금액'] / summary['총실적']) * 100

    col1, col2, col3, col4 = st.columns(4) # Figma에 맞춰 4개로 확장 유동적
    
    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <p class="label">💰 총 지급예상금액</p>
            <p class="value">{summary['총지급예상금액']:,.0f}원 <span style="font-size: 0.8rem; font-weight: 500; color: #10B981; margin-left: 4px;">({payout_pct:.1f}%)</span></p>
            <p class="progress-info">▲ 실적 대비 지급률</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div class="metric-card">
            <p class="label">🏆 달성 시상 수</p>
            <p class="value">{summary['시상개수']}개</p>
            <p class="progress-info">{summary['선택된시상개수']}개 선택됨</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
        <div class="metric-card">
            <p class="label">📈 평균 달성률</p>
            <p class="value">{summary['평균달성률']:.1f}%</p>
            <p class="progress-info">▲ 전월 대비 4.2%</p>
        </div>
        """, unsafe_allow_html=True)
        
    with col4:
        st.markdown(f"""
        <div class="metric-card">
            <p class="label">📝 이번 달 계약</p>
            <p class="value">{summary.get('당월계약건수', 0)}건</p>
            <p class="progress-info">최종 확정 기준</p>
        </div>
        """, unsafe_allow_html=True)


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
    
    # Product Type Badge
    product_type = group.get('대상분류', '')
    product_badge = ""
    if product_type and product_type != '전체':
        product_badge = f"""
        <span style="font-size: 0.7rem; color: #6366F1; font-weight: 500; margin-left: 4px; background: #EEF2FF; padding: 1px 4px; border-radius: 3px;">
            {product_type}
        </span>
        """
    
    html = f"""
    <!-- Status Icon -->
    <div style="display: flex; justify-content: center;">
        {icon_html}
    </div>
    
    <!-- Award Name & Company -->
    <div style="padding-right: 1rem;">
        <div style="font-weight: 700; font-size: 0.9rem; color: #111827; margin-bottom: 2px;">
            {group['name']}
            {product_badge}
            {imminent_badge}
        </div>
        <div style="font-size: 0.75rem; color: #9CA3AF;">{group['company']}</div>
    </div>
    
    <!-- Type -->
    <div>
        <span style="background: {type_style['bg']}; color: {type_style['color']}; padding: 2px 8px; border-radius: 4px; font-size: 0.7rem; font-weight: 600;">
            {group['type']}
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
            achievement = row.get('달성률', 0)
            
            is_over = perf > target and target > 0
            is_achieved = payout > 0 or achievement >= 100
            
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
                    <td style="padding: 0.6rem 0.5rem; text-align: right; font-weight: 600; color: #111827;">{payout:,.0f}</td>
                    <td style="padding: 0.6rem 0.5rem; text-align: center;">{achievement:.0f}%</td>
                    <td style="padding: 0.6rem 0.5rem; text-align: center;">{status_badge}</td>
                </tr>
            """)
        
        html_parts.append("</tbody></table></div>")
    
    # --- 추가: 인정 계약 (근거 데이터) 섹션 ---
    # rows_df에서 contracts_info 추출 (모든 행의 계약을 합쳐서 보여줌)
    all_contracts = []
    if 'contracts_info' in rows_df.columns:
        seen_contracts = set()
        for idx, row in rows_df.iterrows():
            c_list = row.get('contracts_info', [])
            if isinstance(c_list, list):
                for c in c_list:
                    # 중복 제거를 위한 키 생성 (접수일, 상품명, 보험료 조합)
                    c_key = f"{c.get('접수일')}_{c.get('상품명')}_{c.get('보험료')}"
                    if c_key not in seen_contracts:
                        all_contracts.append(c)
                        seen_contracts.add(c_key)
    
    if all_contracts:
        html_parts.append(f"""
            <div style="font-size: 0.8rem; font-weight: 600; color: #374151; margin-top: 1.5rem; margin-bottom: 0.5rem; border-top: 1px solid #E5E7EB; padding-top: 1rem;">
                📄 인정 계약 (근거 데이터)
            </div>
            <table style="width: 100%; border-collapse: collapse; font-size: 0.75rem; color: #4B5563;">
                <thead>
                    <tr style="text-align: left; border-bottom: 1px solid #F3F4F6;">
                        <th style="padding: 0.5rem;">접수일</th>
                        <th style="padding: 0.5rem;">계약자</th>
                        <th style="padding: 0.5rem;">상품명</th>
                        <th style="padding: 0.5rem;">분류</th>
                        <th style="padding: 0.5rem; text-align: right;">보험료</th>
                    </tr>
                </thead>
                <tbody>
        """)
        
        # 최신순 정렬
        all_contracts.sort(key=lambda x: x.get('접수일', ''), reverse=True)
        
        for c in all_contracts[:50]: # 너무 많으면 상위 50개만
            date_str = pd.to_datetime(c.get('접수일')).strftime('%Y-%m-%d') if c.get('접수일') else '-'
            html_parts.append(f"""
                <tr style="border-bottom: 1px solid #F9FAFB;">
                    <td style="padding: 0.4rem 0.5rem;">{date_str}</td>
                    <td style="padding: 0.4rem 0.5rem; font-weight: 500;">{c.get('계약자', '-')}</td>
                    <td style="padding: 0.4rem 0.5rem;">{c.get('상품명', '-')}</td>
                    <td style="padding: 0.4rem 0.5rem; color: #6B7280;">{c.get('분류', '-')}</td>
                    <td style="padding: 0.4rem 0.5rem; text-align: right;">{c.get('보험료', 0):,.0f}</td>
                </tr>
            """)
        
        if len(all_contracts) > 50:
             html_parts.append(f'<tr><td colspan="5" style="text-align: center; padding: 0.5rem; color: #9CA3AF;">... 외 {len(all_contracts)-50}건 더 있음</td></tr>')
             
        html_parts.append("</tbody></table>")
    
    return clean_html("".join(html_parts))


def render_results_table(results_df: pd.DataFrame):
    """전체 시상 테이블 렌더링 (Figma 디자인 정확히 따라하기)"""
    
    # 헤더 및 범례
    st.markdown(textwrap.dedent("""
        <div id="awards-section" style="margin-bottom: 0.5rem; display: flex; justify-content: space-between; align-items: flex-end;">
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
        sort_by = st.selectbox("🔃 정렬", ["시작일순", "지급금액순", "달성률순"], label_visibility="collapsed")
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
        elif '기준보상' in group_df.columns:
             # [Fix] 기준보상(Potential Reward)을 우선 확인하여 미달성 시에도 최고 금액 표시
             max_possible = group_df['기준보상'].max()
        elif '보상금액' in group_df.columns:
            max_possible = group_df['보상금액'].max()
        elif '지급금액' in group_df.columns:
            max_possible = group_df['지급금액'].max()

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
            '대상분류': group_df['대상분류'].iloc[0] if '대상분류' in group_df.columns else '',
            'original_index': group_df.index.min() # 원본 데이터 순서 추적용
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
        
        if group['payout'] > 0:
            payout_display = f"<span style='color: #10B981; font-weight: 700;'>{group['payout']:,.0f}원</span>"
        else:
            payout_display = f"<span style='color: #6B7280;'>0원</span>"
            
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
        
    full_table_html = f'<div class="award-table"><div class="award-table-header"><div style="text-align: center;">상태</div><div>시상명</div><div>유형</div><div>기간</div><div style="text-align: right;">목표실적</div><div style="text-align: center;">실적 / 달성률</div><div style="text-align: right;">지급금액</div></div>{"".join(table_rows_html)}</div>'
    
    st.write(full_table_html, unsafe_allow_html=True)

def render_footer_report(results_df: pd.DataFrame, contracts_df: pd.DataFrame, summary: dict, target_date: datetime):
    """하단 리포트 및 추천 섹션 (확장된 성과 최적화 가이드 포함)"""
    st.markdown('<div id="stats-section"></div>', unsafe_allow_html=True)
    
    # 🎯 성과 최적화 가이드 로직 (Figma 고정 디자인 버전)
    current_time = pd.Timestamp.now().normalize()
    
    # 80~100% 사이인 항목들 (중복 제거)
    potential_df = results_df[(results_df['달성률'] >= 80) & (results_df['달성률'] < 100)].copy() if not results_df.empty else pd.DataFrame()
    if not potential_df.empty:
        potential_df = potential_df.drop_duplicates(subset=['시상명'])
        potential_df['end_date_dt'] = pd.to_datetime(potential_df['종료일'])
        ongoing_imminent = potential_df[potential_df['end_date_dt'] >= current_time]
        past_missed = potential_df[potential_df['end_date_dt'] < current_time]
    else:
        ongoing_imminent = pd.DataFrame()
        past_missed = pd.DataFrame()
    
    # [신규] 교차 최적화 분석
    try:
        from data_loader import analyze_cross_company_optimization
        optimization_recos = analyze_cross_company_optimization(results_df)
    except:
        optimization_recos = []

    active_items = []
    history_items = []
    switch_items = []

    def get_v(row, keys, default=0):
        for k in keys:
            if k in row:
                val = row[k]
                if pd.notna(val): return val
        return default

    # 0. 전략적 전환 (SWITCH)
    for reco in optimization_recos:
        sat = reco['saturated_item']
        opp = reco['opportunity_item']
        switch_items.append({'sat_info': sat, 'opp_info': opp})

    # 1. 액티브 가이드 (IMMINENT)
    for _, r in ongoing_imminent.head(4).iterrows():
        m_target = get_v(r, ['목표실적', 'target'])
        m_perf = get_v(r, ['실적', 'perf'])
        missing_amt = max(0, m_target - m_perf)
        award_name = r.get('시상명', '')
        company = get_v(r, ['회사', '원수사', '보험사'], '')
        solidified = results_df[(results_df['시상명'] == award_name) & (results_df['회사'] == company)]['최종지급금액'].max() if not results_df.empty else 0
        diff_payout = max(0, get_v(r, ['기준보상', '보상금액', '지급금액']) - (solidified if pd.notna(solidified) else 0))
        
        active_items.append({
            'title': award_name, 'company': company,
            'missing': missing_amt, 'bonus': diff_payout
        })

    # 2. 아쉬운 결과 (HISTORY)
    for _, r in past_missed.head(4).iterrows():
        m_target = get_v(r, ['목표실적', 'target'])
        m_perf = get_v(r, ['실적', 'perf'])
        missing_amt = max(0, m_target - m_perf)
        award_name = r.get('시상명', '')
        company = get_v(r, ['회사', '원수사', '보험사'], '')
        solidified = results_df[(results_df['시상명'] == award_name) & (results_df['회사'] == company)]['최종지급금액'].max() if not results_df.empty else 0
        loss_amt = max(0, get_v(r, ['기준보상', '보상금액', '지급금액']) - (solidified if pd.notna(solidified) else 0))
        
        history_items.append({
            'title': award_name, 'company': company,
            'missing': missing_amt, 'loss': loss_amt
        })

    # UI 렌더링 시작 (내용이 있을 때만 렌더링)
    if active_items or history_items or switch_items:
        # Title
        st.markdown(f'<p style="font-weight: 700; color: #1E293B; margin-bottom: 1rem; font-size: 1.1rem; letter-spacing: -0.02em;">🎯 성과 최적화 가이드</p>', unsafe_allow_html=True)
        
        # 0. SWITCH Items
        for item in switch_items:
            sat, opp = item['sat_info'], item['opp_info']
            s_target = sat.get('target', 0)
            s_excess = sat.get('surplus', 0)
            o_target = opp.get('target', 0)
            o_bonus = opp.get('marginal_gain', 0)
            s_award = sat.get('award_name', '')
            o_award = opp.get('award_name', '')
            
            # FROM Target Pct Calculation
            from_pct = min(100, int((s_target + s_excess) / s_target * 100)) if s_target > 0 else 100
            remaining_surplus = max(0, s_excess - o_target)

            html = f"""
            <div class="guide-card-switch" style="background: linear-gradient(to right, #F8FAFC, #EFF6FF); border: 1px solid #DBEAFE; border-radius: 12px; padding: 16px; margin-bottom: 16px;">
                <div style="margin-bottom: 12px;">
                    <span class="badge-switch" style="background: #DBEAFE; color: #1E40AF; padding: 4px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 600;">✨ 전략적 집중 이동</span>
                    <p style="margin-top: 8px; font-size: 0.9rem; color: #334155; line-height: 1.4;">
                        <b>{sat['company']}</b>에서 초과 달성 중인 실적을<br/>
                        <b>{opp['company']}</b>로 돌렸을 때의 수익 분석입니다.
                    </p>
                </div>
                
                <div style="display: flex; align-items: stretch; gap: 8px; margin-bottom: 16px;">
                    <!-- FROM -->
                    <div style="flex: 1; background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 8px; padding: 12px;">
                        <div style="font-size: 0.75rem; color: #64748B; margin-bottom: 4px;">FROM (목표 {from_pct}% 달성)</div>
                        <div style="font-weight: 700; color: #1E293B; margin-bottom: 4px;">{sat['company']}</div>
                        <div style="font-size: 0.8rem; color: #475569;">
                            목표: {s_target:,.0f}<br/>
                            <span style="color: #059669; font-weight: 600;">초과: +{s_excess:,.0f}</span>
                        </div>
                        <div style="font-size: 0.7rem; color: #94A3B8; margin-top: 6px;">{s_award}</div>
                    </div>
                    
                    <!-- Arrow -->
                    <div style="display: flex; align-items: center; justify-content: center; color: #94A3B8; font-weight: 300; width: 20px;">→</div>
                    
                    <!-- TO -->
                    <div style="flex: 1; background: #FFFFFF; border: 1px solid #BFDBFE; border-radius: 8px; padding: 12px; box-shadow: 0 4px 6px -1px rgba(59, 130, 246, 0.1);">
                        <div style="font-size: 0.75rem; color: #3B82F6; font-weight: 600; margin-bottom: 4px;">TO (상위구간 점프 기회)</div>
                        <div style="font-weight: 700; color: #1E293B; margin-bottom: 4px;">{opp['company']}</div>
                        <div style="font-size: 0.8rem; color: #475569;">
                            도전 목표: {o_target:,.0f}<br/>
                            <span style="color: #2563EB; font-weight: 700;">총 추가 보상: +{o_bonus:,.0f}원</span>
                        </div>
                        <div style="font-size: 0.7rem; color: #94A3B8; margin-top: 6px;">{o_award}</div>
                    </div>
                </div>
                
                <!-- Simulation -->
                <div style="background: #F0F9FF; border-radius: 8px; padding: 12px; border: 1px solid #BAE6FD;">
                    <div style="font-size: 0.85rem; font-weight: 600; color: #0369A1; margin-bottom: 4px;">💡 시뮬레이션 결과:</div>
                    <div style="font-size: 0.8rem; color: #334155; line-height: 1.5;">
                        {sat['company']}의 초과 실적인 <b>{s_excess:,.0f}원</b>을 {opp['company']}에 전환 사용한다면,<br/>
                        {o_target:,.0f} 목표를 즉시 달성하여 <b>+{o_bonus:,.0f}원의 수익</b>을 추가로 확보할 수 있습니다.<br/>
                        <span style="color: #64748B; font-size: 0.75rem;">(심지어 {remaining_surplus:,.0f}원의 실적이 더 남습니다!)</span>
                    </div>
                </div>
            </div>
            """
            st.markdown(html, unsafe_allow_html=True)

        # 1. Active Items
        if active_items:
            st.markdown("<div style='font-size:0.85rem; color:#475569; font-weight:600; margin: 24px 0 8px 0;'>🔥 지금 바로 챙겨야 할 기회</div>", unsafe_allow_html=True)
            cols = st.columns(2)
            for i, item in enumerate(active_items):
                with cols[i % 2]:
                    html = f"""
                    <div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 12px; padding: 16px; margin-bottom: 12px; height: 100%;">
                        <div style="margin-bottom: 8px;"><span style="background: #FEF3C7; color: #D97706; padding: 2px 6px; border-radius: 4px; font-size: 0.7rem; font-weight: 600;">⚠️ 달성임박</span></div>
                        <div style="font-size: 0.9rem; font-weight: 700; color: #1E293B; margin-bottom: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{item['title']}</div>
                        <div style="font-size: 0.8rem; color: #64748B; margin-bottom: 8px;">{item['company']}</div>
                        <div style="font-size: 0.85rem; color: #334155;">
                            다음 단계까지 <br/>
                            <span style="color:#D97706; font-weight:600;">{item['missing']:,.0f}원</span> 
                            <span style="font-size:0.75rem; color:#059669;">(달성 시 +{item['bonus']:,.0f}원)</span>
                        </div>
                    </div>
                    """
                    st.markdown(html, unsafe_allow_html=True)

        # 2. History Items
        if history_items:
            st.markdown("<div style='font-size:0.85rem; color:#64748B; font-weight:600; margin: 24px 0 8px 0;'>📚 지난달 복기 (아까운 미달성)</div>", unsafe_allow_html=True)
            cols = st.columns(2)
            for i, item in enumerate(history_items):
                with cols[i % 2]:
                    html = f"""
                    <div style="background: #F8FAFC; border: 1px solid #F1F5F9; border-radius: 12px; padding: 16px; margin-bottom: 12px; height: 100%;">
                        <div style="margin-bottom: 8px;"><span style="background: #F1F5F9; color: #64748B; padding: 2px 6px; border-radius: 4px; font-size: 0.7rem; font-weight: 600;">😢 아쉬운 결과</span></div>
                        <div style="font-size: 0.9rem; font-weight: 700; color: #1E293B; margin-bottom: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{item['title']}</div>
                        <div style="font-size: 0.8rem; color: #94A3B8; margin-bottom: 8px;">{item['company']}</div>
                        <div style="font-size: 0.85rem; color: #475569;">
                            <span style="color:#EF4444; font-weight:600;">{item['missing']:,.0f}원</span> 부족해서<br/>
                            <span style="color:#EF4444; font-weight:700;">{item['loss']:,.0f}원</span>을 놓쳤습니다.
                        </div>
                    </div>
                    """
                    st.markdown(html, unsafe_allow_html=True)



def render_performance_graphs(contracts_df: pd.DataFrame, results_df: pd.DataFrame = None, display_period_start: datetime = None, display_period_end: datetime = None):
    """실적 분석 추이 (차트 및 통계 테이블)"""
    # 조회 기간이 명시된 경우 해당 기간으로 먼저 타이트하게 필터링
    if display_period_start and display_period_end:
        contracts_df = filter_by_period(contracts_df, display_period_start, display_period_end)
    
    # 헤더 및 컨트롤러
    st.markdown('<div id="charts-section"></div>', unsafe_allow_html=True)
    st.markdown('<h3 style="margin-top: 0.5rem; margin-bottom: 0.5rem; font-size: 1.2rem; font-weight: 700; color: #1E293B;">📈 분석 추이</h3>', unsafe_allow_html=True)
    
    chart_view = st.radio(
            "차트 보기",
            options=["누적 추이", "일별 실적", "모두 보기"],
            index=2, # 모두 보기 디폴트
            horizontal=True,
            key="chart_view_toggle",
            label_visibility="collapsed"
        )
    
    # 데이터 준비 및 필터링
    start_date = display_period_start
    end_date = display_period_end
    if (not start_date or not end_date) and results_df is not None and not results_df.empty:
        start_date = results_df['시작일'].min()
        end_date = results_df['종료일'].max()

    daily_df = get_daily_trend(contracts_df)
    if not daily_df.empty:
        daily_df['날짜'] = pd.to_datetime(daily_df['날짜'])
        filtered_daily = daily_df
        if start_date and end_date:
            filtered_daily = daily_df[(daily_df['날짜'] >= pd.to_datetime(start_date)) & 
                                     (daily_df['날짜'] <= pd.to_datetime(end_date))]
        
        if not filtered_daily.empty:
            # 그래프 영역 (비율 조정: 7:3)
            main_col, side_col = st.columns([7, 3])
            
            with main_col:
                # 한국어 요일 표현을 위한 Vega-Lite 표현식 수정
                axis_label_expr = "utcFormat(datum.value, '%m/%d') + ' ' + (['(일)', '(월)', '(화)', '(수)', '(목)', '(금)', '(토)'][day(datum.value)])"

                # 차트 정의
                cumulative_chart = alt.Chart(filtered_daily).mark_area(
                    line={'color': '#6366F1'},
                    color=alt.Gradient(
                        gradient='linear',
                        stops=[alt.GradientStop(color='#6366F1', offset=0),
                               alt.GradientStop(color='rgba(99, 102, 241, 0)', offset=1)],
                        x1=1, x2=1, y1=1, y2=0
                    )
                ).encode(
                    x=alt.X('날짜:T', title=None, axis=alt.Axis(labelExpr=axis_label_expr, grid=False)),
                    y=alt.Y('누적실적:Q', title="누적 보험료", axis=alt.Axis(grid=True, gridDash=[2,2])),
                    tooltip=[alt.Tooltip('날짜:T', title="날짜", format='%m/%d'), alt.Tooltip('누적실적:Q', format=',.0f', title="누적")]
                ).properties(height=280 if chart_view == "모두 보기" else 350)

                daily_chart = alt.Chart(filtered_daily).mark_bar(
                    color='#6366F1',
                    cornerRadiusTopLeft=4,
                    cornerRadiusTopRight=4
                ).encode(
                    x=alt.X('날짜:T', title=None, axis=alt.Axis(labelExpr=axis_label_expr, grid=False)),
                    y=alt.Y('일실적:Q', title="일일 보험료", axis=alt.Axis(grid=True, gridDash=[2,2])),
                    tooltip=[alt.Tooltip('날짜:T', title="날짜", format='%m/%d'), alt.Tooltip('일실적:Q', format=',.0f', title="일실적")]
                ).properties(height=280 if chart_view == "모두 보기" else 350)

                if chart_view == "누적 추이":
                    st.altair_chart(cumulative_chart, use_container_width=True)
                elif chart_view == "일별 실적":
                    st.altair_chart(daily_chart, use_container_width=True)
                else:
                    # 모두 보기: 수직 결합
                    st.altair_chart(cumulative_chart, use_container_width=True)
                    st.altair_chart(daily_chart, use_container_width=True)

            with side_col:
                # 1. 시각적 정돈을 위해 제목 제거 및 테이블 구성
                # 모든 날짜 채우기 (0값 포함)
                if start_date and end_date:
                    full_date_range = pd.date_range(start=start_date, end=end_date)
                    full_daily_df = pd.DataFrame({'날짜': full_date_range})
                    full_daily_df['날짜'] = pd.to_datetime(full_daily_df['날짜']).dt.date
                    filtered_daily['날짜'] = pd.to_datetime(filtered_daily['날짜']).dt.date
                    merged_df = pd.merge(full_daily_df, filtered_daily, on='날짜', how='left').fillna(0)
                    merged_df['누적실적'] = merged_df['누적실적'].replace(0, pd.NA).ffill().fillna(0)
                else:
                    merged_df = filtered_daily
                
                # 요일 정보 추가 (한글)
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

def render_performance_pivot(contracts_df: pd.DataFrame, summary: dict = None, display_period_start: datetime = None, display_period_end: datetime = None):
    """보험사별/상품별 실적 통계 (메트릭 카드 포함)"""
    if display_period_start and display_period_end:
        contracts_df = filter_by_period(contracts_df, display_period_start, display_period_end)

    st.markdown('<h3 style="margin-top: 1rem; margin-bottom: 0.5rem; font-size: 1.2rem; font-weight: 700; color: #1E293B;">📊 실적 통계</h3>', unsafe_allow_html=True)
    
    # 1. 상단 핵심 지표 영역 (통합 렌더링)
    if summary and not contracts_df.empty:
        payout_pct = (summary['총지급예상금액'] / summary['총실적'] * 100) if summary.get('총실적', 0) > 0 else 0
        
        # 회사별 실적 계산 (통합/개별 모두 대응)
        kb_perf = month_filtered_kb = contracts_df[contracts_df['회사'].str.contains('KB', case=False, na=False)]['보험료'].sum() if '회사' in contracts_df.columns else 0
        sam_perf = month_filtered_sam = contracts_df[contracts_df['회사'].str.contains('삼성', case=False, na=False)]['보험료'].sum() if '회사' in contracts_df.columns else 0
        
        if kb_perf == 0 and '원수사' in contracts_df.columns:
            kb_perf = contracts_df[contracts_df['원수사'].str.contains('KB', case=False, na=False)]['보험료'].sum()
            sam_perf = contracts_df[contracts_df['원수사'].str.contains('삼성', case=False, na=False)]['보험료'].sum()

        st.markdown(f"""
        <div style="display: grid; grid-template-columns: 1fr 1fr 1fr 1fr; gap: 1rem; margin-bottom: 1rem; margin-top: 0.5rem;">
            <div class="metric-card" style="background: transparent; border: none; box-shadow: none; padding-left: 0; min-height: 90px; display: flex; flex-direction: column; justify-content: flex-start; padding-top: 1rem; gap: 0px;">
                <p class="label">🏢 총 지급 인센티브</p>
                <p class="value" style="color: #4F46E5; font-size: 1.5rem;">{summary["총지급예상금액"]:,.0f}원</p>
                <p class="progress-info" style="color: #10B981; font-weight: 500;">▲ 전체 실적 대비 {payout_pct:.1f}% 지출</p>
            </div>
            <div class="metric-card" style="background: transparent; border: none; box-shadow: none; padding-left: 0; min-height: 90px; display: flex; flex-direction: column; justify-content: flex-start; padding-top: 1rem; gap: 0px;">
                <p class="label">📊 전체 실적 합계</p>
                <p class="value" style="font-size: 1.5rem;">{summary["총실적"]:,.0f}원</p>
            </div>
            <div class="metric-card" style="background: transparent; border: none; box-shadow: none; padding-left: 0; min-height: 90px; display: flex; flex-direction: column; justify-content: flex-start; padding-top: 1rem; gap: 0px;">
                <p class="label" style="color: #1E40AF;">🔵 삼성화재 실적</p>
                <p class="value" style="color: #1E40AF; font-size: 1.5rem;">{sam_perf:,.0f}원</p>
            </div>
            <div class="metric-card" style="background: transparent; border: none; box-shadow: none; padding-left: 0; min-height: 90px; display: flex; flex-direction: column; justify-content: flex-start; padding-top: 1rem; gap: 0px;">
                <p class="label" style="color: #B45309;">🟡 KB손해보험 실적</p>
                <p class="value" style="color: #B45309; font-size: 1.5rem;">{kb_perf:,.0f}원</p>
            </div>
        </div>
        """, unsafe_allow_html=True)

    if not contracts_df.empty:
        # 1. 원본 데이터 계산
        pivot_df = contracts_df.pivot_table(
            index='분류', 
            columns='회사', 
            values='보험료', 
            aggfunc='sum', 
            fill_value=0
        )
        
        # 2. 보험사별 합계 계산 및 정렬 (좌측 -> 우측 내림차순: 큰 금액부터 작은 금액)
        company_totals = pivot_df.sum().sort_values(ascending=False)
        sorted_companies = company_totals.index.tolist()
        pivot_df = pivot_df[sorted_companies]
        
        # 3. '합계' 열을 맨 앞에 추가
        pivot_df.insert(0, '합계', pivot_df.sum(axis=1))
        
        # 4. 행 정렬 (상단 -> 하단 내림차순: 큰 금액부터 작은 금액)
        # '합계' 열 기준으로 내림차순 정렬
        pivot_df = pivot_df.sort_values(by='합계', ascending=False)
        
        # 5. '합계' 행을 맨 위에 추가 (모든 행의 합계)
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

    st.markdown('<div style="margin-top: 1rem;"></div>', unsafe_allow_html=True)





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
    # 1. 상단 강제 이동 제어 (조회 버튼 클릭 시에만 작동)
    if st.session_state.get('trigger_scroll_top'):
        scroll_js = """<img src="x" onerror="(function(){
            var targets = [
                window.parent,
                window.parent.document.querySelector('.main'),
                window.parent.document.querySelector('[data-testid=\\'stAppViewContainer\\']'),
                window.parent.document.querySelector('.stApp')
            ];
            function s() { targets.forEach(function(t) { if(t) { if(t.scrollTo) t.scrollTo({top: 0, behavior: 'instant'}); t.scrollTop = 0; } }); }
            s(); setTimeout(s, 50); setTimeout(s, 150); setTimeout(s, 400);
        })();" style="display:none;">"""
        st.markdown(scroll_js, unsafe_allow_html=True)
        st.session_state.trigger_scroll_top = False
    
    from data_loader import filter_by_period
    init_session_state()
    
    # 1. 고정 헤더 렌더링 (컨트롤 및 책갈피만 포함)
    calc_params = render_main_controls()
    
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
                    # 단일 설계사: 상세 뷰 렌더링
                    
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
                            
                            # 필터 적용
                            if calc_params['product_filter']:
                                 # (이미 batch에서 반영되었을 수 있으나 결과 수준에서 한번 더 확인하거나 넘어감)
                                 pass
                                 
                            # 정렬 로직 수정: 룰 파일의 원본 순서 유지 (Index join)
                            # 중복 제거된 시상명-인덱스 맵 생성 (중요: 단순 merge시 데이터 뻥튀기 발생)
                            rule_order_map = st.session_state.rules_df[['시상명']].reset_index().drop_duplicates(subset=['시상명'])
                            
                            # 시상명 기준으로 인덱스 병합
                            temp_results = pd.merge(results, rule_order_map, on='시상명', how='left')
                            temp_results.rename(columns={'index': 'rule_order'}, inplace=True)
                            results = temp_results.sort_values('rule_order').drop(columns=['rule_order'])
                            
                            st.session_state.results_df = results
                            summary = get_award_summary(results)
                            
                            # 월별 필터링
                            # target_month = calc_params['target_date'].month
                            # month_str = f"{target_month}월"
                            # results = results[results['시상명'].str.contains(month_str, na=False)]
                            
                            results = resolve_competing_awards(results)
                            st.session_state.results_df = results
                            summary = get_award_summary(results)
                        else:
                            results = pd.DataFrame()
                            summary = {'총지급예상금액': 0, '시상개수': 0, '선택된시상개수': 0, '평균달성률': 0}

                    # 총실적은 조회 기간(Month)으로 엄격하게 필터링하여 표시
                    month_filtered_df = filter_by_period(processed_df, calc_params['period_start'], calc_params['period_end'])
                    summary['총실적'] = month_filtered_df['보험료'].sum()
                    summary['당월계약건수'] = len(month_filtered_df)
                    # summary 딕셔너리에 기간 정보 주입 (footer report에서 사용)
                    summary['period_start'] = calc_params['period_start']
                    summary['period_end'] = calc_params['period_end']
                    
                    # 1. 통합 성과 분석 및 전략 (메트릭 + 가이드)
                    render_footer_report(results, processed_df, summary, calc_params["target_date"])
                    
                    # 2. 보험사별/상품별 실적 통계 (메트릭 포함)
                    st.markdown('<div style="margin-top: 1rem;"></div>', unsafe_allow_html=True)
                    render_performance_pivot(processed_df, summary, calc_params['period_start'], calc_params['period_end'])
                    
                    # 3. 실적 분석 추이 및 그래프
                    st.markdown('<div style="margin-top: 2rem;"></div>', unsafe_allow_html=True)
                    render_performance_graphs(processed_df, results, calc_params['period_start'], calc_params['period_end'])
                    
                    # 4. 상세 시상 내역 테이블
                    st.markdown('<div style="margin-top: 2rem;"></div>', unsafe_allow_html=True)
                    if not results.empty:
                        render_results_table(results)
                    else:
                        st.info("해당 기간에 달성한 시상 내역이 없습니다.")


                else:
                    # 전체 보기 (메인 대시보드)
                    current_period = (calc_params['period_start'], calc_params['period_end'])
                    
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

                    agent_payouts = []
                    processed_df, _ = preprocess_contracts(st.session_state.contracts_df, agent_name=None)
                    if calc_params['product_filter']:
                        processed_df = processed_df[processed_df['분류'].isin(calc_params['product_filter'])]
                        
                    if not all_results_df.empty:
                        filtered_all = all_results_df.copy()
                        if calc_params['type_filter']:
                            filtered_all = filtered_all[filtered_all['유형'].isin(calc_params['type_filter'])]

                        agent_groups = filtered_all.groupby('설계사')
                        for agent, group in agent_groups:
                            p_df = processed_df[processed_df['사원명'] == agent]
                            month_filtered_p_df = filter_by_period(p_df, calc_params['period_start'], calc_params['period_end'])
                            t_perf = month_filtered_p_df['보험료'].sum()
                            total_payout = group[group['선택여부'] == True]['최종지급금액'].sum()
                            
                            missed_opportunity_amt = 0
                            missed_count = 0
                            for _, r in group.iterrows():
                                ach = r.get('달성률', 0)
                                if 80 <= ach < 100:
                                    current_pay = r.get('최종지급금액', 0)
                                    target_pay = r.get('지급금액', 0) 
                                    if target_pay > current_pay:
                                         missed_opportunity_amt += (target_pay - current_pay)
                                         missed_count += 1

                            kb_pay = group[(group['회사'].str.contains('KB', case=False, na=False)) & (group['선택여부'] == True)]['최종지급금액'].sum()
                            sam_pay = group[(group['회사'].str.contains('삼성', case=False, na=False)) & (group['선택여부'] == True)]['최종지급금액'].sum()
                            
                            kb_perf = 0
                            sam_perf = 0
                            if '회사' in month_filtered_p_df.columns:
                                kb_perf = month_filtered_p_df[month_filtered_p_df['회사'].str.contains('KB', case=False, na=False)]['보험료'].sum()
                                sam_perf = month_filtered_p_df[month_filtered_p_df['회사'].str.contains('삼성', case=False, na=False)]['보험료'].sum()
                            elif '원수사' in month_filtered_p_df.columns:
                                kb_perf = month_filtered_p_df[month_filtered_p_df['원수사'].str.contains('KB', case=False, na=False)]['보험료'].sum()
                                sam_perf = month_filtered_p_df[month_filtered_p_df['원수사'].str.contains('삼성', case=False, na=False)]['보험료'].sum()

                            if total_payout > 0 or t_perf > 0:
                                other_perf = max(0, t_perf - kb_perf - sam_perf)
                                agent_payouts.append({
                                    '설계사': agent,
                                    '소속': p_df['지점'].iloc[0] if not p_df.empty and '지점' in p_df.columns else '-',
                                    '총지급액': total_payout,
                                    '지급률': (total_payout / t_perf * 100) if t_perf > 0 else 0,
                                    '총실적': t_perf,
                                    '달성시상수': len(group[(group['최종지급금액'] > 0) & (group['선택여부'] == True)]),
                                    '놓친기회금액': missed_opportunity_amt,
                                    '코칭필요': missed_count > 0,
                                    'KB지급액': kb_pay,
                                    '삼성지급액': sam_pay,
                                    'KB실적': kb_perf,
                                    '삼성실적': sam_perf,
                                    '기타실적': other_perf
                                })
                        
                        summary = {
                            '총지급예상금액': filtered_all[filtered_all['선택여부'] == True]['최종지급금액'].sum(),
                            '시상개수': len(filtered_all.groupby(['회사', '시상명'])),
                            '선택된시상개수': len(filtered_all[(filtered_all['최종지급금액'] > 0) & (filtered_all['선택여부'] == True)].groupby(['회사', '시상명'])),
                            '평균달성률': filtered_all['달성률'].mean() if not filtered_all.empty else 0,
                            '총실적': processed_df[
                                (processed_df['접수일'] >= pd.Timestamp(calc_params['period_start'])) & 
                                (processed_df['접수일'] <= pd.Timestamp(calc_params['period_end']))
                            ]['보험료'].sum()
                        }
                        summary['당월계약건수'] = len(processed_df[
                            (processed_df['접수일'] >= pd.Timestamp(calc_params['period_start'])) & 
                            (processed_df['접수일'] <= pd.Timestamp(calc_params['period_end']))
                        ])
                        st.session_state.agg_result_df = pd.DataFrame(agent_payouts)
                        
                        # 지점별 집계 데이터 생성
                        if not st.session_state.agg_result_df.empty:
                            branch_groups = st.session_state.agg_result_df.groupby('소속').agg({
                                '총지급액': 'sum',
                                '총실적': 'sum',
                                'KB실적': 'sum',
                                '삼성실적': 'sum',
                                '기타실적': 'sum'
                            }).reset_index()
                            
                            branch_groups['지급률'] = (branch_groups['총지급액'] / branch_groups['총실적'] * 100).fillna(0)
                            st.session_state.branch_agg_df = branch_groups
                        else:
                            st.session_state.branch_agg_df = pd.DataFrame()

                        st.session_state.dashboard_summary = summary
                    
                    agg_df = st.session_state.get('agg_result_df', pd.DataFrame())
                    branch_agg_df = st.session_state.get('branch_agg_df', pd.DataFrame())
                    summary = st.session_state.get('dashboard_summary', {})
                    
                    # 지점 필터가 설정된 경우 데이터 필터링
                    selected_branch = st.session_state.get('selected_branch_filter')
                    if selected_branch:
                        agg_df = agg_df[agg_df['소속'] == selected_branch]
                        # summary도 재계산해야 함
                        summary['총지급예상금액'] = agg_df['총지급액'].sum()
                        summary['총실적'] = agg_df['총실적'].sum()
                        # (지점 필터 시 summary의 다른 항목들은 지점 단위 데이터로 표시되도록 render_performance_pivot에서 contracts_df로 처리됨)

                    if not agg_df.empty:
                        # 1. 보험사별/상품별 실적 통계 (메트릭 카드 포함)
                        # 지점 필터된 경우의 contracts_df 준비
                        branch_filtered_contracts = processed_df.copy()
                        if selected_branch:
                             branch_filtered_contracts = branch_filtered_contracts[branch_filtered_contracts['지점'] == selected_branch]
                        
                        render_performance_pivot(branch_filtered_contracts, summary, calc_params['period_start'], calc_params['period_end'])

                        # 2. 월간 계약 데이터 상세 보기
                        with st.expander(f"📅 {calc_params['target_date'].strftime('%Y년 %m월')} {'['+selected_branch+'] ' if selected_branch else ''}전체 계약 내역 상세보기", expanded=False):
                            target_m = calc_params['target_date'].month
                            target_y = calc_params['target_date'].year
                            monthly_contracts = branch_filtered_contracts[
                                (branch_filtered_contracts['접수일'].dt.year == target_y) & 
                                (branch_filtered_contracts['접수일'].dt.month == target_m)
                            ].copy()
                            
                            if not monthly_contracts.empty:
                                # 1. 컬럼 매칭 및 명칭 정리
                                # 원본에 이미 '사원명'이 있다면 '설계사'를 굳이 '사원명'으로 바꿀 때 중복 발생
                                display_contracts = monthly_contracts.copy()
                                
                                # 보험사 통합 (회사, 보험사, 원수사 중 하나만 선택)
                                for col in ['회사', '원수사']:
                                    if col in display_contracts.columns and '보험사' in display_contracts.columns:
                                        display_contracts = display_contracts.drop(columns=[col])
                                    elif col in display_contracts.columns:
                                        display_contracts = display_contracts.rename(columns={col: '보험사'})
                                
                                # 사원명 통합 (설계사 -> 사원명)
                                if '설계사' in display_contracts.columns:
                                    if '사원명' in display_contracts.columns:
                                        display_contracts = display_contracts.drop(columns=['설계사'])
                                    else:
                                        display_contracts = display_contracts.rename(columns={'설계사': '사원명'})
                                
                                # 2. 최종 출력 컬럼 정의 (순서 유지 및 중복 제거)
                                target_order = ['보험사', '접수일', '사원명', '소속', '상품명', '분류', '보험료', '계약자']
                                final_cols = []
                                for c in target_order:
                                    if c in display_contracts.columns and c not in final_cols:
                                        final_cols.append(c)
                                
                                # 3. 데이터 선택 및 중복 인덱스/컬럼 최종 정리
                                display_contracts = display_contracts[final_cols].sort_values('접수일')
                                display_contracts.columns = [str(c) for c in display_contracts.columns] # 컬럼명 문자열 강제
                                
                                # 중복 컬럼 최종 확인 및 제거 (Pandas 기능 이용)
                                display_contracts = display_contracts.loc[:, ~display_contracts.columns.duplicated()]
                                
                                st.dataframe(
                                    display_contracts.style.format({'보험료': '{:,.0f}원'}),
                                    column_config={
                                        "접수일": st.column_config.DateColumn("접수일", format="YYYY-MM-DD"),
                                        "보험료": st.column_config.TextColumn("보험료")
                                    },
                                    use_container_width=True,
                                    hide_index=True
                                )
                            else:
                                st.info("조회된 계약 내역이 없습니다.")

                        st.markdown('<div style="margin-top: 3rem;"></div>', unsafe_allow_html=True)

                        # 3. 실적 분석 추이 (이동됨)
                        render_performance_graphs(processed_df, display_period_start=calc_params['period_start'], display_period_end=calc_params['period_end'])

                        st.markdown('<div style="margin-top: 3rem;"></div>', unsafe_allow_html=True)

                        st.markdown('<div style="margin-top: 3rem;"></div>', unsafe_allow_html=True)

                        # 4. 팀별(지점별) 현황 (지점 필터가 없을 때만 표시하거나, 항상 표시)
                        from ui_components import render_agent_list_ui, render_branch_list_ui
                        if not selected_branch:
                            st.subheader(f"🏢 팀별 현황 ({len(branch_agg_df)}개 지점)", anchor="teams-section")
                            render_branch_list_ui(branch_agg_df)
                            st.markdown('<div style="margin-top: 3rem;"></div>', unsafe_allow_html=True)

                        # 5. 설계사별 현황 데이터 준비 (필터/정렬 전 로직 실행)
                        display_df = agg_df.copy()
                        
                        # 세션 상태에서 필터 값 미리 가져오기 (헤더의 인원수와 동기화)
                        search_q_val = st.session_state.get('agent_search_box', "").strip().lower()
                        branch_f_val = st.session_state.get('branch_filter_box', [])
                        coaching_f_val = st.session_state.get('coaching_filter_select', "전체 설계사 보기")

                        # 데이터 필터링 (위젯 렌더링 전 수행하여 개수 정확히 측정)
                        if branch_f_val: display_df = display_df[display_df['소속'].isin(branch_f_val)]
                        if search_q_val:
                            display_df = display_df[(display_df['설계사'].str.lower().str.contains(search_q_val, na=False)) | (display_df['소속'].str.lower().str.contains(search_q_val, na=False))]
                        if coaching_f_val == "코칭 대상자만 보기": display_df = display_df[display_df['코칭필요'] == True]
                        
                        sort_col = st.session_state.get('agg_sort_col', '총지급액')
                        sort_desc = st.session_state.get('agg_sort_descending', True)
                        if sort_col in display_df.columns: display_df = display_df.sort_values(sort_col, ascending=not sort_desc)

                        # UI 출력 (헤더 -> 레이블 -> 필터 위젯 순)
                        st.subheader(f"👥 {'['+selected_branch+'] ' if selected_branch else ''}설계사별 현황 ({len(display_df)}명)", anchor="agents-section")
                        st.markdown('<div style="margin-bottom: 0.5rem; font-weight: 600; color: #475569; font-size: 0.9rem;">🔍 현황 검색 및 필터</div>', unsafe_allow_html=True)
                        
                        f_col1, f_col2, f_col3 = st.columns([2, 1.5, 1.5])
                        with f_col1:
                            st.text_input("설계사 또는 지점 검색", placeholder="이름 또는 지점명 입력...", key="agent_search_box", label_visibility="collapsed")
                        with f_col2:
                            unique_branches = sorted(agg_df['소속'].unique()) if '소속' in agg_df.columns else []
                            st.multiselect("지점 필터", options=unique_branches, placeholder="지점 선택", key="branch_filter_box", label_visibility="collapsed")
                        with f_col3:
                            st.selectbox("성과 관리 필터", ["전체 설계사 보기", "코칭 대상자만 보기"], index=0, key="coaching_filter_select", label_visibility="collapsed")
                        
                        st.markdown('<div style="margin-top: 1rem;"></div>', unsafe_allow_html=True)
                        
                        render_agent_list_ui(display_df.reset_index(drop=True))
                    else:
                        st.warning("집계된 실적 데이터가 없습니다.")
                        st.caption(f"* 총 {len(display_contracts)}건의 계약이 조회되었습니다.")
                
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
