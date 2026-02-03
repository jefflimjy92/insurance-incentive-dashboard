"""
분석 기능 모듈
놓친 기회 분석, 전략 전환 시점 분석, 일일 코칭 리포트
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any


def regret_analysis(results_df: pd.DataFrame, rules_df: pd.DataFrame) -> pd.DataFrame:
    """
    놓친 기회 분석: 달성률 80-99%인 시상 중 ROI가 높은 것을 찾아냄
    
    Args:
        results_df: 정산결과 DataFrame
        rules_df: 시상규칙 DataFrame (다음 단계 보상 조회용)
    
    Returns:
        pd.DataFrame: 놓친 기회 목록 (ROI 내림차순)
    """
    if results_df.empty:
        return pd.DataFrame()
    
    # 조건 필터링: 달성률 80-99%, 다음 목표 존재
    mask = (
        (results_df['달성률'] >= 80) & 
        (results_df['달성률'] < 100) & 
        (results_df['다음목표'].notna()) &
        (results_df['부족금액'] > 0)
    )
    
    regrets = results_df[mask].copy()
    
    if regrets.empty:
        return pd.DataFrame()
    
    # 다음 단계 보상 계산
    def get_next_reward(row):
        """다음 단계 보상 조회"""
        시상명 = row['시상명']
        회사 = row['회사']
        현재단계 = row.get('달성단계', 0) or 0
        다음단계 = 현재단계 + 1
        
        # 규칙에서 찾기
        rule_match = rules_df[
            (rules_df['시상명'] == 시상명) & 
            (rules_df['회사'] == 회사)
        ]
        
        if rule_match.empty:
            return row['지급금액'] * 1.5  # 추정값
        
        rule = rule_match.iloc[0]
        
        if 현재단계 == 0:
            # 아직 미달성, 1단계 보상이 추가 보상
            return rule.get('1단계보상', 0) or 0
        else:
            # 다음 단계 보상 - 현재 보상
            next_reward = rule.get(f'{다음단계}단계보상', 0) or 0
            current_reward = row['지급금액']
            return max(next_reward - current_reward, 0)
    
    regrets['추가보상'] = regrets.apply(get_next_reward, axis=1)
    
    # ROI 계산: (추가보상 / 부족금액) × 100
    regrets['ROI'] = regrets.apply(
        lambda row: (row['추가보상'] / row['부족금액'] * 100) if row['부족금액'] > 0 else 0,
        axis=1
    )
    
    # ROI 높은 순 정렬
    regrets = regrets.sort_values('ROI', ascending=False)
    
    # 조언 메시지 생성
    def generate_advice(row):
        부족 = row['부족금액']
        추가 = row['추가보상']
        roi = row['ROI']
        
        if roi >= 500:
            return f"🔥 {부족:,.0f}원만 더 채우면 {추가:,.0f}원 추가! (ROI {roi:.0f}%)"
        elif roi >= 200:
            return f"⚠️ {부족:,.0f}원 투자로 {추가:,.0f}원 획득 가능! (ROI {roi:.0f}%)"
        else:
            return f"💡 {부족:,.0f}원으로 {추가:,.0f}원 달성 가능 (ROI {roi:.0f}%)"
    
    regrets['조언'] = regrets.apply(generate_advice, axis=1)
    
    regrets['목표실적'] = regrets['다음목표']
    
    return regrets[['회사', '시상명', '유형', '실적', '목표실적', '달성률', '부족금액', '추가보상', 'ROI', '조언']]


def pivot_analysis(contracts_df: pd.DataFrame) -> Optional[Dict[str, Any]]:
    """
    전략 전환 시점 분석: 7일 이동평균이 30% 이상 하락한 시점 탐지
    
    Args:
        contracts_df: 계약 데이터 DataFrame
    
    Returns:
        dict 또는 None: 전환점 정보
    """
    if contracts_df.empty or '접수일' not in contracts_df.columns:
        return None
    
    # 일별 집계
    daily = contracts_df.groupby(
        contracts_df['접수일'].dt.date
    )['보험료'].sum().reset_index()
    
    daily.columns = ['날짜', '일실적']
    daily = daily.sort_values('날짜')
    
    if len(daily) < 7:
        return None  # 데이터 부족
    
    # 7일 이동평균
    daily['7일평균'] = daily['일실적'].rolling(window=7, min_periods=1).mean()
    
    # 이전 대비 변화율 계산
    daily['변화율'] = daily['7일평균'].pct_change() * 100
    
    # 급감 구간 탐지 (변화율 < -30%)
    pivots = daily[daily['변화율'] < -30].copy()
    
    if pivots.empty:
        return None
    
    # 첫 번째 전환점
    pivot_row = pivots.iloc[0]
    pivot_date = pivot_row['날짜']
    decline_rate = pivot_row['변화율']
    
    # 전환 전후 실적 비교
    pivot_idx = daily[daily['날짜'] == pivot_date].index[0]
    before_avg = daily.iloc[max(0, pivot_idx-7):pivot_idx]['일실적'].mean() if pivot_idx > 0 else 0
    after_avg = daily.iloc[pivot_idx:min(len(daily), pivot_idx+7)]['일실적'].mean()
    
    return {
        '전환일': pivot_date,
        '하락률': abs(decline_rate),
        '전환전평균': before_avg,
        '전환후평균': after_avg,
        '메시지': f"💡 {pivot_date}부터 효율이 {abs(decline_rate):.1f}% 급감했습니다. "
                  f"이 시점에 다른 보험사 시상으로 전환했다면 더 유리했을 수 있습니다."
    }


def generate_daily_report(results_df: pd.DataFrame, contracts_df: pd.DataFrame,
                          rules_df: pd.DataFrame, target_date: datetime,
                          agent_name: str) -> str:
    """
    일일 코칭 리포트 생성
    
    Args:
        results_df: 정산결과 DataFrame
        contracts_df: 계약 데이터 DataFrame
        rules_df: 시상규칙 DataFrame
        target_date: 기준 날짜
        agent_name: 설계사명
    
    Returns:
        str: 마크다운 형식 리포트
    """
    # 요약 통계
    selected = results_df[results_df['선택여부'] == True] if '선택여부' in results_df.columns else results_df
    total_incentive = results_df['최종지급금액'].sum() if '최종지급금액' in results_df.columns else results_df['지급금액'].sum()
    num_awards = len(selected)
    
    valid_rates = results_df['달성률'].dropna()
    avg_rate = valid_rates.mean() if len(valid_rates) > 0 else 0
    
    report = f"""
