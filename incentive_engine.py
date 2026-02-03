import pandas as pd
import numpy as np
from datetime import datetime

def calculate_single_award(contracts, rule, p_start, p_end):
    award_type = rule.get('유형', '')
    total = contracts['보험료'].sum() if not contracts.empty else 0
    
    res = {
        '시상명': rule.get('시상명'),
        '회사': rule.get('회사'),
        '유형': award_type,
        '실적': total,
        '지급금액': 0,
        '최종지급금액': 0,
        '달성률': 0,
        '다음목표': 0,
        '비교시상': rule.get('비교시상')
    }
    
    if award_type == '정률형':
        rate = pd.to_numeric(rule.get('지급률', 0), errors='coerce') or 0
        res['지급금액'] = total * (rate / 100)
        res['달성률'] = 100 if total > 0 else 0
    elif award_type in ['계단형', '합산형']:
        steps = []
        for i in range(1, 10):
            t = rule.get(f'{i}단계목표', 0)
            r = rule.get(f'{i}단계보상', 0)
            if t > 0: steps.append((t, r))
        
        achieved = [s for s in steps if s[0] <= total]
        if achieved:
            best = achieved[-1]
            res['지급금액'] = best[1]
            res['달성률'] = 100
        elif steps:
            res['다음목표'] = steps[0][0]
            res['달성률'] = (total / steps[0][0] * 100) if steps[0][0] > 0 else 0
            
    res['최종지급금액'] = res['지급금액']
    return res

def calculate_all_awards(contracts, rules, p_start, p_end, agent_name=None, consecutive_rules=None):
    results = []
    if rules.empty: return pd.DataFrame()
    for _, rule in rules.iterrows():
        # Filtering logic by company and period (simplified)
        res = calculate_single_award(contracts, rule, p_start, p_end)
        if res:
            res['설계사'] = agent_name
            results.append(res)
    return pd.DataFrame(results)

def resolve_competing_awards(results_df):
    if results_df.empty: return results_df
    df = results_df.copy()
    df['선택여부'] = True
    # Compare awards in same group
    for gp in df['비교시상'].dropna().unique():
        if str(gp).strip() == '': continue
        idx = df[df['비교시상'] == gp].index
        max_val = df.loc[idx, '지급금액'].max()
        for i in idx:
            if df.loc[i, '지급금액'] < max_val:
                df.loc[i, '선택여부'] = False
                df.loc[i, '최종지급금액'] = 0
    return df

def get_award_summary(df):
    if df.empty: return {'총지급예상금액': 0, '선택된시상개수': 0, '평균달성률': 0}
    sel = df[df.get('선택여부', True)]
    return {
        '총지급예상금액': sel['최종지급금액'].sum(),
        '선택된시상개수': len(sel[sel['최종지급금액'] > 0]),
        '평균달성률': df['달성률'].mean()
    }

def find_golden_opportunities(df, rules):
    return df[(df['달성률'] >= 80) & (df['달성률'] < 100)]

def calculate_all_agents_awards(contracts, rules, p_start, p_end):
    # This is a wrapper for batch processing
    return pd.DataFrame() # Placeholder
