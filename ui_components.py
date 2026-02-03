
import pandas as pd
import streamlit as st

def render_award_cards(results_df: pd.DataFrame):
    """
    Render individual awards as visual cards in a grid layout.
    Replaces the previous dense table view with a more engaging dashboard style.
    """
    if results_df is None or results_df.empty:
        st.info("표시할 시상 내역이 없습니다.")
        return

    st.markdown("""
    <style>
        .award-card {
            background-color: white;
            border: 1px solid #E2E8F0;
            border-radius: 12px;
            padding: 1.25rem;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
            transition: all 0.2s;
            height: 100%;
        }
        .award-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
            border-color: #CBD5E1;
        }
        .award-badge {
            display: inline-block;
            padding: 0.25rem 0.6rem;
            border-radius: 9999px;
            font-size: 0.75rem;
            font-weight: 600;
        }
        .badge-achieved { background-color: #D1FAE5; color: #047857; }
        .badge-progress { background-color: #FEF3C7; color: #B45309; }
        .badge-fail { background-color: #F1F5F9; color: #64748B; }
        .award-title {
            font-size: 1.1rem;
            font-weight: 700;
            color: #1E293B;
            margin-top: 0.5rem;
            margin-bottom: 0.25rem;
        }
        .award-company {
            font-size: 0.85rem;
            color: #64748B;
            margin-bottom: 0.75rem;
        }
        .award-metric {
            display: flex;
            justify-content: space-between;
            align-items: flex-end;
            margin-bottom: 0.5rem;
        }
        .metric-label { font-size: 0.8rem; color: #94A3B8; }
        .metric-value { font-size: 1rem; font-weight: 600; color: #334155; }
        .payout-value { font-size: 1.25rem; font-weight: 800; color: #4F46E5; }
        .progress-bar-bg {
            background-color: #F1F5F9;
            height: 8px;
            border-radius: 4px;
            overflow: hidden;
            margin-top: 0.5rem;
        }
        .progress-bar-fill {
            height: 100%;
            border-radius: 4px;
            transition: width 0.5s ease-in-out;
        }
    </style>
    """, unsafe_allow_html=True)

    # Sort: Achieved (with payout) first, then close to achievement
    # Create copies to safely modify for sorting
    df = results_df.copy()
    df['sort_payout'] = df['최종지급금액'].fillna(0)
    df['sort_rate'] = df['달성률'].fillna(0)
    
    # Priority: High Payout > High Achievement Rate
    df = df.sort_values(['sort_payout', 'sort_rate'], ascending=[False, False])

    cols = st.columns(3) # 3-column grid
    
    for idx, row in df.iterrows():
        col = cols[idx % 3]
        
        with col:
            # Determine status
            payout = row.get('최종지급금액', 0)
            achieve_rate = row.get('달성률', 0)
            target = row.get('목표실적', 0)
            current = row.get('실적', 0)
            
            if payout > 0:
                status_class = "badge-achieved"
                status_text = "🎉 달성 완료"
                bar_color = "#10B981"
            elif achieve_rate >= 80:
                status_class = "badge-progress"
                status_text = "⚠️ 달성 임박"
                bar_color = "#F59E0B"
            else:
                status_class = "badge-fail"
                status_text = "진행 중"
                bar_color = "#CBD5E1"
            
            # Cap progress bar at 100% for visual consistency
            bar_pct = min(achieve_rate, 100)
            
            html = f"""
            <div class="award-card">
                <div style="display:flex; justify-content:space-between;">
                    <span class="award-badge {status_class}">{status_text}</span>
                    <span style="font-size:0.8rem; color:#94A3B8;">{row.get('유형', '기타')}</span>
                </div>
                <div class="award-title">{row['시상명']}</div>
                <div class="award-company">{row['회사']}</div>
                
                <div style="margin-top: 1rem;">
                    <div class="award-metric">
                        <span class="metric-label">현재 실적</span>
                        <span class="metric-value">{current:,.0f}원 <span style="font-size:0.8rem; color:#94A3B8;">/ {target:,.0f}원</span></span>
                    </div>
                    <div class="progress-bar-bg">
                        <div class="progress-bar-fill" style="width: {bar_pct}%; background-color: {bar_color};"></div>
                    </div>
                    <div style="text-align: right; font-size: 0.8rem; color: {bar_color}; margin-top: 4px; font-weight:600;">
                        달성률 {achieve_rate:.1f}%
                    </div>
                </div>
                
                <div style="margin-top: 1.2rem; padding-top: 1rem; border-top: 1px solid #F1F5F9; display:flex; justify-content:space-between; align-items:center;">
                    <span class="metric-label">예상 인센티브</span>
                    <span class="payout-value">{payout:,.0f}원</span>
                </div>
            </div>
            """
            st.markdown(html, unsafe_allow_html=True)
            st.markdown("<div style='margin-bottom: 1rem;'></div>", unsafe_allow_html=True)