# 📊 {target_date.strftime('%Y년 %m월 %d일')} 인센티브 현황 리포트

**설계사**: {agent_name}

---

## 💰 종합 현황

| 항목 | 값 |
|------|------|
| **총 지급예상금액** | {total_incentive:,.0f}원 |
| **시상 개수** | {num_awards}개 |
| **평균 달성률** | {avg_rate:.1f}% |

---

## ⚠️ 놓친 기회 (달성률 80-99%)

"""
    
    # 놓친 기회 분석
    regrets = regret_analysis(results_df, rules_df)
    
    if not regrets.empty:
        for idx, row in regrets.head(3).iterrows():
            report += f"""
### 🎯 [{row['회사']}] {row['시상명']}
- **달성률**: {row['달성률']:.1f}%
- **부족금액**: {row['부족금액']:,.0f}원
- **추가 보상**: {row['추가보상']:,.0f}원
- **ROI**: {row['ROI']:.0f}%
- {row['조언']}

"""
    else:
        report += "\n✅ **없음** - 모든 시상을 잘 달성하고 있습니다!\n\n"
    
    report += "---\n\n"
    
    # 전환 시점 분석
    pivot = pivot_analysis(contracts_df)
    if pivot:
        report += f"""
## 💡 전략 전환 제안

{pivot['메시지']}

- **전환 전 일평균**: {pivot['전환전평균']:,.0f}원
- **전환 후 일평균**: {pivot['전환후평균']:,.0f}원

---

"""
    
    # 오늘의 추천 행동
    report += """
## 🎉 오늘의 추천 행동

"""
    
    if not regrets.empty:
        top_regret = regrets.iloc[0]
        report += f"""1. **ROI 최고 시상에 집중!** - {top_regret['시상명']} ({top_regret['ROI']:.0f}%)
2. **부족금액 {top_regret['부족금액']:,.0f}원만 채우면** {top_regret['추가보상']:,.0f}원 추가 획득!
"""
    else:
        report += """1. 현재 진행 상황 유지하세요!
2. 새로운 시상 기회를 탐색해보세요.
"""
    
    report += f"""
3. 이번 주 남은 일수 확인하고 페이스 조절

---

**작성시간**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
    
    return report


def get_product_statistics(contracts_df: pd.DataFrame) -> pd.DataFrame:
    """
    상품 분류별 통계
    
    Args:
        contracts_df: 계약 데이터 (분류 컬럼 포함)
    
    Returns:
        pd.DataFrame: 분류별 통계
    """
    if contracts_df.empty or '분류' not in contracts_df.columns:
        return pd.DataFrame(columns=['분류', '계약건수', '총보험료', '평균보험료'])
    
    stats = contracts_df.groupby('분류').agg({
        '보험료': ['count', 'sum', 'mean']
    }).round(0)
    
    stats.columns = ['계약건수', '총보험료', '평균보험료']
    stats = stats.reset_index()
    
    return stats


