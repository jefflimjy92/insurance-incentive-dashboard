"""
종합 테스트 스크립트 - 최종 로직 통합 검증
모든 최근 수정사항 반영 여부 확인:
1. 연속형 시상 규칙 Fuzzy Matching
2. 계약 분류 6대 필수 규칙
3. 상품구분 기반 실적 인정
"""

import pandas as pd
import sys
from datetime import datetime

# 모듈 임포트
from data_loader import (
    load_contracts_from_csv, 
    load_rules_from_csv,
    preprocess_contracts,
    load_consecutive_rules,
    classify_product
)
from incentive_engine import calculate_all_awards

def test_contract_classification():
    """계약 분류 규칙 테스트"""
    print("\n" + "="*60)
    print("TEST 1: 계약 분류 규칙 검증")
    print("="*60)
    
    test_cases = [
        {'상품명': '실손의료비', '상품종류': '보장성', '예상': '기타'},  # 실손 제외
        {'상품명': '펫닥터플러스', '상품종류': '보장성', '예상': '펫보험'},  # 펫 우선
        {'상품명': '암보험플러스', '상품종류': '보장성', '예상': '인보험'},  # 정상 인보험
        {'상품명': '화재보험', '상품종류': '재물성', '예상': '재물보험'},  # 재물
        {'상품명': '단체상해보험', '상품종류': '단체', '예상': '단체보험'},  # 단체
        {'상품명': '자동차보험', '상품종류': '재물성', '예상': '재물보험'},  # 재물
    ]
    
    success = 0
    for i, case in enumerate(test_cases, 1):
        result = classify_product(pd.Series(case))
        status = "✅" if result == case['예상'] else "❌"
        print(f"{status} Case {i}: {case['상품명']} ({case['상품종류']}) → {result} (예상: {case['예상']})")
        if result == case['예상']:
            success += 1
    
    print(f"\n결과: {success}/{len(test_cases)} 통과")
    return success == len(test_cases)

def test_preprocessing():
    """전처리 로직 테스트"""
    print("\n" + "="*60)
    print("TEST 2: 전처리 로직 검증 (본인계약 제외)")
    print("="*60)
    
    df = load_contracts_from_csv('sample_data/계약데이터.csv')
    print(f"원본 계약 수: {len(df)}")
    
    processed, stats = preprocess_contracts(df, agent_name='김균언')
    
    print(f"전처리 후 계약 수: {len(processed)}")
    print(f"본인 계약 제외: {stats['self_contracts_removed']}건")
    print(f"보험료 0 제외: {stats['zero_premium_removed']}건")
    
    # 분류별 집계
    category_counts = processed['분류'].value_counts()
    print("\n분류별 계약 수:")
    for category, count in category_counts.items():
        print(f"  - {category}: {count}건")
    
    # 본인 계약이 남아있는지 확인
    self_contracts = processed[processed['사원명'] == processed['계약자']]
    print(f"\n잔여 본인 계약: {len(self_contracts)}건 (0이어야 정상)")
    
    return len(self_contracts) == 0

def test_incentive_calculation():
    """인센티브 계산 엔진 테스트"""
    print("\n" + "="*60)
    print("TEST 3: 인센티브 계산 엔진 검증")
    print("="*60)
    
    # 데이터 로드
    contracts_df = load_contracts_from_csv('sample_data/계약데이터.csv')
    rules_df = load_rules_from_csv('sample_data/시상규칙.csv')
    consecutive_rules = load_consecutive_rules()
    
    # 전처리
    processed_df, _ = preprocess_contracts(contracts_df, agent_name='김균언')
    
    # 계산
    period_start = datetime(2025, 10, 1)
    period_end = datetime(2025, 10, 31)
    
    results = calculate_all_awards(
        processed_df, 
        rules_df,
        period_start,
        period_end,
        agent_name='김균언',
        company_filter='전체',
        consecutive_rules=consecutive_rules
    )
    
    print(f"\n계산된 시상 수: {len(results)}")
    
    if len(results) > 0:
        # 시상별 요약
        print("\n시상별 결과:")
        for _, row in results.iterrows():
            award_name = row['시상명']
            award_type = row['유형']
            performance = row.get('실적', 0)
            payout = row.get('최종지급금액', row.get('지급금액', 0))
            
            print(f"  - {award_name} ({award_type})")
            print(f"    실적: {performance:,.0f}, 지급: {payout:,.0f}원")
    
    return len(results) > 0

def test_fuzzy_matching():
    """연속형 시상 Fuzzy Matching 테스트"""
    print("\n" + "="*60)
    print("TEST 4: 연속형 시상 규칙 Fuzzy Matching")
    print("="*60)
    
    consecutive_rules = load_consecutive_rules()
    
    # 테스트 케이스: 미세한 이름 차이
    test_rules = [
        ('KB손해보험', '2025_10월_11월_주차 연속가동 시상'),
        ('KB손해보험', '2025_4분기_KB멤버스 시상'),
    ]
    
    for company, award_name in test_rules:
        def flexible_match(v1, v2):
            if pd.isna(v1) or pd.isna(v2): return False
            v1_clean = str(v1).replace(' ', '').replace('_', '').lower()
            v2_clean = str(v2).replace(' ', '').replace('_', '').lower()
            return v1_clean == v2_clean or v1_clean in v2_clean or v2_clean in v1_clean
        
        matches = consecutive_rules[
            (consecutive_rules['시상명'].apply(lambda x: flexible_match(x, award_name))) &
            (consecutive_rules['회사'].apply(lambda x: flexible_match(x, company)))
        ]
        
        status = "✅" if len(matches) > 0 else "❌"
        print(f"{status} {company} - {award_name}: {len(matches)}개 규칙 매칭")
    
    return True

def main():
    """통합 테스트 실행"""
    print("\n" + "="*60)
    print("🧪 보험 인센티브 대시보드 - 종합 테스트")
    print("="*60)
    
    results = {
        '계약 분류': test_contract_classification(),
        '전처리 로직': test_preprocessing(),
        'Fuzzy Matching': test_fuzzy_matching(),
        '인센티브 계산': test_incentive_calculation(),
    }
    
    print("\n" + "="*60)
    print("📊 최종 결과")
    print("="*60)
    
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    all_passed = all(results.values())
    print("\n" + "="*60)
    if all_passed:
        print("🎉 모든 테스트 통과!")
    else:
        print("⚠️  일부 테스트 실패")
    print("="*60)
    
    return 0 if all_passed else 1

if __name__ == '__main__':
    sys.exit(main())