def render_agent_list_ui(agg_df: pd.DataFrame):
    """
    Render the list of agents with a clean, button-based interface.
    Replaces the awkward checkbox interaction of st.dataframe.
    """
    st.markdown("""
    <style>
        .agent-row {
            padding: 1rem;
            background: white;
            border-radius: 8px;
            border: 1px solid #E2E8F0;
            margin-bottom: 0.5rem;
            display: flex;
            align-items: center;
            transition: box-shadow 0.2s;
        }
        .agent-row:hover {
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
            border-color: #CBD5E1;
        }
        .agent-name { font-weight: 700; font-size: 1rem; color: #1E293B; }
        .agent-branch { font-size: 0.85rem; color: #64748B; margin-left: 0.5rem; }
        .agent-stat-label { font-size: 0.75rem; color: #94A3B8; }
        .agent-stat-value { font-weight: 600; color: #334155; font-size: 0.95rem; }
        .agent-payout { font-weight: 700; color: #4F46E5; font-size: 1rem; }
    </style>
    """, unsafe_allow_html=True)

    # Header Row
    h1, h2, h3, h4, h5, h6, h7, h8 = st.columns([1.8, 1.3, 0.7, 1.1, 1.0, 1.0, 1.0, 0.7])
    with h1: st.markdown("**설계사 / 지점**")
    with h2: st.markdown("**총 예상 인센티브**")
    with h3: st.markdown("**지급률**")
    with h4: st.markdown("**전체 실적**")
    with h5: st.markdown("**🔵 삼성**")
    with h6: st.markdown("**🟡 KB**")
    with h7: st.markdown("**🟢 기타**")
    with h8: st.markdown("**상세**")
    
    st.markdown("<hr style='margin: 0.5rem 0;'>", unsafe_allow_html=True)

    if agg_df.empty:
        st.info("조건에 맞는 설계사가 없습니다.")
        return

    for idx, row in agg_df.iterrows():
        c1, c2, c3, c4, c5, c6, c7, c8 = st.columns([1.8, 1.3, 0.7, 1.1, 1.0, 1.0, 1.0, 0.7])
        
        with c1:
            st.markdown(f"<div><span style='font-weight:700;'>{row['설계사']}</span> <span style='color:#64748B; font-size:0.85rem;'>{row['소속']}</span></div>", unsafe_allow_html=True)
        
        with c2:
            st.markdown(f"<span style='color:#4F46E5; font-weight:700;'>{row['총지급액']:,.0f}원</span>", unsafe_allow_html=True)
        
        with c3:
            st.markdown(f"{row['지급률']:.1f}%")
        
        with c4:
             # 전체 실적 Bold Black
             st.markdown(f"<span style='font-weight:700; color:#334155;'>{row['총실적']:,.0f}원</span>", unsafe_allow_html=True)

        with c5:
            # Samsung 실적
            sam_val = row.get('삼성실적', 0)
            st.markdown(f"<span style='color:#1E40AF; font-weight:600;'>{sam_val:,.0f}</span>", unsafe_allow_html=True)
            
        with c6:
             # KB 실적
            kb_val = row.get('KB실적', 0)
            st.markdown(f"<span style='color:#B45309; font-weight:600;'>{kb_val:,.0f}</span>", unsafe_allow_html=True)
            
        with c7:
            # Others 실적
            others_val = row.get('기타실적', 0)
            st.markdown(f"<span style='color:#059669; font-weight:600;'>{others_val:,.0f}</span>", unsafe_allow_html=True)
            
        with c8:
            # Unified secondary style for all agents
            if st.button("조회", key=f"view_btn_{idx}_{row['설계사']}", type="secondary"):
                st.session_state.selected_agent = row['설계사']
                st.rerun()
        
        st.markdown("<div style='border-bottom: 1px solid #F1F5F9; margin: 0.25rem 0;'></div>", unsafe_allow_html=True)


