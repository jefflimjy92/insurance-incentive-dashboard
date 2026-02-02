import pandas as pd
from incentive_engine import calculate_single_award, calc_step_type

def test_company_separation():
    # 1. Mock Data
    # Two contracts: one for KB, one for Samsung
    contracts = pd.DataFrame([
        {'접수일': pd.Timestamp('2026-01-10'), '회사': 'KB손해보험', '상품명': 'KB건강', '보험료': 100000, '분류': '인보험', '사원명': 'TestAgent'},
        {'접수일': pd.Timestamp('2026-01-10'), '회사': '삼성화재', '상품명': '삼성건강', '보험료': 500000, '분류': '인보험', '사원명': 'TestAgent'}
    ])
    
    # Rule for KB only
    period_start = pd.Timestamp('2026-01-01')
    period_end = pd.Timestamp('2026-01-31')
    
    kb_rule_group = pd.DataFrame([
        {
            '시상명': 'KB 정률시상', '회사': 'KB손해보험', '유형': '정률형', 
            '시작일': period_start, '종료일': period_end, 
            '상품구분': '인보험', '목표실적': 0, '지급률': 10
        }
    ])
    
    print("--- Test: Company Separation ---")
    print(f"Contracts Total: {contracts['보험료'].sum()} (KB: 100k, Samsung: 500k)")
    
    # 2. Run Calculation for KB Rule
    # Expectation: Should only consider KB contract (100k base), so reward should be 10% of 100k = 10k.
    # If bug exists: It might sum both (600k base), reward 60k.
    
    result = calculate_single_award(contracts, kb_rule_group, period_start, period_end)
    
    if result:
        print(f"Result for KB Rule: Performance: {result['실적']}, Reward: {result['지급금액']}")
        if result['실적'] == 100000:
            print("SUCCESS: Only KB contracts calculated.")
        elif result['실적'] == 600000:
            print("FAIL: All contracts calcualted (No company filter).")
        else:
            print(f"FAIL: Unexpected performance {result['실적']}")
    else:
        print("FAIL: No result returned.")

if __name__ == "__main__":
    test_company_separation()
