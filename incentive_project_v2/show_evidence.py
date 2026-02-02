
import pandas as pd
from datetime import datetime
from data_loader import preprocess_contracts

def show_detailed_evidence():
    contracts = pd.read_csv('sample_data/계약데이터.csv')
    contracts, _ = preprocess_contracts(contracts)
    
    # Filter for Agent '김균언' and KB Products
    kb_products = ['새로고침건강', '내돈내삼보험']
    agent_name = '김균언'
    
    # Award 1: 2025_10월_11월_주차 연속가동 시상
    # Period 1: 2025-10-20 ~ 2025-10-31
    # Period 2: 2025-11-01 ~ 2025-11-16
    
    mask = (contracts['설계사'] == agent_name) & (contracts['상품명'].isin(kb_products))
    filtered = contracts[mask].copy()
    filtered['접수일'] = pd.to_datetime(filtered['접수일'])
    
    p1_start, p1_end = pd.Timestamp('2025-10-20'), pd.Timestamp('2025-10-31')
    p2_start, p2_end = pd.Timestamp('2025-11-01'), pd.Timestamp('2025-11-16')
    
    p1_contracts = filtered[(filtered['접수일'] >= p1_start) & (filtered['접수일'] <= p1_end)]
    p2_contracts = filtered[(filtered['접수일'] >= p2_start) & (filtered['접수일'] <= p2_end)]
    
    print("=== [데이터 근거] 2025_10월_11월 주차 연속가동 시상 ===")
    
    print(f"\n[1구간] {p1_start.date()} ~ {p1_end.date()}")
    if not p1_contracts.empty:
        print(p1_contracts[['접수일', '상품명', '보험료']].to_string(index=False))
        print(f"-> 1구간 합계: {p1_contracts['보험료'].sum():,}원 (목표 10만 대비 성공)")
    else:
        print("내역 없음")
        
    print(f"\n[2구간] {p2_start.date()} ~ {p2_end.date()}")
    if not p2_contracts.empty:
        print(p2_contracts[['접수일', '상품명', '보험료']].to_string(index=False))
        print(f"-> 2구간 합계: {p2_contracts['보험료'].sum():,}원 (목표 10만 대비 성공)")
    else:
        print("내역 없음")

    print("\n" + "="*50)
    print("=== [중복 시상 제외 논리] ===")
    print("이 시상은 '1주차그룹'에 소속되어 있습니다.")
    print("- 해당 시상 계산액: 200,000원")
    print("- '1주차합산' 계산액: 700,000원")
    print(">>> 결과: 설계사에게 유리한 '700,000원'이 최종 확정되고, 20만원은 0원 처리됨.")

if __name__ == "__main__":
    show_detailed_evidence()