def render_sticky_header(title, is_detail=False, back_callback=None, nav_items=None):
    """
    Renders a unified, sticky header for the application.
    Returns:
        container/column: The rightmost column to place additional controls (e.g. filters).
    """
    
    # CSS for Sticky Header & Layout Optimizations
    st.markdown("""
    <style>
        /* [Critical] Reset top padding */
        .block-container {
            padding-top: 0rem !important;
            padding-bottom: 5rem !important;
        }
        
        /* completely hide Streamlit's default header and decoration bar */
        header, [data-testid="stHeader"] { 
            display: none !important; 
            visibility: hidden !important;
            height: 0 !important;
        }
        
        /* Hide the colorful decoration line at the top */
        [data-testid="stDecoration"] {
            display: none !important;
            visibility: hidden !important;
            height: 0 !important;
        }
        
        /* Sticky Container - Logic: Ultra Compact & Flush Top */
        div[data-testid="stVerticalBlock"] > div:has(.sticky-header-marker) {
            position: sticky;
            top: 0;
            z-index: 9999;
            background: transparent;
            
            /* User Requested Adjustment */
            margin-top: -2.65rem; 
            padding-top: 0.5rem; /* Ultra slim */
            padding-bottom: 0.5rem; /* Ultra slim */
            margin-bottom: 1.5rem;
            
            overflow: visible;
        }

        /* The Full-Bleed Background Layer */
        div[data-testid="stVerticalBlock"] > div:has(.sticky-header-marker)::before {
            content: "";
            position: absolute;
            top: 0;
            left: -50vw; 
            width: 200vw; 
            height: 100%;
            background: rgba(255, 255, 255, 0.98);
            backdrop-filter: blur(12px);
            border-bottom: 1px solid #e2e8f0;
            box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
            z-index: -1; 
        }

        /* Inner Content Wrapper */
        div[data-testid="stVerticalBlock"] > div:has(.sticky-header-marker) > div {
             width: 100%;
        }

        .header-title {
            font-size: 1.25rem;
            font-weight: 800;
            color: #1e293b;
            letter-spacing: -0.5px;
            white-space: nowrap;
        }
        
        .nav-pills {
            display: flex;
            background: #f1f5f9;
            padding: 4px;
            border-radius: 8px;
            gap: 4px;
        }
        
        .nav-link-custom {
            text-decoration: none;
            color: #64748b;
            font-size: 0.85rem;
            font-weight: 600;
            padding: 6px 16px;
            border-radius: 6px;
            transition: all 0.2s;
            white-space: nowrap;
        }
        
        .nav-link-custom:hover {
            color: #1e293b;
            background: rgba(255,255,255,0.5);
        }
        
        /* Adjust for back button */
        .stButton button {
            border: none;
            background: transparent;
            padding: 0;
            color: #64748b;
        }
        .stButton button:hover {
            color: #4f46e5;
            background: transparent;
        }
    </style>
    """, unsafe_allow_html=True)

    with st.container():
        st.markdown('<div class="sticky-header-marker"></div>', unsafe_allow_html=True)
        
        # Adjust column ratios to give space for controls on the right
        # c1: Left (Title/Nav), c2: Spacer, c3: Right (Controls)
        c1, c2, c3 = st.columns([5, 0.5, 3.5], gap="small")
        
        with c1:
            # Layout: [BackBtn] [Title] [Nav]
            sub_cols = st.columns([0.4, 2.5, 5]) if is_detail else st.columns([3, 5])
            
            nav_col_idx = 2 if is_detail else 1
            
            if is_detail:
                # Back Button Column
                with sub_cols[0]:
                    if st.button("⬅️", key=f"back_btn_{title}"):
                        if back_callback:
                            back_callback()
                            st.rerun()
                # Title Column
                with sub_cols[1]:
                    st.markdown(f'<div class="header-title" style="margin-top: 5px;">{title}</div>', unsafe_allow_html=True)
            else:
                # Main Title Column
                with sub_cols[0]:
                    st.markdown(f'<div class="header-title">🎯 {title}</div>', unsafe_allow_html=True)

            # Navigation Pills
            with sub_cols[nav_col_idx]:
                if nav_items:
                    links_html = ""
                    for item in nav_items:
                        links_html += f'<a href="{item["anchor"]}" class="nav-link-custom">{item["label"]}</a>'
                    
                    st.markdown(f"""
                    <div style="display: flex; align-items: center; height: 100%; padding-left: 10px;">
                        <div class="nav-pills">
                            {links_html}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
        
        # Return the right column so the caller can place filters there
        return c3