def get_daily_trend(contracts_df: pd.DataFrame) -> pd.DataFrame:
    """
    일별 실적 추이
    
    Args:
        contracts_df: 계약 데이터
    
    Returns:
        pd.DataFrame: 일별 추이 (누적 포함)
    """
    if contracts_df.empty or '접수일' not in contracts_df.columns:
        return pd.DataFrame(columns=['날짜', '일실적', '누적실적'])
    
    daily = contracts_df.groupby(
        contracts_df['접수일'].dt.date
    )['보험료'].sum().reset_index()
    
    daily.columns = ['날짜', '일실적']
    daily = daily.sort_values('날짜')
    daily['누적실적'] = daily['일실적'].cumsum()
    
    return daily


def analyze_weekly_performance(contracts_df: pd.DataFrame, rules_df: pd.DataFrame,
                                period_start: datetime) -> List[Dict[str, Any]]:
    """
    주차별 성과 분석 (연속형 시상용)
    
    Args:
        contracts_df: 계약 데이터
        rules_df: 시상규칙
        period_start: 분석 시작일
    
    Returns:
        List[dict]: 주차별 분석 결과
    """
    results = []
    
    for week in range(4):
        week_start = period_start + timedelta(days=week * 7)
        week_end = week_start + timedelta(days=6)
        
        week_contracts = contracts_df[
            (contracts_df['접수일'] >= pd.Timestamp(week_start)) &
            (contracts_df['접수일'] <= pd.Timestamp(week_end))
        ]
        
        week_total = week_contracts['보험료'].sum() if len(week_contracts) > 0 else 0
        week_count = len(week_contracts)
        
        results.append({
            '주차': f'{week + 1}주차',
            '시작일': week_start.strftime('%m/%d'),
            '종료일': week_end.strftime('%m/%d'),
            '계약건수': week_count,
            '실적': week_total
        })
    return results


