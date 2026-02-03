import streamlit as st
import pandas as pd

def render_award_card(row, index):
    color = "#3B82F6" if row['달성률'] < 100 else "#10B981"
    st.markdown(f"""
    <div style="border: 1px solid #E2E8F0; border-radius: 12px; padding: 16px; margin-bottom: 12px; background: white;">
        <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
            <span style="font-size: 0.75rem; color: #64748B; font-weight: 600;">{row['회사']} | {row['유형']}</span>
            <span style="font-size: 1.1rem; font-weight: 700; color: #1E293B;">{int(row['최종지급금액']):,}원</span>
        </div>
        <div style="font-weight: 600; font-size: 1rem; color: #334155; margin-bottom: 12px;">{row['시상명']}</div>
        <div style="background: #F8FAFC; padding: 10px; border-radius: 8px;">
            <div style="display: flex; justify-content: space-between; font-size: 0.8rem; margin-bottom: 4px;">
                <span style="color: #64748B;">현재 실적: {int(row['실적']):,}원</span>
                <span style="color: {color}; font-weight: 700;">{row['달성률']:.1f}%</span>
            </div>
            <div style="width: 100%; height: 6px; background: #E2E8F0; border-radius: 3px;">
                <div style="width: {min(row['달성률'], 100)}%; height: 100%; background: {color}; border-radius: 3px;"></div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

def render_agent_list_ui(df):
    st.markdown("#### 👥 설계사 실적 순위")
    st.dataframe(df[['설계사', '소속', '총실적', '총예상수익']].sort_values('총실적', ascending=False), hide_index=True, use_container_width=True)

def render_branch_list_ui(df):
    st.markdown("#### 🏢 지점별 성과")
    st.dataframe(df, hide_index=True, use_container_width=True)
