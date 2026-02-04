"""
인센티브 계산 엔진
4가지 시상 유형 계산 및 경쟁 시상 처리
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from data_loader import filter_by_products, filter_by_period


def calc_rate_type(contracts: pd.DataFrame, rule_group: pd.DataFrame) -> Dict[str, Any]:
    """정률형 계산: 실적 × (지급률 / 100)"""
    rule = rule_group.iloc[0]
    total = contracts['보험료'].sum() if len(contracts) > 0 else 0
    
    rate = rule.get('지급률', 0)
    
    if pd.isna(rate) or rate <= 0:
        # Check for offset column issue (value might be in 5단계보상)
        offset_val = rule.get('5단계보상', 0)
        if pd.notna(offset_val) and offset_val > 0:
             rate = offset_val
        else:
             rate = 0
    
    incentive = total * (rate / 100)
    
    return {
        '실적': total,
        '지급금액': incentive,
        '최종지급금액': incentive,
        '달성단계': None,
        '달성률': 100.0 if total > 0 else 0.0,
        '다음목표': None,
        '부족금액': 0,
        '지급률': rate,
        'steps_info': [{'step': 1, 'target': 0, 'reward': rate, 'type': '정률', 'description': f'실적의 {rate}% 지급'}],
        'steps_info': [{'step': 1, 'target': 0, 'reward': rate, 'type': '정률', 'description': f'실적의 {rate}% 지급'}]
    }


def get_safe_val(source, keys: List[str], default=0):
    """여러 키 후보 중 존재하는 값을 안전하게 반환 (공백 제거 매칭 포함)"""
    names = []
    if hasattr(source, 'index'): # Pandas Series/DataFrame
        names = source.index.tolist()
    elif isinstance(source, dict):
        names = list(source.keys())
        
    # 1. 정확한 매칭
    for k in keys:
        if k in source and pd.notna(source[k]):
            return source[k]
            
    # 2. 공백 제거 매칭
    clean_names = {str(n).strip(): n for n in names}
    for k in keys:
        if k in clean_names:
            val = source[clean_names[k]]
            if pd.notna(val): return val
            
    return default


def calc_step_type(contracts: pd.DataFrame, rule_group: pd.DataFrame) -> Dict[str, Any]:
    """계단형 계산: 실적 구간에 따라 고정 보상액 지급 (행 기반 및 컬럼 기반 지원)"""
    total = contracts['보험료'].sum() if len(contracts) > 0 else 0
    
    steps = []
    # 1. 컬럼 기반 단계 확인 (1단계목표 ~ 9단계보상)
    rule_first = rule_group.iloc[0]
    for i in range(1, 10):
        target = rule_first.get(f'{i}단계목표')
        reward = rule_first.get(f'{i}단계보상')
        if pd.notna(target) and target > 0:
            steps.append({'target': target, 'reward': reward or 0, 'step': i})
            
    # 2. 행 기반 단계 확인 (항상 확인)
    # 단일 행으로 처리될 때도 목표실적을 읽어야 함
    for idx, row in rule_group.iterrows():
        target = row.get('목표실적')
        reward = row.get('보상금액')
        if pd.notna(target) and target > 0:
            steps.append({'target': target, 'reward': reward or 0, 'step': 0})
    
    # 중복 제거 및 정렬
    if not steps:
        return {'실적': total, '지급금액': 0, '달성단계': 0, '달성률': 0, '다음목표': None, '부족금액': 0}
        
    steps_df = pd.DataFrame(steps).sort_values('target')
    
    # 달성 단계 찾기
    achieved = steps_df[steps_df['target'] <= total]
    if not achieved.empty:
        best_step = achieved.iloc[-1]
        incentive = best_step['reward']
        
        # 다음 목표 찾기
        next_steps = steps_df[steps_df['target'] > total]
        if not next_steps.empty:
            next_target = next_steps.iloc[0]['target']
            shortage = next_target - total
            rate = (total / next_target) * 100
        else:
            next_target = None
            shortage = 0
            rate = 100.0
        
        return {
            '실적': total,
            '지급금액': incentive,
            '최종지급금액': incentive,
            '달성단계': best_step['step'] if best_step['step'] > 0 else len(achieved),
            '달성률': min(rate, 100.0),
            '다음목표': next_target,
            '부족금액': max(shortage, 0),
            '부족금액': max(shortage, 0),
            'steps_info': steps
        }
    else:
        # 1단계도 미달성
        first_target = steps_df.iloc[0]['target']
        return {
            '실적': total,
            '지급금액': 0,
            '최종지급금액': 0,
            '달성단계': 0,
            '달성률': (total / first_target * 100) if first_target > 0 else 0,
            '다음목표': first_target,
            '부족금액': max(first_target - total, 0),
            '부족금액': max(first_target - total, 0),
            'steps_info': steps
        }


def calc_continuous_type(contracts: pd.DataFrame, rule_group: pd.DataFrame, 
                         period_start: datetime, period_end: datetime,
                         consecutive_rules: pd.DataFrame = None) -> Dict[str, Any]:
    """
    연속형 계산: 구간별 달성 여부 확인 후 최종 보상 결정
    
    개선된 로직: 
    1. 전용 파일(consecutive_rules)에 데이터가 있으면 우선 사용
    2. 없으면 메인 시트(rule_group)의 '연속단계' 컬럼을 기반으로 동적 처리
    """
    try:
        rule = rule_group.iloc[0]
        award_name = rule.get('시상명', '')
        company = rule.get('회사', '')
        
        # 1. 연속형 규칙 데이터 소스 결정
        award_rules = pd.DataFrame()
        if consecutive_rules is not None and not consecutive_rules.empty:
            # 유연한 매칭 함수
            def flexible_match(v1, v2):
                if pd.isna(v1) or pd.isna(v2): return False
                v1_clean = str(v1).replace(' ', '').replace('_', '').lower()
                v2_clean = str(v2).replace(' ', '').replace('_', '').lower()
                return v1_clean == v2_clean or v1_clean in v2_clean or v2_clean in v1_clean

            award_rules = consecutive_rules[
                (consecutive_rules['시상명'].apply(lambda x: flexible_match(x, award_name))) & 
                (consecutive_rules['회사'].apply(lambda x: flexible_match(x, company)))
            ].copy()


        if award_rules.empty:
            if '연속단계' in rule_group.columns and rule_group['연속단계'].notna().any():
                award_rules = rule_group.copy()
                award_rules['구간번호'] = award_rules['연속단계'].astype(int)
            else:
                return calc_step_type(contracts, rule_group)
        else:
             # consecutive_rules에서 가져온 경우에도 '연속단계' 컬럼을 '구간번호'로 매핑
             if '연속단계' in award_rules.columns and '구간번호' not in award_rules.columns:
                 award_rules['구간번호'] = award_rules['연속단계'].astype(int)

        # 각 행별로 목표실적/보상금액이 비어있으면 1단계 컬럼에서 가져오기 (표준화)
        def normalize_rule_row(row):
            r = row.copy()
            if pd.isna(r.get('목표실적')) or r.get('목표실적') == 0:
                for i in range(1, 10):
                    v = r.get(f'{i}단계목표', 0)
                    if pd.notna(v) and v > 0: 
                        r['목표실적'] = v
                        break
            if pd.isna(r.get('보상금액')) or r.get('보상금액') == 0:
                for i in range(1, 10):
                    v = r.get(f'{i}단계보상', 0)
                    if pd.notna(v) and v > 0: 
                        r['보상금액'] = v
                        break
            return r
        
        award_rules = award_rules.apply(normalize_rule_row, axis=1)

        # 구간별 실적 계산
        period_stats = {}
        # Ensure '구간번호' exists
        if '구간번호' not in award_rules.columns:
             # Should not happen if logic matches CSV structure
             print(f"ERROR: '구간번호' column missing for {award_name}")
             return None
             
        total_periods = int(award_rules['구간번호'].max())
        
        for period_num in sorted(award_rules['구간번호'].unique()):
            p_rules = award_rules[award_rules['구간번호'] == period_num]
            
            p_start = p_rules['시작일'].min()
            p_end = p_rules['종료일'].max()
            
            if pd.isna(p_start): p_start = period_start
            if pd.isna(p_end): p_end = period_end
            
            # --- Year Correction Logic ---
            # If the parsed date is significantly in the future compared to period_end, 
            # it likely belongs to the previous year (Year-end period case).
            if pd.notna(p_start) and pd.notna(period_end):
                p_start_ts = pd.Timestamp(p_start)
                p_end_limit = pd.Timestamp(period_end) + pd.Timedelta(days=31)
                if p_start_ts > p_end_limit:
                    p_start = p_start_ts.replace(year=p_start_ts.year - 1)
            
            if pd.notna(p_end) and pd.notna(period_end):
                p_end_ts = pd.Timestamp(p_end)
                p_end_limit = pd.Timestamp(period_end) + pd.Timedelta(days=31)
                if p_end_ts > p_end_limit:
                    p_end = p_end_ts.replace(year=p_end_ts.year - 1)
            # -----------------------------
            
            # 해당 구간의 계약 필터링 (기간 AND 회사)
            p_contracts = filter_by_period(contracts, p_start, p_end)
            
            # 회사 필터링 추가 (rule_group의 '회사'를 기준으로 강력 필터링)
            # consecutive_rules의 '회사' 컬럼이 비어있거나 부정확할 수 있으므로, 메인 규칙의 회사를 따름
            target_company = company
            if not target_company or target_company == '전체':
                 # 메인 규칙에 회사가 없으면 p_rules에서 시도
                 target_company = p_rules['회사'].iloc[0] if '회사' in p_rules.columns else None
                 
            if target_company and target_company != '전체':
                 if '회사' in p_contracts.columns:
                     # Apply flexible match for company name
                     p_contracts = p_contracts[p_contracts['회사'].apply(lambda x: flexible_match(x, target_company))]

            p_total = p_contracts['보험료'].sum() if not p_contracts.empty else 0
            
            # 해당 구간에서 달성한 최고 목표 찾기
            max_achieved_target = 0
            p_targets = p_rules[p_rules['목표실적'] <= p_total]['목표실적']
            if not p_targets.empty:
                max_achieved_target = p_targets.max()
            
            # Structure possible targets with rewards
            possible_targets_data = []
            if '목표실적' in p_rules.columns:
                # Drop duplicates and sort
                unique_targets = p_rules[['목표실적', '보상금액']].drop_duplicates().sort_values('목표실적')
                for _, r in unique_targets.iterrows():
                    possible_targets_data.append({
                        'target': r['목표실적'],
                        'reward': r['보상금액'] if pd.notna(r['보상금액']) else 0
                    })

            period_stats[int(period_num)] = {
                'perf': p_total,
                'max_target': max_achieved_target,
                'contracts': p_contracts.to_dict('records') if not p_contracts.empty else [],
                'possible_targets': possible_targets_data,
                'start': p_start,
                'end': p_end
            }
        
        # 최종 보상 결정 (마지막 구간 기준)
        final_reward = 0
        
        # If prev_cond is missing, infer it from rank
        if total_periods > 1 and ('이전구간조건' not in award_rules.columns or award_rules['이전구간조건'].fillna(0).sum() == 0):
            # We need to map Period N rule -> Period N-1 Target
            # Strategy: Sort Period N-1 by Target, Period N by Reward (since targets might be equal)
            # Then map by index.
            temp_rules = []
            for p in range(2, total_periods + 1):
                prev_p = p - 1
                if prev_p not in period_stats: continue
                
                # Get rules for prev and curr
                # We must use the original award_rules to get the targets/rewards for matching
                r_prev = award_rules[award_rules['구간번호'] == prev_p].sort_values('목표실적')
                r_curr = award_rules[award_rules['구간번호'] == p].sort_values('보상금액')
                
                if len(r_prev) == len(r_curr):
                    # 1-to-1 mapping
                    prev_targets = r_prev['목표실적'].values
                    curr_indices = r_curr.index
                    for idx, pt in zip(curr_indices, prev_targets):
                        award_rules.loc[idx, '이전구간조건'] = pt
        
        if total_periods in period_stats:
            last_rules = award_rules[award_rules['구간번호'] == total_periods].sort_values('보상금액', ascending=False)
            curr_perf = period_stats[total_periods]['perf']
            
            # 이전 구간들의 최소 달성 실적 (복합 조건 대응용)
            # 단, 여기서는 "직전 단계의 달성 Target"을 의미하는게 더 적합할 수 있음. 
            # But 'max_target' records the Tier Target achieved.
            prev_ok_all = True
            prev_min_achieved = float('inf')
            
            # Check all previous periods
            if total_periods > 1:
                for p in range(1, total_periods):
                    p_max = period_stats.get(p, {}).get('max_target', 0)
                    if p_max == 0:
                        prev_ok_all = False
                        break
                    prev_min_achieved = min(prev_min_achieved, p_max)
            
            if prev_ok_all:
                for _, r in last_rules.iterrows():
                    target = r.get('목표실적', 0)
                    reward = r.get('보상금액', 0)
                    if pd.isna(reward): reward = 0
                    if pd.isna(target): target = 0
                    
                    # 이전구간조건 (Inferred or Explicit)
                    prev_cond = r.get('이전구간조건', 0)
                    
                    # Check previous condition
                    prev_cond_ok = (pd.isna(prev_cond) or prev_cond == 0 or prev_min_achieved >= prev_cond)
                    
                    # Check current condition
                    curr_ok = (curr_perf >= target) if target > 0 else True
                    
                    if prev_cond_ok and curr_ok:
                        # 보상액 찾기 - 내림차순 정렬이므로 첫 번째 달성 건이 최적
                        final_reward = reward
                        break
        
        # --- Scenarios Generation for UI (Explicit Matrix) ---
        scenarios = []
        if total_periods > 0:
            # 최종 구간의 규칙들을 기준으로 역추적하여 시나리오 완성
            last_rules = award_rules[award_rules['구간번호'] == total_periods].sort_values('보상금액')
            
            for _, last_rule in last_rules.iterrows():
                scenario = {
                    'reward': last_rule.get('보상금액', 0),
                    'targets': {}
                }
                
                # 최종 구간 목표
                scenario['targets'][total_periods] = last_rule.get('목표실적', 0)
                
                # 역추적 (Backtrack)
                curr_rule = last_rule
                for p in range(total_periods, 1, -1):
                    prev_p = p - 1
                    target_prev = curr_rule.get('이전구간조건', 0)
                    
                    if pd.isna(target_prev) or target_prev == 0:
                        # 명시적 조건이 없으면 매칭 로직 재사용 (Inferred)
                        # Find the rule in prev_p that corresponds to this tier
                        # (Reuse the sort-based inference if '이전구간조건' was filled in Lines 241-262)
                        # Since we modified award_rules in-place earlier, '이전구간조건' SHOULD be there if inferred.
                        pass
                        
                    scenario['targets'][prev_p] = target_prev
                    
                    # 다음 반복(더 이전 구간)을 위해 curr_rule 업데이트 필요
                    # 하지만 '이전구간조건'만으로는 이전 규칙 Row를 특정하기 어려움 (같은 목표값이 있을 수 있음)
                    # 여기서는 단순히 목표값만 추적하여 저장
                    
                    # 만약 3구간 이상이라면, 이전 구간의 규칙을 찾아야 '그 이전' 조건을 알 수 있음.
                    # 현재 로직상 2구간(1->2)이 대부분이므로, 
                    # 3구간 이상일 경우 '이전구간조건'이 체인이 끊길 수 있음.
                    # FIXME: 3구간 이상 완벽 지원하려면 award_rules에 이전 Row Index를 매핑했어야 함.
                    # 현재는 2구간 가정 또는 '이전구간조건' 필드가 채워져 있다고 가정.
                    
                    if prev_p > 1:
                        # Find rule in prev_prev_p ? No, we need rule in prev_p that has target == target_prev
                        # This is ambiguous if multiple rules have same target.
                        # For now, simplistic approach: match first rule with that target
                        prev_rules_match = award_rules[
                            (award_rules['구간번호'] == prev_p) & 
                            (award_rules['목표실적'] == target_prev)
                        ]
                        if not prev_rules_match.empty:
                            curr_rule = prev_rules_match.iloc[0]
                        else:
                            curr_rule = {} # Chain broken
                
                scenarios.append(scenario)

        # 모든 구간의 계약 정보를 하나로 합치기
        all_contracts_list = []
        for p_v in period_stats.values():
            if 'contracts' in p_v:
                all_contracts_list.extend(p_v['contracts'])

        return {
            '실적': period_stats[total_periods]['perf'] if total_periods in period_stats else 0,
            '지급금액': final_reward,
            '최종지급금액': final_reward,
            '달성단계': 1 if final_reward > 0 else 0,
            '달성률': 100.0 if final_reward > 0 else 0.0, # 단순화
            '부족금액': 0,
            'period_stats': period_stats,
            'scenarios': scenarios, # UI용 상세 시나리오
            'steps_info': [], # 연속형은 steps_info 대신 period_stats/scenarios 사용
            'contracts_info': all_contracts_list
        }
    except Exception as e:
        import traceback
        print(f"Error in calc_continuous_type: {e}")
        traceback.print_exc()
        return None



def calculate_single_award(contracts: pd.DataFrame, rule_group: pd.DataFrame,
                           period_start: datetime, period_end: datetime,
                           consecutive_rules: pd.DataFrame = None) -> Dict[str, Any]:
    """단일 시상 계산 (그룹화된 규칙 기반)"""
    rule = rule_group.iloc[0]
    award_type = rule.get('유형', '')
    
    # 0. 회사 필터링
    # 시상 규칙의 회사(예: KB손해)와 일치하는 계약만 대상으로 계산해야 함
    rule_company = rule.get('회사', '')
    if rule_company and rule_company != '전체':
        # 계약 데이터에서 사용 가능한 회사 컬럼 찾기
        contract_company_col = None
        for col in ['회사', '원수사', '보험사']:
            if col in contracts.columns:
                contract_company_col = col
                break
        
        # 해당 회사 계약만 필터링
        if contract_company_col:
            contracts = contracts[contracts[contract_company_col] == rule_company]
    
    # 1. 포함상품/상품구분 필터링
    포함상품 = rule.get('포함상품', None)
    상품구분 = rule.get('상품구분', None)
    
    # 시상 규칙 시트의 C열(상품구분)에 지정된 카테고리만 실적으로 인정
    # 데이터 로더의 filter_by_products 함수가 '분류' 컬럼을 활용하여 정교하게 필터링함
    filtered_contracts = filter_by_products(contracts, 포함상품, 상품구분)
    
    # 2. 시상 기간 필터링 (시상규칙의 기간과 대시보드 기간의 교집합)
    rule_start = rule.get('시작일')
    rule_end = rule.get('종료일')
    
    # '연속형'은 내부에서 기간을 따로 처리하므로 다른 유형만 여기서 필터링
    calc_start = period_start
    if pd.notna(rule_start) and award_type != '연속형':
        if pd.notna(rule_start):
            calc_start = pd.to_datetime(rule_start)
        
    calc_end = period_end
    if pd.notna(rule_end) and award_type != '연속형':
        calc_end = min(pd.Timestamp(period_end), pd.to_datetime(rule_end))
    
    # 기간 유효성 체크
    if pd.notna(rule_start) and pd.Timestamp(period_end) < pd.Timestamp(rule_start):
        return None
    else:
        # 3. 유형별 계산
        if award_type == '정률형':
            result = calc_rate_type(filter_by_period(filtered_contracts, calc_start, calc_end), rule_group)
        elif award_type == '계단형':
            result = calc_step_type(filter_by_period(filtered_contracts, calc_start, calc_end), rule_group)
        elif award_type == '연속형':
            result = calc_continuous_type(filtered_contracts, rule_group, period_start, period_end, consecutive_rules)
            
            # Fallback logic
            has_step_columns = any(f'{i}단계보상' in rule_group.columns for i in range(1, 4))
            if (not result or result.get('지급금액', 0) == 0) and has_step_columns:
                 fallback_result = calc_step_type(filter_by_period(filtered_contracts, calc_start, calc_end), rule_group)
                 if isinstance(fallback_result, dict) and fallback_result.get('지급금액', 0) > 0:
                     if result and 'period_stats' in result:
                         fallback_result['period_stats'] = result['period_stats']
                     result = fallback_result
                 elif not result:
                     result = fallback_result
        elif award_type == '합산형':
            result = calc_step_type(filter_by_period(filtered_contracts, calc_start, calc_end), rule_group)
        else:
            result = {'실적': 0, '지급금액': 0, '달성단계': None, '달성률': 0, '다음목표': None, '부족금액': 0}

    # --- Payout Attribution Logic (지급 귀속월 처리) ---
    raw_payout = result.get('지급금액', 0)
    expected_payout = raw_payout
    final_payout = 0
    
    is_payout_period = True
    if pd.notna(rule_end) and pd.notna(period_end):
        re_date = pd.Timestamp(rule_end).normalize()
        pe_date = pd.Timestamp(period_end).normalize()
        
        # 조회 기간이 끝나기 전에 규칙이 끝나지 않았다면 (즉 현재 조회일 < 지급일)
        if pe_date < re_date:
            is_payout_period = False

    if is_payout_period:
        final_payout = raw_payout
    else:
        final_payout = 0 # 아직 지급 시기가 아님 (예상 금액으로만 존재)
        # 상세 내역(Rows)에 대해서도 지급액 0 처리 (UI 혼선 방지)
        if 'rows' in result and isinstance(result['rows'], list):
            for r in result['rows']:
                r['expected_payout'] = r.get('지급금액', 0)
                r['지급금액'] = 0
    
    result['지급금액'] = final_payout
    result['예상지급금액'] = expected_payout
    result['지급시기도래'] = is_payout_period

    # 공통 정보 추가
    result['회사'] = rule_group['회사'].iloc[0] if '회사' in rule_group.columns else rule.get('회사', '')
    result['시상명'] = rule_group['시상명'].iloc[0] if '시상명' in rule_group.columns else rule.get('시상명', '')
    result['유형'] = award_type
    result['비교시상'] = rule.get('비교시상', None)
    result['시작일'] = rule_start
    result['종료일'] = rule_end
    result['상품구분'] = 상품구분  # UI 표시용 추가
    
    # 4. 결과에 포함할 계약 리스트 (3단계 근거 데이터)
    # calc_continuous_type 등에서 이미 단계별 계약을 포함했다면 덮어쓰지 않음
    if 'contracts_info' not in result:
        # 시간 필터링된 계약 리스트 포함 ({접수일, 상품명, 보험료, 계약자, 분류, 회사})
        evidence_contracts = filter_by_period(filtered_contracts, calc_start, calc_end)
        
        # 컬럼 존재 여부 확인 후 선택
        target_cols = ['접수일', '상품명', '보험료']
        opt_cols = ['계약자', '분류', '회사', '지점', '보험사'] 
        
        for pool_col in opt_cols:
            if pool_col in evidence_contracts.columns:
                target_cols.append(pool_col)
            elif pool_col == '회사' and '보험사' in evidence_contracts.columns:
                evidence_contracts['회사'] = evidence_contracts['보험사']
                if '회사' not in target_cols: target_cols.append('회사')
                
        # 중복 제거 (target_cols 내 중복 방지)
        target_cols = list(dict.fromkeys(target_cols))
        result['contracts_info'] = evidence_contracts[target_cols].to_dict('records') if not evidence_contracts.empty else []
    
    return result


def calculate_all_awards(contracts: pd.DataFrame, rules: pd.DataFrame,
                          period_start: datetime, period_end: datetime,
                          agent_name: Optional[str] = None,
                          company_filter: Optional[str] = None,
                          consecutive_rules: pd.DataFrame = None,
                          rule_consecutive_map: Optional[Dict] = None,
                          rule_groups: Optional[List] = None) -> pd.DataFrame:
    """모든 시상 계산 (규칙 그룹화 처리)"""
    results = []
    
    # 연속형 규칙 로드 (외부에서 전달받지 않은 경우)
    if consecutive_rules is None and rule_consecutive_map is None:
        try:
            from data_loader import load_consecutive_rules
            consecutive_rules = load_consecutive_rules()
        except Exception:
            consecutive_rules = pd.DataFrame()
    
    # 그룹화된 규칙이 전달되지 않은 경우 직접 수행
    if rule_groups is None:
        filtered_rules = rules.copy()
        if company_filter and company_filter != "전체":
            filtered_rules = filtered_rules[filtered_rules['회사'] == company_filter]
        rule_groups = filtered_rules.groupby(['회사', '시상명', '유형'])
    
    # 시상명 및 유형별로 그룹화하여 처리
    for (company, award_name, award_type), group in rule_groups:
        # --- 기간 필터링 로직 추가 ---
        # 시상 전체 기간이 현재 조회 기간과 하나라도 겹치는지 확인
        group_start = pd.to_datetime(group['시작일']).min() if '시작일' in group.columns else pd.NaT
        group_end = pd.to_datetime(group['종료일']).max() if '종료일' in group.columns else pd.NaT
        
        # 연속형의 경우 세부 규칙(구간별 날짜)에서도 기간 합산 확인
        if award_type == '연속형':
            c_rules = pd.DataFrame()
            
            # 최적화: 미리 계산된 맵이 있으면 사용
            if rule_consecutive_map is not None and (company, award_name, award_type) in rule_consecutive_map:
                c_rules = rule_consecutive_map[(company, award_name, award_type)]
            # 없으면 기존 방식으로 검색 (백워드 호환성)
            elif consecutive_rules is not None and not consecutive_rules.empty:
                # 유연한 매칭 함수 (속도 위해 단순화)
                def simple_fuzzy(v1, v2):
                    if pd.isna(v1) or pd.isna(v2): return False
                    v1_c, v2_c = str(v1).replace(' ', '').replace('_', ''), str(v2).replace(' ', '').replace('_', '')
                    return v1_c in v2_c or v2_c in v1_c
                    
                c_rules = consecutive_rules[
                    (consecutive_rules['시상명'].apply(lambda x: simple_fuzzy(x, award_name))) & 
                    (consecutive_rules['회사'].apply(lambda x: simple_fuzzy(x, company)))
                ]
            
            if not c_rules.empty:
                c_start = pd.to_datetime(c_rules['시작일']).min()
                c_end = pd.to_datetime(c_rules['종료일']).max()
                group_start = min(group_start, c_start) if pd.notna(group_start) and pd.notna(c_start) else (c_start if pd.isna(group_start) else group_start)
                group_end = max(group_end, c_end) if pd.notna(group_end) and pd.notna(c_end) else (c_end if pd.isna(group_end) else group_end)
        
        # 필터링: 시상 기간이 조회 기간을 완전히 벗어난 경우 건너뜀
        if pd.notna(group_start) and pd.notna(group_end):
            if group_end < pd.Timestamp(period_start) or group_start > pd.Timestamp(period_end):
                continue
        # ---------------------------

        try:
             
            # 연속형이나 합산형은 전체 그룹을 한번에 처리해야 함
            if award_type in ['연속형', '합산형']:
                overall_result = calculate_single_award(contracts, group, period_start, period_end, consecutive_rules)


                if overall_result:
                    res = overall_result.copy()
                    res['설계사'] = agent_name or '전체'
                    res['회사'] = company
                    res['시상명'] = award_name
                    res['유형'] = award_type
                    # 정렬을 위한 기본값
                    res['정렬_목표실적'] = 0 
                    
                    # 기준보상 추정 (연속형은 시나리오 중 최대 보상 혹은 최종 보상)
                    if 'scenarios' in res and res['scenarios']:
                        res['기준보상'] = max([s.get('reward', 0) for s in res['scenarios']])
                    else:
                        res['기준보상'] = res.get('지급금액', 0)

                    # 기간 정보는 전체 그룹 범위로 설정
                    if pd.notna(group_start): res['시작일'] = group_start
                    if pd.notna(group_end): res['종료일'] = group_end

                    results.append(res)
            else:
                # 계단형, 정률형 등은 각 행을 개별적으로 보여달라는 요청 (모든 행 노출)
                # 단, 같은 시상명 내에서는 일반적으로 가장 높은 금액 하나만 지급되어야 함.
                # 따라서 개별 계산 후, 그룹 내 최고 금액만 남기고 나머지는 0원 처리
                
                temp_results = []
                for _, rule in group.iterrows():
                    # 1개 행으로 구성된 임시 그룹 생성
                    single_rule_group = pd.DataFrame([rule])
                    res = calculate_single_award(contracts, single_rule_group, period_start, period_end)
                    
                    if res:
                        res['설계사'] = agent_name or '전체'
                        # print(f"DEBUG: res for normal rule ({_}): {res.get('지급금액', 'No Amount')}")
                        # 개별 행의 목표실적 보존 (정렬용 + 표시용)
                        res['목표실적'] = get_safe_val(rule, ['목표실적', 'target'], 0)
                        res['정렬_목표실적'] = res['목표실적']
                        
                        # 중요: 실제 달성 여부와 상관없이 '이 단계를 달성했을 때 받을 금액'을 저장 (가이드용)
                        res['기준보상'] = get_safe_val(rule, ['보상금액', '지급금액', 'reward'], 0)
                        
                        # 정률형의 경우 실적 기반이므로 현재 실적 기준 혹은 지급금액 사용
                        if award_type == '정률형':
                            res['기준보상'] = res.get('지급금액', 0)

                        temp_results.append(res)
                
                # print(f"DEBUG: temp_results count: {len(temp_results)}")
                
                # 같은 시상명 내 최고 지급액 선정
                if temp_results:
                    # 지급금액 내림차순 정렬
                    temp_results.sort(key=lambda x: x['지급금액'], reverse=True)
                    
                    # 1등만 금액 유지, 나머지는 0원 (단, 화면엔 노출)
                    best_idx = 0
                    if temp_results[0]['지급금액'] > 0:
                        for i in range(1, len(temp_results)):
                            temp_results[i]['지급금액'] = 0
                            temp_results[i]['최종지급금액'] = 0 # 미리 초기화
                    
                    # 원래 순서(목표실적 오름차순)로 다시 정렬하여 추가 (화면 표시용)
                    temp_results.sort(key=lambda x: x.get('정렬_목표실적', 0))
                    results.extend(temp_results)

        except Exception as e:
            results.append({
                '설계사': agent_name or '전체',
                '회사': company,
                '시상명': award_name,
                '유형': award_type,
                '실적': 0,
                '지급금액': 0,
                '달성단계': None,
                '달성률': 0,
                '오류': str(e),
                '비교시상': None,
                '시작일': group_start if pd.notna(group_start) else pd.NaT,
                '종료일': group_end if pd.notna(group_end) else pd.NaT
            })
    
    if not results:
        return pd.DataFrame()
        
    df = pd.DataFrame(results)
    
    # 4. 결과 정렬 (회사 -> 시상명 -> 목표실적 순)
    # 정렬을 통해 같은 시상끼리 뭉쳐 보이게 함
    if '정렬_목표실적' in df.columns:
        df = df.sort_values(by=['회사', '시상명', '정렬_목표실적'])
    else:
        df = df.sort_values(by=['회사', '시상명'])
    
    return df


def resolve_competing_awards(results_df: pd.DataFrame) -> pd.DataFrame:
    """경쟁 시상 처리: 같은 비교시상 그룹 내 최대값만 선택"""
    if results_df.empty:
        return results_df
    
    results = results_df.copy()
    results['선택여부'] = True
    results['최종지급금액'] = results['지급금액']
    
    # 비교시상이 있는 항목 처리
    # '비교시상' 컬럼이 있고 빈 문자열이 아닌 경우
    has_comparison = results['비교시상'].notna() & (results['비교시상'].astype(str).str.strip() != '')
    
    if has_comparison.any():
        for group_id in results[has_comparison]['비교시상'].unique():
            group_mask = results['비교시상'] == group_id
            group_indices = results[group_mask].index
            
            if len(group_indices) <= 1:
                continue
            
            # 그룹 내 최대 지급금액 찾기
            max_val = results.loc[group_indices, '지급금액'].max()
            
            # 최대값이 0보다 큰 경우, 최대값을 가진 첫 번째 항목만 선택 (동점 시 하나만 또는 모두 선택은 정책에 따름)
            # 여기서는 정의서의 '가장 높은 금액 하나만' 원칙 적용
            found_max = False
            for idx in group_indices:
                if results.loc[idx, '지급금액'] == max_val and not found_max and max_val > 0:
                    results.loc[idx, '선택여부'] = True
                    results.loc[idx, '최종지급금액'] = results.loc[idx, '지급금액']
                    found_max = True
                else:
                    results.loc[idx, '선택여부'] = False
                    results.loc[idx, '최종지급금액'] = 0
                    
    return results


def get_award_summary(results_df: pd.DataFrame) -> Dict[str, Any]:
    """시상 결과 요약 통계"""
    if results_df.empty:
        return {'총지급예상금액': 0, '시상개수': 0, '선택된시상개수': 0, '평균달성률': 0}
    
    selected = results_df[results_df['선택여부'] == True].copy()
    valid_rates = results_df['달성률'].dropna()
    
    # 달성된 시상 수 계산 (같은 시상명+회사는 하나로 취급)
    # 실제 지급금액이 있는 유니크한 (회사, 시상명) 조합 수
    achieved_awards = selected[selected['최종지급금액'] > 0]
    num_achieved = 0
    if not achieved_awards.empty:
        num_achieved = len(achieved_awards.groupby(['회사', '시상명']))

    return {
        '총지급예상금액': selected['최종지급금액'].sum(),
        '시상개수': len(results_df.groupby(['회사', '시상명'])),
        '선택된시상개수': num_achieved,
        '평균달성률': valid_rates.mean() if len(valid_rates) > 0 else 0
    }


def calculate_all_agents_awards(contracts: pd.DataFrame, rules: pd.DataFrame,
                                period_start: datetime, period_end: datetime,
                                company_filter: Optional[str] = None,
                                consecutive_rules: pd.DataFrame = None) -> pd.DataFrame:
    """모든 설계사에 대해 시상 계산 수행 (최적화 버전)"""
    
    # --- 전역 최적화: 시상 규칙별 연속형 매칭 및 그룹화 미리 계산 ---
    rule_consecutive_map = {}
    
    # 0. 규칙 필터링 (회사 필터 반영)
    filtered_rules = rules.copy()
    if company_filter and company_filter != "전체":
        filtered_rules = filtered_rules[filtered_rules['회사'] == company_filter]
        
    # 1. 시상 규칙 그룹화 (미리 계산)
    rule_groups = list(filtered_rules.groupby(['회사', '시상명', '유형']))
    
    if consecutive_rules is not None and not consecutive_rules.empty:
        # 데이터 클리닝 및 그룹화 (속도 위해)
        c_rules = consecutive_rules.copy()
        c_rules['__clean_name'] = c_rules['시상명'].astype(str).str.replace(' ', '', regex=False).str.replace('_', '', regex=False)
        c_rules['__clean_company'] = c_rules['회사'].astype(str).str.replace(' ', '', regex=False).str.replace('_', '', regex=False)
        
        # 시상 규칙별로 필터링된 데이터 미리 저장
        for (company, award_name, award_type), _ in rule_groups:
            if award_type == '연속형':
                clean_name = str(award_name).replace(' ', '').replace('_', '')
                clean_company = str(company).replace(' ', '').replace('_', '')
                
                matched = c_rules[
                    (c_rules['__clean_name'].str.contains(clean_name, na=False) | c_rules['__clean_name'].apply(lambda x: clean_name in str(x) if pd.notna(x) else False)) &
                    (c_rules['__clean_company'].str.contains(clean_company, na=False) | c_rules['__clean_company'].apply(lambda x: clean_company in str(x) if pd.notna(x) else False))
                ]
                if not matched.empty:
                    rule_consecutive_map[(company, award_name, award_type)] = matched.drop(columns=['__clean_name', '__clean_company'])

    # 2. 설계사별 그룹화
    if '사원명' not in contracts.columns:
        agents = ['Unknown']
        contracts = contracts.copy()
        contracts['사원명'] = 'Unknown'
    else:
        agents = contracts['사원명'].unique()
    
    all_results = []
    
    for agent in agents:
        agent_contracts = contracts[contracts['사원명'] == agent]
        
        # 3. 각 설계사별 시상 계산
        results = calculate_all_awards(
            agent_contracts,
            filtered_rules, # 필터링된 규칙 전달
            period_start,
            period_end,
            agent_name=agent,
            company_filter=None, # 이미 위에서 필터링함
            consecutive_rules=consecutive_rules,
            rule_consecutive_map=rule_consecutive_map,
            rule_groups=rule_groups # 미리 계산된 그룹 전달
        )
        
        if not results.empty:
            # 경쟁 시상 처리
            results = resolve_competing_awards(results)
            all_results.append(results)
    
    if not all_results:
        return pd.DataFrame()
        
    return pd.concat(all_results, ignore_index=True)


def get_company_summary(all_results: pd.DataFrame) -> Dict[str, Any]:
    """회사 전체 시상 요약 집계"""
    if all_results.empty:
        return {
            '총예상시상금': 0,
            '확정시상수': 0,
            '진행중시상수': 0,
            '미달성시상수': 0,
            '총설계사수': 0,
            '달성률평균': 0
        }
    
    # 선택된 시상만 (경쟁 시상 처리 후)
    selected = all_results[all_results.get('선택여부', True) == True]
    
    # 확정: 지급금액 > 0
    confirmed = selected[selected['최종지급금액'] > 0]
    
    # 진행중: 달성률 50% 이상, 미달성
    in_progress = selected[(selected['달성률'] >= 50) & (selected['최종지급금액'] == 0)]
    
    # 미달성: 달성률 50% 미만
    not_achieved = selected[selected['달성률'] < 50]
    
    # 설계사 수
    agent_count = all_results['설계사'].nunique() if '설계사' in all_results.columns else 0
    
    return {
        '총예상시상금': confirmed['최종지급금액'].sum(),
        '확정시상수': len(confirmed),
        '진행중시상수': len(in_progress),
        '미달성시상수': len(not_achieved),
        '총설계사수': agent_count,
        '달성률평균': all_results['달성률'].mean() if len(all_results) > 0 else 0
    }


def find_golden_opportunities(
    all_results: pd.DataFrame,
    rules: pd.DataFrame
) -> pd.DataFrame:
    """달성 임박 시상 + ROI 분석 (골든 기회)"""
    if all_results.empty:
        return pd.DataFrame()
    
    opportunities = []
    
    for _, row in all_results.iterrows():
        # 아직 달성하지 않았지만 진행 중인 시상
        payout = row.get('최종지급금액', 0)
        achievement = row.get('달성률', 0)
        
        if payout == 0 and 50 <= achievement < 100:
            # 다음 목표까지 부족 금액 계산
            target = row.get('목표실적', 0)
            perf = row.get('실적', 0)
            gap = max(0, target - perf)
            
            # 예상 보상 (다음 단계 보상)
            expected_reward = row.get('지급금액', 0)
            if expected_reward == 0:
                # 규칙에서 보상 찾기
                award_name = row.get('시상명', '')
                company = row.get('회사', '')
                matching_rules = rules[(rules['시상명'] == award_name) & (rules['회사'] == company)]
                if not matching_rules.empty:
                    for i in range(1, 10):
                        t = matching_rules.iloc[0].get(f'{i}단계목표')
                        r = matching_rules.iloc[0].get(f'{i}단계보상')
                        if pd.notna(t) and t > perf and pd.notna(r):
                            expected_reward = r
                            break
            
            # ROI 계산 (보상 / 필요 실적)
            roi = expected_reward / gap if gap > 0 else 0
            
            if expected_reward > 0:
                opportunities.append({
                    '설계사': row.get('설계사', ''),
                    '시상명': row.get('시상명', ''),
                    '회사': row.get('회사', ''),
                    '현재실적': perf,
                    '필요실적': gap,
                    '예상보상': expected_reward,
                    'ROI': roi,
                    '달성률': achievement
                })
    
    if not opportunities:
        return pd.DataFrame()
    
    df = pd.DataFrame(opportunities)
    # ROI 높은 순으로 정렬
    df = df.sort_values('ROI', ascending=False)
    return df
