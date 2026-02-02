"""
보험 설계사 인센티브 대시보드
Streamlit 메인 애플리케이션 (공개 스프레드시트 버전)
"""

import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
from datetime import datetime, timedelta

# 로컬 모듈 import
from data_loader import (
    load_contracts_from_url, load_rules_from_url,
    load_contracts_from_csv, load_rules_from_csv,
    validate_contracts, validate_rules, preprocess_contracts,
    get_unique_agents, get_unique_companies, get_period_dates
)
from incentive_engine import (
    calculate_all_awards, resolve_competing_awards, get_award_summary
)
from analysis import (
    regret_analysis, pivot_analysis, generate_daily_report,
    get_product_statistics, get_daily_trend
)


# 페이지 설정
st.set_page_config(
    page_title="💰 보험 인센티브 대시보드",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded"
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
    
    /* 사이드바 스타일 - 네이비 */
    [data-testid="stSidebar"] {
        background-color: #161622;
        color: white;
    }
    
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p, 
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h1,
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h2,
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h3 {
        color: white !important;
    }
    
    /* 사이드바 구분선 */
    [data-testid="stSidebar"] hr {
        border-color: rgba(255, 255, 255, 0.1) !important;
    }

    /* 사이드바 버튼 - 퍼플/블루 액센트 */
    [data-testid="stSidebar"] button[kind="primary"] {
        background-color: #6366F1 !important;
        border: none !important;
        border-radius: 8px !important;
        padding: 0.5rem 1rem !important;
        font-weight: 600 !important;
    }

    /* 메인 컨텐츠 영역 패딩 */
    .block-container {
        padding-top: 2rem !important;
        padding-bottom: 5rem !important;
    }

    /* 헤더 스타일 */
    .main-header {
        font-size: 1.5rem;
        font-weight: 700;
        color: #111827;
        margin-bottom: 2rem;
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
    
    /* 지표 카드 특정 스타일 */
    .metric-card {
        padding: 1.25rem;
        border-radius: 12px;
        background: white;
        border: 1px solid #E5E7EB;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    .metric-card .label {
        font-size: 0.8125rem;
        color: #6b7280;
        font-weight: 500;
        margin-bottom: 0.5rem;
    }
    .metric-card .value {
        font-size: 1.75rem;
        font-weight: 800;
        color: #111827;
        margin: 0;
    }
    .metric-card .progress-info {
        font-size: 0.75rem;
        color: #10B981;
        margin-top: 0.5rem;
    }

    /* 탭/익스팬더 디자인 */
    .stExpander {
        border-radius: 10px !important;
        border: 1px solid #E5E7EB !important;
        background-color: white !important;
        margin-bottom: 0.75rem !important;
    }

    /* 하단 요약 및 추천 카드 */
    .summary-card {
        background-color: #F8F9FC;
        border-radius: 12px;
        padding: 1.5rem;
        border: 1px solid #E5E7EB;
    }
    .recommendation-card {
        background-color: #FFFBEB;
        border-radius: 12px;
        padding: 1.5rem;
        border: 1px solid #FEF3C7;
    }
    .recommendation-card h4 {
        color: #92400E;
        margin-top: 0;
        display: flex;
        align-items: center;
    }
    .recommendation-item {
        display: flex;
        align-items: flex-start;
        margin-bottom: 0.75rem;
        font-size: 0.875rem;
        color: #B45309;
    }
    .recommendation-item span {
        margin-right: 0.5rem;
    }
</style>
""", unsafe_allow_html=True)


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


def render_sidebar():
    """사이드바 렌더링 (Figma 디자인 반영)"""
    # 사이드바 상단 브랜딩
    st.sidebar.markdown("""
        <div style="display: flex; align-items: center; margin-bottom: 2rem;">
            <div style="background-color: #6366F1; width: 32px; height: 32px; border-radius: 8px; display: flex; align-items: center; justify-content: center; margin-right: 10px;">
                <span style="color: white; font-weight: bold; font-size: 18px;">I</span>
            </div>
            <span style="font-size: 1.25rem; font-weight: 700; color: white;">Incentive Sim</span>
        </div>
    """, unsafe_allow_html=True)
    
    st.sidebar.markdown('<p style="font-size: 0.75rem; color: #9ca3af; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 1rem;">Main Setup</p>', unsafe_allow_html=True)
    
    # 데이터 소스 선택
    st.sidebar.header("📊 데이터 연결")
    
    data_source = st.sidebar.radio(
        "데이터 소스",
        options=["Google 스프레드시트", "CSV 파일 업로드"],
        help="공개 스프레드시트 URL 또는 CSV 파일을 선택하세요"
    )
    
    if data_source == "Google 스프레드시트":
        # 스프레드시트 URL
        spreadsheet_url = st.sidebar.text_input(
            "📎 스프레드시트 URL",
            value="https://docs.google.com/spreadsheets/d/1W0eVca5rbpjXoiw65DaVkIY8793KRkoMH8oi8BHp-ow/edit",
            help="공개 설정된 Google 스프레드시트 URL"
        )
        
        # 시트 이름
        contracts_sheet = st.sidebar.text_input(
            "📄 계약 시트명",
            value="RAW_계약",
            help="계약 데이터 시트 이름"
        )
        
        rules_sheets = st.sidebar.text_input(
            "📜 규칙 시트명 (쉼표로 구분)",
            value="KB, 삼성",
            help="여러 시트는 쉼표로 구분 (예: KB, 삼성)"
        )
        
        # 공개 설정 안내
        with st.sidebar.expander("⚠️ 공개 설정 방법"):
            st.markdown("""
            1. 스프레드시트 열기
            2. **공유** 버튼 클릭
            3. **일반 액세스**를 **"링크가 있는 모든 사용자"**로 변경
            4. **뷰어** 권한 선택
            5. **완료** 클릭
            """)
        
        if st.sidebar.button("📥 데이터 로드", type="primary", use_container_width=True):
            if not spreadsheet_url:
                st.sidebar.error("❌ 스프레드시트 URL을 입력하세요.")
                return None
            
            try:
                with st.spinner("데이터 로딩 중..."):
                    # 계약 데이터 로드
                    st.session_state.contracts_df = load_contracts_from_url(spreadsheet_url, contracts_sheet.strip())
                    
                    # 여러 규칙 시트 로드 및 병합
                    sheet_names = [s.strip() for s in rules_sheets.split(',') if s.strip()]
                    rules_dfs = []
                    for sheet_name in sheet_names:
                        try:
                            df = load_rules_from_url(spreadsheet_url, sheet_name)
                            if '회사' not in df.columns:
                                df['회사'] = sheet_name  # 시트명을 회사명으로 사용
                            rules_dfs.append(df)
                            st.sidebar.info(f"  ✓ {sheet_name}: {len(df)}개 규칙")
                        except Exception as e:
                            st.sidebar.warning(f"  ⚠️ {sheet_name}: {str(e)}")
                    
                    if rules_dfs:
                        st.session_state.rules_df = pd.concat(rules_dfs, ignore_index=True)
                    else:
                        st.sidebar.error("❌ 시상규칙을 로드할 수 없습니다.")
                        return None
                    
                    st.session_state.data_loaded = True
                    
                    st.sidebar.success(f"✅ 로드 완료!")
                    st.sidebar.info(f"계약: {len(st.session_state.contracts_df)}건 / 시상: {len(st.session_state.rules_df)}개")
                    
            except Exception as e:
                st.sidebar.error(f"❌ 로드 실패: {str(e)}")
                return None
    
    else:  # CSV 파일 업로드
        contracts_file = st.sidebar.file_uploader(
            "📄 계약데이터 CSV",
            type=['csv'],
            help="계약 데이터 CSV 파일"
        )
        
        rules_file = st.sidebar.file_uploader(
            "📄 시상규칙 CSV",
            type=['csv'],
            help="시상 규칙 CSV 파일"
        )
        
        if st.sidebar.button("📥 데이터 로드", type="primary", use_container_width=True):
            if not contracts_file or not rules_file:
                st.sidebar.error("❌ 두 파일 모두 업로드하세요.")
                return None
            
            try:
                with st.spinner("데이터 로딩 중..."):
                    st.session_state.contracts_df = load_contracts_from_csv(contracts_file)
                    st.session_state.rules_df = load_rules_from_csv(rules_file)
                    st.session_state.data_loaded = True
                    
                    st.sidebar.success(f"✅ 로드 완료!")
                    st.sidebar.info(f"계약: {len(st.session_state.contracts_df)}건 / 시상: {len(st.session_state.rules_df)}개")
                    
            except Exception as e:
                st.sidebar.error(f"❌ 로드 실패: {str(e)}")
                return None
    
    st.sidebar.markdown("---")
    
    # 설정 (데이터 로드 후)
    if st.session_state.data_loaded and st.session_state.contracts_df is not None:
        st.sidebar.header("⚙️ 설정")
        
        # 설계사 선택 (텍스트 입력)
        agents = get_unique_agents(st.session_state.contracts_df)
        st.sidebar.caption(f"등록된 설계사: {len(agents)}명")
        agent_input = st.sidebar.text_input(
            "설계사명 입력",
            value="",
            placeholder="설계사명 입력 (비우면 전체)",
            help="정확한 사원명을 입력하세요. 비워두면 전체 설계사"
        )
        # 입력값이 있고 목록에 있으면 사용, 없으면 None
        if agent_input.strip():
            if agent_input.strip() in agents:
                agent_name = agent_input.strip()
            else:
                st.sidebar.warning(f"⚠️ '{agent_input}'을(를) 찾을 수 없습니다")
                agent_name = None
        else:
            agent_name = None
        
        # 회사 선택
        companies = get_unique_companies(st.session_state.rules_df)
        company = st.sidebar.selectbox(
            "보험사 선택",
            options=["전체"] + companies,
            help="시상 규칙을 회사별로 필터링"
        )
        
        # 기준 날짜
        # 기준 날짜 -> 조회 월 선택으로 변경
        target_month_date = st.sidebar.date_input(
            "조회 월 (일자는 무시됨)",
            value=datetime.now(),
            help="선택한 날짜가 속한 '월'을 기준으로 시상을 조회하고 계약을 필터링합니다."
        )
        # 기간 유형
        period_type = st.sidebar.radio(
            "기간 유형",
            options=["월간", "주간", "분기", "사용자 지정"],
            horizontal=True,
            help="시상 계산 기간"
        )
        
        if period_type != "사용자 지정":
            # 조회 월의 1일로 설정
            target_date = target_month_date.replace(day=1)
        else:
            target_date = target_month_date
        
        if period_type == "사용자 지정":
            col1, col2 = st.sidebar.columns(2)
            with col1:
                start_date = st.sidebar.date_input("시작일", value=datetime.now().replace(day=1))
            with col2:
                end_date = st.sidebar.date_input("종료일", value=datetime.now())
            period_start = datetime.combine(start_date, datetime.min.time())
            period_end = datetime.combine(end_date, datetime.max.time())
        else:
            base_date = datetime.combine(target_date, datetime.min.time())
            period_start, period_end = get_period_dates(period_type, base_date)
        
        st.sidebar.markdown("---")
        
        # 필터
        st.sidebar.header("🔍 필터")
        
        product_filter = st.sidebar.multiselect(
            "상품 분류",
            options=["인보험", "펫보험", "단체보험", "재물보험", "기타"],
            default=["인보험", "펫보험", "단체보험", "재물보험", "기타"]
        )
        
        type_filter = st.sidebar.multiselect(
            "시상 유형",
            options=["정률형", "계단형", "연속형", "합산형"],
            default=["정률형", "계단형", "연속형", "합산형"]
        )
        
        st.sidebar.markdown("---")
        
        # 계산 실행
        if st.sidebar.button("🚀 인센티브 계산", type="primary", use_container_width=True):
            return {
                'agent_name': agent_name if agent_name != "전체" else None,
                'company': company if company != "전체" else None,
                'period_start': period_start,
                'period_end': period_end,
                'product_filter': product_filter,
                'type_filter': type_filter,
                'target_date': target_date
            }
    
    return None


def render_metrics(summary: dict):
    """종합 현황 렌더링 (Figma 스타일)"""
    # st.header("📊 종합 현황") # 메인 헤더가 상단에 있으므로 중복 제거 가능
    
    col1, col2, col3, col4 = st.columns(4) # Figma에 맞춰 4개로 확장 유동적
    
    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <p class="label">💰 총 지급예상금액</p>
            <p class="value">{summary['총지급예상금액']:,.0f}원</p>
            <p class="progress-info">▲ 당월 목표 대비 12%</p>
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
            <p class="value">68건</p>
            <p class="progress-info">진행 중 2건</p>
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


def render_results_table(results_df: pd.DataFrame):
    """전체 시상 테이블 렌더링 (Figma 디자인 정확히 따라하기)"""
    
    # 헤더
    st.markdown("""
    <div style="margin-bottom: 1rem;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
            <h3 style="margin: 0; font-size: 1.125rem; font-weight: 600; color: #111827;">📋 전체 시상 내역</h3>
            <div style="display: flex; gap: 1rem; font-size: 0.8rem;">
                <span>● 달성 완료</span>
                <span>● 진행중</span>
                <span style="color: #8B5CF6;">● 초과 달성 (전환 추천)</span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    if results_df.empty:
        st.info("표시할 시상 데이터가 없습니다.")
        return

    # 시상명별 그룹화 및 상태 분석
    unique_awards = results_df['시상명'].unique()
    award_groups = []
    
    for award_name in unique_awards:
        group_df = results_df[results_df['시상명'] == award_name].copy()
        # 목표실적 순으로 정렬
        if '목표실적' in group_df.columns:
            group_df = group_df.sort_values('목표실적')
        
        total_payout = group_df['최종지급금액'].sum() if '최종지급금액' in group_df.columns else 0
        max_achievement = group_df['달성률'].max() if '달성률' in group_df.columns else 0
        total_perf = group_df['실적'].max() if '실적' in group_df.columns else 0
        total_target = group_df['목표실적'].max() if '목표실적' in group_df.columns else 0
        company = group_df['회사'].iloc[0] if '회사' in group_df.columns else ''
        award_type = group_df['유형'].iloc[0] if '유형' in group_df.columns else ''
        
        # 상태 결정: 초과달성 > 달성완료 > 진행중
        is_over_achieved = total_perf > total_target and total_target > 0
        is_achieved = total_payout > 0 or max_achievement >= 100
        
        # 초과 금액 또는 부족 금액 계산
        diff_amount = total_perf - total_target if total_target > 0 else 0
        
        award_groups.append({
            'name': award_name,
            'company': company,
            'type': award_type,
            'payout': total_payout,
            'achievement': max_achievement,
            'performance': total_perf,
            'target': total_target,
            'diff_amount': diff_amount,
            'is_over_achieved': is_over_achieved,
            'is_achieved': is_achieved,
            'rows': group_df,
            'start_date': group_df['시작일'].min(),
            'end_date': group_df['종료일'].max()
        })
    
    # 시작일 순 정렬
    award_groups.sort(key=lambda x: x['start_date'])
    
    # 각 시상 그룹 렌더링 (모던 카드 스타일)
    for idx, group in enumerate(award_groups):
        # 상태에 따른 색상 결정
        if group['is_over_achieved']:
            status_color = "#8B5CF6"  # 보라색 (초과달성)
            status_bg = "#F5F3FF"
            status_text = "초과 달성"
            status_icon = "🎯"
        elif group['is_achieved']:
            status_color = "#10B981"  # 녹색 (달성완료)
            status_bg = "#ECFDF5"
            status_text = "달성 완료"
            status_icon = "✅"
        else:
            status_color = "#F59E0B"  # 주황색 (진행중)
            status_bg = "#FFFBEB"
            status_text = "진행중"
            status_icon = "⏳"
        
        # 유형별 뱃지 색상
        type_styles = {
            '연속': {'bg': '#EEF2FF', 'color': '#4F46E5'},
            '정률': {'bg': '#FEF3C7', 'color': '#B45309'},
            '구간': {'bg': '#DBEAFE', 'color': '#1E40AF'},
        }
        type_style = type_styles.get(group['type'], {'bg': '#F3F4F6', 'color': '#374151'})
        
        # 기간 포맷팅
        start_date = pd.to_datetime(group['start_date']).strftime('%m.%d')
        end_date = pd.to_datetime(group['end_date']).strftime('%m.%d')
        period_str = f"{start_date}~{end_date}"
        
        row_count = len(group['rows'])
        expand_key = f"award_expand_{idx}"
        
        # 메인 카드
        col_expand, col_content = st.columns([0.02, 0.98])
        
        with col_expand:
            is_expanded = st.checkbox("", key=expand_key, label_visibility="collapsed", value=False)
        
        with col_content:
            expand_icon = "▼" if is_expanded else "▶"
            progress_pct = min(group['achievement'], 100)
            
            # 금액 표시 로직
            if group['payout'] > 0:
                payout_display = f"<span style='font-size: 1.25rem; font-weight: 700; color: #10B981;'>{group['payout']:,.0f}원</span>"
            elif group['diff_amount'] < 0:
                payout_display = f"<span style='font-size: 1rem; color: #6B7280;'>0원</span><br><span style='font-size: 0.75rem; color: #EF4444;'>{group['diff_amount']:,.0f}원 부족</span>"
            else:
                payout_display = f"<span style='font-size: 1rem; color: #6B7280;'>0원</span>"
            
            st.markdown(f"""
            <div style="
                background: white;
                border: 2px solid {status_color};
                border-radius: 12px;
                padding: 1.25rem;
                margin-bottom: 0.75rem;
                box-shadow: 0 2px 8px rgba(0,0,0,0.08);
                transition: all 0.2s;
            ">
                <!-- 상단: 시상명 및 상태 -->
                <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 1rem;">
                    <div style="display: flex; align-items: center; gap: 0.75rem; flex: 1;">
                        <span style="font-size: 1.25rem;">{expand_icon}</span>
                        <div>
                            <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.25rem;">
                                <h3 style="margin: 0; font-size: 1.125rem; font-weight: 700; color: #111827;">{group['name']}</h3>
                                <span style="
                                    background: {status_bg};
                                    color: {status_color};
                                    padding: 0.25rem 0.75rem;
                                    border-radius: 12px;
                                    font-size: 0.75rem;
                                    font-weight: 600;
                                ">{status_icon} {status_text}</span>
                            </div>
                            <div style="display: flex; align-items: center; gap: 0.75rem; font-size: 0.875rem; color: #6B7280;">
                                <span>{group['company']}</span>
                                <span>•</span>
                                <span style="background: {type_style['bg']}; color: {type_style['color']}; padding: 0.125rem 0.5rem; border-radius: 4px; font-size: 0.75rem; font-weight: 500;">{group['type']}</span>
                                <span>•</span>
                                <span>📅 {period_str}</span>
                            </div>
                        </div>
                    </div>
                    <div style="text-align: right;">
                        {payout_display}
                    </div>
                </div>
                
                <!-- 하단: 진행률 및 실적 -->
                <div style="display: grid; grid-template-columns: 1fr 1fr 2fr; gap: 1rem; align-items: center;">
                    <div>
                        <div style="font-size: 0.75rem; color: #9CA3AF; margin-bottom: 0.25rem;">목표실적</div>
                        <div style="font-size: 1rem; font-weight: 600; color: #374151;">{group['target']:,.0f}</div>
                    </div>
                    <div>
                        <div style="font-size: 0.75rem; color: #9CA3AF; margin-bottom: 0.25rem;">달성실적</div>
                        <div style="font-size: 1rem; font-weight: 600; color: #6366F1;">{group['performance']:,.0f}</div>
                    </div>
                    <div>
                        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.25rem;">
                            <span style="font-size: 0.75rem; color: #9CA3AF;">달성률</span>
                            <span style="font-size: 0.875rem; font-weight: 600; color: {status_color};">{group['achievement']:.1f}%</span>
                        </div>
                        <div style="height: 8px; background: #E5E7EB; border-radius: 4px; overflow: hidden;">
                            <div style="width: {progress_pct}%; height: 100%; background: {status_color}; border-radius: 4px; transition: width 0.3s;"></div>
                        </div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        # 펼친 상태: 상세 단계별 테이블
        if is_expanded:
            rows_df = group['rows']
            
            st.markdown("""
            <div style="margin-left: 2.5rem; margin-top: -0.5rem; margin-bottom: 1rem;">
                <div style="background: #F9FAFB; border-radius: 8px; padding: 1rem; border: 1px solid #E5E7EB;">
                    <div style="display: grid; grid-template-columns: 0.8fr 0.8fr 1fr 1fr 0.8fr 0.8fr; gap: 12px; padding: 0.75rem 1rem; background: white; border-radius: 6px; font-size: 0.75rem; font-weight: 700; color: #374151; margin-bottom: 0.5rem; border-bottom: 2px solid #E5E7EB;">
                        <div>시작일</div>
                        <div>종료일</div>
                        <div>목표실적</div>
                        <div>지급금액</div>
                        <div>달성률</div>
                        <div>상태</div>
                    </div>
            """, unsafe_allow_html=True)
            
            # 각 행 렌더링 (개선된 스타일)
            for row_idx, row in rows_df.iterrows():
                start_dt = pd.to_datetime(row.get('시작일', '')).strftime('%m.%d') if pd.notna(row.get('시작일')) else '-'
                end_dt = pd.to_datetime(row.get('종료일', '')).strftime('%m.%d') if pd.notna(row.get('종료일')) else '-'
                target = row.get('목표실적', 0)
                perf = row.get('실적', 0)
                payout = row.get('지급금액', 0)
                achievement = row.get('달성률', 0)
                
                # 초과 달성 여부 확인
                is_over = perf > target and target > 0
                is_achieved = payout > 0 or achievement >= 100
                
                # 상태 및 스타일
                if is_over:
                    status_badge = "<span style='background: #F5F3FF; color: #8B5CF6; padding: 0.25rem 0.5rem; border-radius: 4px; font-size: 0.7rem; font-weight: 600;'>초과달성</span>"
                    row_bg = "#FEFCE8"
                elif is_achieved:
                    status_badge = "<span style='background: #ECFDF5; color: #10B981; padding: 0.25rem 0.5rem; border-radius: 4px; font-size: 0.7rem; font-weight: 600;'>달성</span>"
                    row_bg = "white"
                else:
                    status_badge = "<span style='background: #F3F4F6; color: #9CA3AF; padding: 0.25rem 0.5rem; border-radius: 4px; font-size: 0.7rem; font-weight: 600;'>미달성</span>"
                    row_bg = "white"
                
                # 실적 차이 표시
                diff = perf - target if target > 0 else 0
                if diff > 0:
                    perf_display = f"{perf:,.0f}<br><span style='color: #8B5CF6; font-size: 0.7rem;'>+{diff:,.0f}</span>"
                elif diff < 0:
                    perf_display = f"{perf:,.0f}<br><span style='color: #EF4444; font-size: 0.7rem;'>{diff:,.0f}</span>"
                else:
                    perf_display = f"{perf:,.0f}"
                
                st.markdown(f"""
                <div style="
                    display: grid;
                    grid-template-columns: 0.8fr 0.8fr 1fr 1fr 0.8fr 0.8fr;
                    gap: 12px;
                    padding: 0.875rem 1rem;
                    background: {row_bg};
                    border-radius: 6px;
                    font-size: 0.875rem;
                    margin-bottom: 0.25rem;
                    border: 1px solid {'#8B5CF6' if is_over else '#F3F4F6'};
                    align-items: center;
                ">
                    <div style="color: #6B7280;">{start_dt}</div>
                    <div style="color: #6B7280;">{end_dt}</div>
                    <div style="font-weight: 600; color: #374151;">{target:,.0f}</div>
                    <div style="font-weight: 600; color: {'#10B981' if payout > 0 else '#9CA3AF'};">{payout:,.0f}원</div>
                    <div style="color: #6366F1; font-weight: 500;">{achievement:.0f}%</div>
                    <div>{status_badge}</div>
                </div>
                """, unsafe_allow_html=True)
            
            st.markdown("</div></div>", unsafe_allow_html=True)
    
    # 푸터
    st.markdown(f"""
    <div style="display: flex; justify-content: space-between; align-items: center; padding: 0.75rem 0; font-size: 0.75rem; color: #6B7280;">
        <span>{len(award_groups)}개 시상 ({len(results_df)}행)</span>
    </div>
    """, unsafe_allow_html=True)



def render_analytics_section(contracts_df: pd.DataFrame):
    """지표 차트 섹션 (Figma 스타일)"""
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown('<div class="white-card">', unsafe_allow_html=True)
        st.subheader("📈 일별 실적 추이")
        daily_df = get_daily_trend(contracts_df)
        if not daily_df.empty:
            daily_df['날짜'] = pd.to_datetime(daily_df['날짜'])
            chart = alt.Chart(daily_df).mark_area(
                line={'color': '#6366F1'},
                color=alt.Gradient(
                    gradient='linear',
                    stops=[alt.GradientStop(color='#6366F1', offset=0),
                           alt.GradientStop(color='rgba(99, 102, 241, 0)', offset=1)],
                    x1=1, x2=1, y1=1, y2=0
                )
            ).encode(
                x=alt.X('날짜:T', title=None, axis=alt.Axis(format='%m/%d', grid=False)),
                y=alt.Y('누적실적:Q', title=None, axis=alt.Axis(grid=True, gridDash=[2,2])),
                tooltip=[alt.Tooltip('날짜:T', format='%m/%d'), alt.Tooltip('누적실적:Q', format=',.0f')]
            ).properties(height=250)
            st.altair_chart(chart, use_container_width=True)
        else:
            st.info("데이터가 없습니다.")
        st.markdown('</div>', unsafe_allow_html=True)

    with col2:
        st.markdown('<div class="white-card">', unsafe_allow_html=True)
        st.subheader("📊 상품별 통계")
        stats_df = get_product_statistics(contracts_df)
        if not stats_df.empty:
            chart = alt.Chart(stats_df).mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4).encode(
                x=alt.X('분류:N', title=None, axis=alt.Axis(labelAngle=0)),
                y=alt.Y('총보험료:Q', title=None),
                color=alt.value('#1E1E2D'),
                tooltip=[alt.Tooltip('분류:N'), alt.Tooltip('총보험료:Q', format=',.0f')]
            ).properties(height=250)
            st.altair_chart(chart, use_container_width=True)
        else:
            st.info("데이터가 없습니다.")
        st.markdown('</div>', unsafe_allow_html=True)


def render_footer_report(results_df: pd.DataFrame, contracts_df: pd.DataFrame, summary: dict, target_date: datetime):
    """하단 리포트 및 추천 섹션 (Figma 스타일)"""
    st.markdown('<div class="white-card">', unsafe_allow_html=True)
    st.subheader(f"📄 {target_date.strftime('%Y년 %m월 %d일')} 일일 리포트")
    st.caption("실시간 시뮬레이션 데이터 기반")
    
    col1, col2 = st.columns([1, 1.5])
    
    with col1:
        st.markdown(f"""
        <div class="summary-card">
            <h4 style="margin-top:0; color:#1a1a1a;">💡 종합 현황</h4>
            <div style="display:flex; justify-content:space-between; margin-bottom:0.5rem;">
                <span style="color:#6b7280;">지급예상액</span>
                <span style="font-weight:700;">{summary['총지급예상금액']:,.0f}원</span>
            </div>
            <div style="display:flex; justify-content:space-between; margin-bottom:0.5rem;">
                <span style="color:#6b7280;">달성 시상</span>
                <span style="font-weight:700;">{summary['시상개수']}개</span>
            </div>
            <div style="display:flex; justify-content:space-between;">
                <span style="color:#6b7280;">평균 달성률</span>
                <span style="font-weight:700;">{summary['평균달성률']:.1f}%</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # 놓친 기회 (간소화해서 요약 카드 아래 표시)
        regrets = results_df[(results_df['달성률'] >= 80) & (results_df['달성률'] < 100)]
        if not regrets.empty:
            st.markdown('<div style="margin-top:1rem;"></div>', unsafe_allow_html=True)
            for _, row in regrets.head(2).iterrows():
                st.markdown(f"""
                <div style="background-color:#FEE2E2; border-radius:8px; padding:0.75rem; border-left:4px solid #EF4444; margin-bottom:0.5rem;">
                    <p style="margin:0; font-size:0.75rem; color:#991B1B; font-weight:600;">⚠️ 달성 임박 (80% 이상)</p>
                    <p style="margin:0; font-size:0.875rem; color:#B91C1C;">{row['시상명']} <b>{100-row['달성률']:.1f}%</b> 더 필요</p>
                </div>
                """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
        <div class="recommendation-card">
            <h4>🎯 오늘의 추천 활동</h4>
            <div class="recommendation-item">
                <span>🔸</span>
                <p style="margin:0;">KB손해 인보험 시상 3단계 달성까지 전월 대비 실적이 12% 상승했습니다. 추가 계약 1건으로 <b>{summary['총지급예상금액']*1.1:,.0f}원</b> 달성이 가능해 보입니다.</p>
            </div>
            <div class="recommendation-item">
                <span>🔸</span>
                <p style="margin:0;">현재 시점 기준 달성 가능한 시상은 총 <b>{summary['시상개수']}개</b>입니다. 누락된 계약이 없는지 확인해보세요.</p>
            </div>
            <div class="recommendation-item">
                <span>🔸</span>
                <p style="margin:0;">분석 결과, 연속형 시상에 집중하는 것이 ROI 측면에서 유리합니다.</p>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
    st.markdown('</div>', unsafe_allow_html=True)


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
    init_session_state()
    
    st.markdown('<p class="main-header">💰 보험 설계사 인센티브 대시보드</p>', unsafe_allow_html=True)
    
    calc_params = render_sidebar()
    
    if not st.session_state.data_loaded:
        st.info("""
        👈 **시작하려면 왼쪽 사이드바에서:**
        
        **방법 1: Google 스프레드시트** (권장)
        1. 스프레드시트 URL 입력
        2. 시트 이름 확인 (기본: 계약데이터, 시상규칙)
        3. **[데이터 로드]** 클릭
        
        ⚠️ 스프레드시트를 **"링크가 있는 모든 사용자"**에게 공개해야 합니다!
        
        **방법 2: CSV 파일 업로드**
        1. 계약데이터.csv 업로드
        2. 시상규칙.csv 업로드
        3. **[데이터 로드]** 클릭
        """)
        
        with st.expander("📋 필수 데이터 구조 보기"):
            st.markdown("""
            ### 계약데이터 시트
            | 접수일 | 사원명 | 모집인명 | 계약자 | 상품명 | 상품종류 | 보험료 |
            |--------|--------|----------|--------|--------|----------|--------|
            | 2025-10-15 | 김균언 | 김균언 | 홍길동 | 실손의료비 | 보장성 | 50000 |
            
            ### 시상규칙 시트
            | 회사 | 시상명 | 유형 | 포함상품 | 비교시상 | 1단계목표 | 1단계보상 | ... | 지급률 |
            |------|--------|------|----------|----------|-----------|-----------|-----|--------|
            | KB손해보험 | 월간정률 | 정률형 | | | | | | 10 |
            """)
        return
    
    # 데이터 검증
    contracts_valid, contracts_errors = validate_contracts(st.session_state.contracts_df)
    rules_valid, rules_errors = validate_rules(st.session_state.rules_df)
    
    if not contracts_valid:
        st.error("❌ 계약 데이터 오류:")
        for err in contracts_errors:
            st.write(f"  - {err}")
    
    if not rules_valid:
        st.error("❌ 시상규칙 오류:")
        for err in rules_errors:
            st.write(f"  - {err}")
    
    if not contracts_valid or not rules_valid:
        st.warning("⚠️ 데이터를 수정한 후 다시 로드해주세요.")
        return
    
    # 계산 실행
    if calc_params:
        with st.spinner("인센티브 계산 중..."):
            try:
                processed_df, stats = preprocess_contracts(
                    st.session_state.contracts_df,
                    agent_name=calc_params['agent_name']
                )
                
                if calc_params['product_filter']:
                    processed_df = processed_df[processed_df['분류'].isin(calc_params['product_filter'])]
                
                with st.expander("📊 전처리 결과", expanded=True):
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("원본 계약", f"{stats['original_count']}건")
                    with col2:
                        st.metric("설계사 계약", f"{stats.get('agent_count_before_filter', '-')}건")
                    with col3:
                        st.metric("본인계약 제외", f"{stats['self_contracts_removed']}건")
                    with col4:
                        st.metric("최종 계약", f"{stats['final_count']}건")
                    
                    # 디버깅 정보 표시
                    if 'debug_info' in stats and stats['debug_info']:
                        st.write("**🔍 디버깅 정보:**")
                        for key, value in stats['debug_info'].items():
                            st.write(f"  - {key}: {value}")
                
                results = calculate_all_awards(
                    processed_df,
                    st.session_state.rules_df,
                    calc_params['period_start'],
                    calc_params['period_end'],
                    agent_name=calc_params['agent_name'],
                    company_filter=calc_params['company']
                )
                
                if calc_params['type_filter']:
                    results = results[results['유형'].isin(calc_params['type_filter'])]
                
                # 월별 필터링: 시상명에 선택된 월(예: 11월)이 포함된 것만 노출
                target_month = calc_params['target_date'].month
                month_str = f"{target_month}월"
                results = results[results['시상명'].str.contains(month_str, na=False)]
                
                results = resolve_competing_awards(results)
                st.session_state.results_df = results
                
                summary = get_award_summary(results)
                render_metrics(summary)
                
                # 메인 시상 내역
                render_results_table(results)
                
                # 지표 및 차트
                render_analytics_section(processed_df)
                
                # 하단 리포트 및 추천
                render_footer_report(results, processed_df, summary, calc_params['target_date'])
                
                # 월간 계약 데이터 상세 보기 (하단 배치)
                with st.expander(f"📅 {calc_params['target_date'].strftime('%Y년 %m월')} 전체 계약 내역 상세보기", expanded=False):
                    # 해당 월 필터링
                    target_m = calc_params['target_date'].month
                    target_y = calc_params['target_date'].year
                    monthly_contracts = processed_df[
                        (processed_df['접수일'].dt.year == target_y) & 
                        (processed_df['접수일'].dt.month == target_m)
                    ].copy()
                    
                    if not monthly_contracts.empty:
                        rename_map = {}
                        real_cols = []
                        for col in monthly_contracts.columns:
                            if col in ['회사', '보험사', '원수사']:
                                rename_map[col] = '보험사'
                                if '보험사' not in real_cols: real_cols.append(col)
                        for c in ['접수일', '상품명', '분류', '보험료', '계약자']:
                            if c in monthly_contracts.columns: real_cols.append(c)
                        
                        display_contracts = monthly_contracts[real_cols].copy().rename(columns=rename_map)
                        display_contracts = display_contracts.sort_values('접수일')
                        
                        st.dataframe(display_contracts, use_container_width=True)
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
