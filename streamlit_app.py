
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import os

# --- Module Imports ---
from data_loader import (
    load_contracts_from_csv, load_rules_from_csv, 
    load_contracts_from_url, load_rules_from_url,
    preprocess_contracts, validate_contracts, validate_rules,
    get_period_dates, load_consecutive_rules
)
from incentive_engine import (
    calculate_all_awards, get_award_summary, 
    resolve_competing_awards, calculate_all_agents_awards,
    find_golden_opportunities
)
from analysis import analyze_agents_performance, analyze_branch_performance
from ui_components import render_award_card, render_agent_list_ui, render_branch_list_ui

# --- Config & CSS ---
st.set_page_config(
    page_title="VIBE 인센티브 대시보드 v1",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS
st.markdown("""
<style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
    
    * { font-family: Pretendard, sans-serif !important; }
    
    /* 네비게이션 버튼 스타일 통일 */
    .nav-btn-fixed {
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        height: 28px !important;
        padding: 0 12px !important;
        font-size: 13px !important;
        font-weight: 600 !important;
        background-color: #F1F5F9 !important;
        color: #475569 !important;
        border-radius: 6px !important;
        text-decoration: none !important;
        transition: all 0.2s !important;
    }
    .nav-btn-fixed:hover {
        background-color: #E2E8F0 !important;
        color: #1E293B !important;
    }
    
    .stApp { background-color: #F8FAFC; }
</style>
""", unsafe_allow_html=True)

# --- Scroll Trigger Logic ---
if st.session_state.get('trigger_scroll_top', False):
    st.components.v1.html("""
        <script>
            window.parent.scrollTo(0, 0);
            var count = 0;
            var interval = setInterval(function() {
                window.parent.scrollTo(0, 0);
                count++;
                if (count > 5) clearInterval(interval);
            }, 50);
        </script>
    """, height=0)
    st.session_state.trigger_scroll_top = False

# --- Initialization ---
def init_session_state():
    if 'contracts_df' not in st.session_state:
        st.session_state.update({
            'contracts_df': None,
            'rules_df': None,
            'consecutive_rules': None,
            'data_loaded': False,
            'agent_name_input': None,
            'active_menu': '대시보드',
            'shadow_year': datetime.now().year,
            'shadow_month': datetime.now().month,
            'trigger_scroll_top': False
        })
    
    if st.session_state.get('consecutive_rules') is None:
        try:
            st.session_state.consecutive_rules = load_consecutive_rules()
        except:
            st.session_state.consecutive_rules = pd.DataFrame()

init_session_state()

# --- Sidebar ---
with st.sidebar:
    st.title("📂 데이터 로드")
    method = st.radio("방식", ["파일", "URL"], horizontal=True)
    if method == "파일":
        c_file = st.file_uploader("계약 (CSV)", type=['csv'])
        r_file = st.file_uploader("규칙 (CSV)", type=['csv'])
        if st.button("로드", use_container_width=True) and c_file and r_file:
            st.session_state.contracts_df = load_contracts_from_csv(c_file)
            st.session_state.rules_df = load_rules_from_csv(r_file)
            st.session_state.data_loaded = True
            st.rerun()
    else:
        url = st.text_input("Sheets URL")
        if st.button("로드", use_container_width=True) and url:
            st.session_state.contracts_df = load_contracts_from_url(url)
            st.session_state.rules_df = load_rules_from_url(url)
            st.session_state.data_loaded = True
            st.rerun()

# --- Header ---
h1, h2, h3, h4 = st.columns([3, 4, 1.2, 1])
with h1: st.subheader("📊 인센티브 대시보드")
with h3:
    y_list = [2024, 2025, 2026]
    sel_y = st.selectbox("년", y_list, index=y_list.index(st.session_state.shadow_year) if st.session_state.shadow_year in y_list else 1)
    if sel_y != st.session_state.shadow_year:
        st.session_state.shadow_year = sel_y
        st.session_state.trigger_scroll_top = True
        st.rerun()
with h4:
    sel_m = st.selectbox("월", range(1, 13), index=st.session_state.shadow_month - 1)
    if sel_m != st.session_state.shadow_month:
        st.session_state.shadow_month = sel_m
        st.session_state.trigger_scroll_top = True
        st.rerun()

# Date Range
p_start, p_end = get_period_dates("월간", datetime(st.session_state.shadow_year, st.session_state.shadow_month, 1))

# --- Main Content ---
if not st.session_state.data_loaded:
    st.info("사이드바에서 데이터를 로드해 주세요.")
else:
    tab1, tab2 = st.tabs(["개인별 현황", "전체 분석"])
    
    with tab1:
        s1, s2 = st.columns([3, 1])
        with s1:
            name = st.text_input("설계사명 검색", value=st.session_state.agent_name_input or "")
        with s2:
            if st.button("초기화", use_container_width=True):
                st.session_state.agent_name_input = None
                st.rerun()
        
        if name != st.session_state.agent_name_input:
            st.session_state.agent_name_input = name
            st.rerun()
            
        if st.session_state.agent_name_input:
            c_processed, _ = preprocess_contracts(st.session_state.contracts_df, agent_name=st.session_state.agent_name_input)
            results = calculate_all_awards(c_processed, st.session_state.rules_df, p_start, p_end, 
                                           agent_name=st.session_state.agent_name_input,
                                           consecutive_rules=st.session_state.consecutive_rules)
            final = resolve_competing_awards(results)
            summary = get_award_summary(final)
            
            sc1, sc2, sc3 = st.columns(3)
            sc1.metric("예상 수령액", f"{int(summary['총지급예상금액']):,}원")
            sc2.metric("달성 시상", f"{summary['선택된시상개수']}개")
            sc3.metric("평균 달성률", f"{summary['평균달성률']:.1f}%")
            
            st.divider()
            if not final.empty:
                for idx, row in final.iterrows():
                    if row.get('선택여부', True):
                        render_award_card(row, idx)
            else:
                st.warning("내역이 없습니다.")
        else:
            st.info("이름을 입력해 주세요.")
            
    with tab2:
        all_c, _ = preprocess_contracts(st.session_state.contracts_df)
        with st.spinner("분석 중..."):
            ana_df = analyze_agents_performance(all_c, st.session_state.rules_df, p_start, p_end)
        if not ana_df.empty:
            m1, m2, m3 = st.columns(3)
            m1.metric("전체 실적", f"{int(ana_df['총실적'].sum()/10000):,}만")
            m2.metric("총 지급액", f"{int(ana_df['총예상수익'].sum()/10000):,}만")
            m3.metric("인당 평균", f"{int(ana_df['총예상수익'].mean()/10000):,}만")
            st.divider()
            render_agent_list_ui(ana_df)
            branch_df = analyze_branch_performance(ana_df)
            render_branch_list_ui(branch_df)
        else:
            st.warning("데이터가 없습니다.")

# --- Footer (KST) ---
# 한국 시간은 UTC+9
kst_now = datetime.utcnow() + timedelta(hours=9)
st.markdown(f"""
<div style="text-align: center; color: #94A3B8; font-size: 0.8rem; margin-top: 60px; padding-bottom: 20px;">
    최종 업데이트: {kst_now.strftime('%Y-%m-%d %H:%M:%S')} (KST)
</div>
""", unsafe_allow_html=True)