def analyze_cross_company_optimization(results_df: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    교차 최적화 분석: 이미 최고 구간을 달성한(포화 상태) 시상을 찾아,
    동일 상품군의 타사 시상으로 전환했을 때의 기회비용을 분석
    
    Args:
        results_df: 정산결과 DataFrame (모든 시상 단계 포함)
        
    Returns:
        List[dict]: 최적화 제언 목록
    """
    if results_df.empty:
        return []

    recommendations = []
    
    # 시상 단위로 그룹화하여 '포화 상태'인지 확인
    # 컬럼명 유연하게 대응
    col_map = {
        'company': next((c for c in ['회사', '보험사', '원수사'] if c in results_df.columns), '회사'),
        'award': next((c for c in ['시상명', '시상'] if c in results_df.columns), '시상명'),
        'type': next((c for c in ['분류', '상품군', '유형'] if c in results_df.columns), '분류'),
        'target': next((c for c in ['목표실적', '목표', 'target'] if c in results_df.columns), '목표실적'),
        'perf': next((c for c in ['실적', '보험료', 'perf'] if c in results_df.columns), '실적'),
        'payout': next((c for c in ['최종지급금액', '지급금액', 'payout'] if c in results_df.columns), '최종지급금액'),
        'base_reward': next((c for c in ['기준보상', '보상금액', 'reward'] if c in results_df.columns), '기준보상'),
        'period': next((c for c in ['기간', '종료일', '분석기간', 'end_date'] if c in results_df.columns), '기간')
    }

    # 필수 컬럼이 하나라도 없으면 빈 리스트 반환 (최소한의 기본 정보는 있어야 함)
    if not all(col in results_df.columns for col in [col_map['company'], col_map['award'], col_map['perf']]):
        return []

    # 신규: 분류 컬럼이 아예 없는 경우 '기타'로 처리
    if col_map['type'] not in results_df.columns:
        results_df[col_map['type']] = '기타'

    # 기간 컬럼이 없을 경우 빈 문자열로 처리
    if col_map['period'] not in results_df.columns:
        results_df[col_map['period']] = ""

    grouped = results_df.groupby([col_map['company'], col_map['award'], col_map['type'], col_map['period']])
    
    saturated_awards = [] 
    opportunity_awards = [] 
    
    for (company, award_name, product_type, period), group in grouped:
        # 이 시상의 최고 목표 실적 찾기
        max_target = group[col_map['target']].max()
        current_perf = group[col_map['perf']].max()
        
        # 간단한 판별: 실적이 최고 목표의 98% 이상이면 포화로 간주 (올림/반올림 오차 대비)
        if max_target > 0 and current_perf >= (max_target * 0.98):
            # 최고 단계 보상액 찾기
            best_row = group[group[col_map['target']] == max_target].iloc[0]
            current_reward = best_row.get(col_map['base_reward'], 0) or best_row.get(col_map['payout'], 0)
            
            saturated_awards.append({
                'company': company,
                'award_name': award_name,
                'product_type': product_type,
                'perf': current_perf,
                'max_target': max_target,
                'surplus': max(0, current_perf - max_target),
                'current_reward': current_reward,
                'period': period
            })
        else:
            # 아직 더 갈 곳이 남은 시상 (기회)
            possible_targets = group[group[col_map['target']] > current_perf]
            if not possible_targets.empty:
                # 다음 단계 하나가 아니라, 초과분으로 달성 가능한 '최중 최고 단계' 분석을 위해 전체 단계 정보 저장
                all_higher_tiers = possible_targets.sort_values(col_map['target'])
                
                # 현재 달성한 최고 단계의 보상액 찾기
                achieved_rows = group[group[col_map['target']] <= current_perf]
                current_max_reward = 0
                if not achieved_rows.empty:
                    best_achieved = achieved_rows.sort_values(col_map['target'], ascending=False).iloc[0]
                    current_max_reward = best_achieved.get(col_map['base_reward'], 0) or best_achieved.get(col_map['payout'], 0)

                opportunity_awards.append({
                    'company': company,
                    'award_name': award_name,
                    'product_type': product_type,
                    'current_perf': current_perf,
                    'current_max_reward': current_max_reward,
                    'higher_tiers': all_higher_tiers.to_dict('records'),
                    'period': period
                })

    # 2. 매칭 (포화 -> 기회)
    # 2-1. 상품군 키워드 추출 함수
    def get_keywords(name):
        for kw in ['인보험', '재물', '펫', '단체', '장기']:
            if kw in str(name): return kw
        return None

    for sat in saturated_awards:
        sat_kw = get_keywords(sat['award_name']) or sat['product_type']
        budget = sat['perf'] # 전체 실적을 이동 가능하다고 가정 (또는 surplus만?) -> 보통 surplus만큼 '더' 할 수 있다는 뜻
        
        matches = []
        for opp in opportunity_awards:
            if opp['company'] == sat['company']: continue
            # 동일 기간이 아니면 전환 불가 (사용자 규칙)
            if opp['period'] != sat['period']: continue
            
            opp_kw = get_keywords(opp['award_name']) or opp['product_type']
            
            if opp['product_type'] == sat['product_type'] or (sat_kw and sat_kw == opp_kw):
                # 이 기회 시상에서 '추가 실적' 투입 시 어디까지 갈 수 있는지 계산
                virtual_perf = opp['current_perf'] + sat['surplus']
                
                # 달성 가능한 행들 필터링
                reachable = [t for t in opp['higher_tiers'] if t[col_map['target']] <= virtual_perf]
                
                if reachable:
                    # 달성 가능한 최고 행
                    best_tier = sorted(reachable, key=lambda x: x[col_map['target']], reverse=True)[0]
                    potential_total_reward = best_tier.get(col_map['base_reward'], 0) or best_tier.get(col_map['payout'], 0)
                    marginal_gain = potential_total_reward - opp['current_max_reward']
                    
                    if marginal_gain > 0:
                        matches.append({
                            'company': opp['company'],
                            'award_name': opp['award_name'],
                            'current_perf': opp['current_perf'],
                            'current_reward': opp['current_max_reward'],
                            'optimized_reward': potential_total_reward,
                            'marginal_gain': marginal_gain,
                            'best_tier_target': best_tier[col_map['target']],
                            'gap_to_best': best_tier[col_map['target']] - opp['current_perf'],
                            'is_max_tier': best_tier[col_map['target']] == max([t[col_map['target']] for t in opp['higher_tiers']])
                        })
        
        matches.sort(key=lambda x: x['marginal_gain'], reverse=True)
        
        if matches:
            best_opp = matches[0]
            recommendations.append({
                'type': 'CROSS_OPTIMIZATION',
                'saturated_item': sat,
                'opportunity_item': best_opp,
                'message': f"{sat['company']} 초과분으로 {best_opp['company']} 최고구간 도전 가능!"
            })
            
    return recommendations
