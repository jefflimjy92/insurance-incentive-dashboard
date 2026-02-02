import pandas as pd
from incentive_engine import calc_continuous_type

def verify_consecutive_separation():
    # 1. Mock Data
    print("Creating mock contracts...")
    contracts = pd.DataFrame([
        {'접수일': pd.Timestamp('2026-01-10'), '회사': 'KB손해보험', '상품명': 'KB', '보험료': 100000, '분류': '인보험', '사원명': 'T'},
        {'접수일': pd.Timestamp('2026-01-10'), '회사': '삼성화재', '상품명': 'SS', '보험료': 500000, '분류': '인보험', '사원명': 'T'}
    ])
    
    # 2. Mock Consecutive Rules (KB)
    print("Creating mock KB rule...")
    kb_rules = pd.DataFrame([
        {'회사': 'KB손해보험', '시상명': '연속', '구간번호': 1, '시작일': '2026-01-01', '종료일': '2026-01-31', '목표실적': 50000, '보상금액': 10000}
    ])
    kb_rules['시작일'] = pd.to_datetime(kb_rules['시작일'])
    kb_rules['종료일'] = pd.to_datetime(kb_rules['종료일'])
    
    # 3. Calculate for KB
    # Should be 100,000 (KB Only)
    print("Calculating KB award...")
    # NOTE: rule_group MUST have '회사' column for strict filtering to work
    kb_result = calc_continuous_type(contracts, kb_rules, pd.Timestamp('2026-01-01'), pd.Timestamp('2026-01-31'), kb_rules)
    print(f"KB Result Performance: {kb_result['실적']}")

    if kb_result['실적'] == 100000:
        print("✅ KB Correct (Calculated 100k)")
    elif kb_result['실적'] == 600000:
        print("❌ KB Failed (Calculated 600k - Mixed)")
    else:
        print(f"❌ KB Failed (Unexpected {kb_result['실적']})")
        
    # 4. Mock Consecutive Rules (Samsung)
    print("\nCreating mock Samsung rule...")
    ss_rules = pd.DataFrame([
        {'회사': '삼성화재', '시상명': '연속', '구간번호': 1, '시작일': '2026-01-01', '종료일': '2026-01-31', '목표실적': 50000, '보상금액': 10000}
    ])
    ss_rules['시작일'] = pd.to_datetime(ss_rules['시작일'])
    ss_rules['종료일'] = pd.to_datetime(ss_rules['종료일'])
    
    # 5. Calculate for Samsung
    # Should be 500,000 (Samsung Only)
    print("Calculating Samsung award...")
    ss_result = calc_continuous_type(contracts, ss_rules, pd.Timestamp('2026-01-01'), pd.Timestamp('2026-01-31'), ss_rules)
    print(f"Samsung Result Performance: {ss_result['실적']}")

    if ss_result['실적'] == 500000:
        print("✅ Samsung Correct (Calculated 500k)")
    elif ss_result['실적'] == 600000:
        print("❌ Samsung Failed (Calculated 600k - Mixed)")
    else:
        print(f"❌ Samsung Failed (Unexpected {ss_result['실적']})")

if __name__ == "__main__":
    verify_consecutive_separation()
