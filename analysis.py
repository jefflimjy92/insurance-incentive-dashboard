import pandas as pd

def analyze_agents_performance(contracts, rules, p_start, p_end):
    if contracts.empty: return pd.DataFrame()
    from incentive_engine import calculate_all_awards, get_award_summary
    
    stats = []
    agents = contracts['모집인명'].unique() if '모집인명' in contracts.columns else contracts['사원명'].unique()
    
    for agent in agents:
        agent_c = contracts[contracts['모집인명'] == agent] if '모집인명' in contracts.columns else contracts[contracts['사원명'] == agent]
        res = calculate_all_awards(agent_c, rules, p_start, p_end, agent_name=agent)
        summ = get_award_summary(res)
        branch = agent_c['소속'].iloc[0] if '소속' in agent_c.columns else "미지정"
        stats.append({
            '설계사': agent,
            '소속': branch,
            '총실적': agent_c['보험료'].sum(),
            '총예상수익': summ['총지급예상금액']
        })
    return pd.DataFrame(stats)

def analyze_branch_performance(ana_df):
    if ana_df.empty: return pd.DataFrame()
    return ana_df.groupby('소속').agg({'설계사': 'count', '총실적': 'sum', '총예상수익': 'sum'}).reset_index()
