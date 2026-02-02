import pandas as pd
from data_loader import load_consecutive_rules, load_contracts_from_url, preprocess_contracts
from incentive_engine import calculate_single_award

def inspect_consecutive_logic():
    print("1. Loading Consecutive Rules...")
    c_rules = load_consecutive_rules()
    if c_rules.empty:
        print("Consecutive rules are empty!")
    else:
        print(f"Loaded {len(c_rules)} consecutive rules.")
        print("Columns:", c_rules.columns.tolist())
        print("\nSample Rules (Head 5):")
        print(c_rules.head(5).to_dict('records'))
        
        # Check for expected columns
        required = ['회사', '시상명', '구간번호', '목표실적', '보상금액']
        missing = [c for c in required if c not in c_rules.columns]
        if missing:
            print(f"CRITICAL: Missing columns in consecutive rules: {missing}")
            # Try to map if they exist under different names
            if '연속단계' in c_rules.columns and '구간번호' not in c_rules.columns:
                print("Found '연속단계' but not '구간번호'. Fix required in loader?")

    print("\n2. Simulating Award Calculation with Consecutive Rules...")
    # Mock data
    period_start = pd.Timestamp("2026-01-01")
    period_end = pd.Timestamp("2026-03-31")
    
    # Mock Contract
    contracts = pd.DataFrame([
        {'접수일': pd.Timestamp('2026-01-20'), '회사': 'KB손해보험', '상품명': '건강보험', '보험료': 200000, '분류': '인보험', '사원명': 'TestAgent'}
    ])
    
    # Mock Rule Group (Main Rule) that triggers consecutive calculation
    # Using a rule name that exists in the sample if possible, or a generic one
    target_award = "2026_1분기_KB멤버스 시상_A"
    rule_group = pd.DataFrame([
        {'시상명': target_award, '회사': 'KB손해보험', '유형': '연속형', '시작일': period_start, '종료일': period_end, '상품구분': '인보험'}
    ])

    print(f"Testing calculation for: {target_award}")
    try:
        from incentive_engine import calc_continuous_type
        result = calc_continuous_type(contracts, rule_group, period_start, period_end, consecutive_rules=c_rules)
        print("\nCalculation Result:")
        print(result)
        
        if 'period_stats' in result:
            print("\nPeriod Stats (Details to be rendered):")
            for p, stats in result['period_stats'].items():
                print(f"Period {p}: {stats}")
        else:
            print("\nWARNING: 'period_stats' missing in result. Detail rendering will fail.")
            
    except Exception as e:
        print(f"Calculation Error: {e}")

if __name__ == "__main__":
    inspect_consecutive_logic()
